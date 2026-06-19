#!/usr/bin/env python3

import time
import threading
import subprocess

class PigpioSbusOutput:
    def __init__(
        self,
        tx_gpio=4,
        baudrate=100000,
        inverted=True,
    ):
        import pigpio

        self.pigpio = pigpio
        self.tx_gpio = tx_gpio
        self.baudrate = baudrate
        self.bit_us = int(round(1_000_000 / baudrate))
        self.inverted = inverted

        subprocess.run(
            ["sudo", "systemctl", "start", "pigpiod"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        time.sleep(0.25)

        self.pi = pigpio.pi()

        if not self.pi.connected:
            raise RuntimeError("Could not connect to pigpiod")

        self.pi.set_mode(self.tx_gpio, pigpio.OUTPUT)

        # SBUS is inverted UART, so physical idle is low.
        self.pi.write(self.tx_gpio, 0 if self.inverted else 1)
    # def

    def _physical_level(self, logical_bit):
        if self.inverted:
            return 0 if logical_bit else 1
        else:
            return 1 if logical_bit else 0
    # def

    def _add_level_pulse(self, pulses, level, duration_us):
        mask = 1 << self.tx_gpio

        if level:
            pulses.append(
                self.pigpio.pulse(mask, 0, duration_us)
            )
        else:
            pulses.append(
                self.pigpio.pulse(0, mask, duration_us)
            )
    # def

    def _byte_to_bits_8e2(self, value):
        bits = []

        # Start bit
        bits.append(0)

        # 8 data bits, LSB first
        ones = 0

        for i in range(8):
            bit = (value >> i) & 1
            bits.append(bit)

            if bit:
                ones += 1

        # Even parity bit
        parity = ones & 1
        bits.append(parity)

        # Two stop bits
        bits.append(1)
        bits.append(1)

        return bits
    # def

    def write(self, data: bytes):
        pulses = []

        current_level = None
        current_duration = 0

        for byte in data:
            bits = self._byte_to_bits_8e2(byte)

            for logical_bit in bits:
                physical = self._physical_level(logical_bit)

                if current_level is None:
                    current_level = physical
                    current_duration = self.bit_us

                elif physical == current_level:
                    current_duration += self.bit_us

                else:
                    self._add_level_pulse(
                        pulses,
                        current_level,
                        current_duration,
                    )

                    current_level = physical
                    current_duration = self.bit_us

        if current_level is not None:
            self._add_level_pulse(
                pulses,
                current_level,
                current_duration,
            )

        self.pi.wave_clear()
        self.pi.wave_add_generic(pulses)

        wave_id = self.pi.wave_create()

        if wave_id < 0:
            raise RuntimeError(f"pigpio wave_create failed: {wave_id}")

        self.pi.wave_send_once(wave_id)

        while self.pi.wave_tx_busy():
            time.sleep(0.0005)

        self.pi.wave_delete(wave_id)
    # def

    def close(self):
        self.pi.wave_clear()
        self.pi.write(self.tx_gpio, 0 if self.inverted else 1)
        self.pi.stop()
    # def


class SbusRcOutput:
    SBUS_START_BYTE = 0x0F
    SBUS_END_BYTE = 0x00

    def __init__(
        self,
        name="SBUS",
        serial_device="/dev/ttyAMA1",
        baudrate=100000,
        use_pigpio=True,
        tx_gpio=4,
        rate_hz=50,
        auto_start=True,
    ):
        self.name = name
        self.rate_hz = rate_hz
        self.enabled = False

        if not use_pigpio:
            raise RuntimeError(
                "This SBUS library is pigpio software-output only"
            )

        self.output = PigpioSbusOutput(
            tx_gpio=tx_gpio,
            baudrate=baudrate,
            inverted=True,
        )

        # SBUS channel values:
        # approx 172=1000us, 992=1500us, 1811=2000us
        self.channels = [992] * 16
        self.lock = threading.Lock()
        self.update_count = 0

        self.running = False
        self.thread = None

        self.set_channels_us(
            1000, 1200, 1200, 1300,
            1000, 2000, 1000, 2000,
            1000, 2000, 1000, 2000,
        )

        if auto_start:
            self.start()
    # def

    def close(self):
        self.stop()
        self.output.close()
    # def

    @staticmethod
    def us_to_sbus(us: int) -> int:
        us = max(1000, min(2000, int(us)))

        return int(
            round(
                (us - 1500)
                * (1811 - 172)
                / 1000
                + 992
            )
        )
    # def

    def set_channels_us(
        self,
        ch1, ch2, ch3, ch4,
        ch5, ch6, ch7, ch8,
        ch9, ch10, ch11, ch12,
    ):
        values = [
            ch1, ch2, ch3, ch4,
            ch5, ch6, ch7, ch8,
            ch9, ch10, ch11, ch12,
        ]

        with self.lock:
            for i, us in enumerate(values):
                self.channels[i] = self.us_to_sbus(us)

            self.update_count += 1
    # def

    def set_channels_sbus(self, ch1_to_ch12):
        if len(ch1_to_ch12) != 12:
            raise ValueError("Expected exactly 12 channel values")

        with self.lock:
            for i, value in enumerate(ch1_to_ch12):
                self.channels[i] = max(172, min(1811, int(value)))

            self.update_count += 1
    # def

    def _pack_channels(self):
        with self.lock:
            channels = list(self.channels)

        value = 0

        for i, ch in enumerate(channels):
            value |= (ch & 0x07FF) << (11 * i)

        return value.to_bytes(22, byteorder="little")
    # def

    def make_frame(self) -> bytes:
        payload = self._pack_channels()

        flags = 0x00

        frame = bytes([self.SBUS_START_BYTE])
        frame += payload
        frame += bytes([flags])
        frame += bytes([self.SBUS_END_BYTE])

        return frame
    # def

    def set_enabled(self, enabled: bool):
        with self.lock:
            was_enabled = self.enabled
            self.enabled = bool(enabled)

        if self.enabled and not was_enabled:
            print(f"\r[{self.name}] serial ENABLED", flush=True)
        elif not self.enabled and was_enabled:
            print(f"\r[{self.name}] serial DISABLED", flush=True)
        # if
    # def

    def enable(self):
        self.set_enabled(True)
    # def

    def disable(self):
        self.set_enabled(False)
    # def

    def is_enabled(self):
        with self.lock:
            return self.enabled
    # def

    def send(self):
        self.output.write(self.make_frame())
    # def

    def start(self):
        if self.thread is not None:
            return

        self.running = True

        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )

        self.thread.start()

        print(
            f"\r[{self.name}] started at {self.rate_hz} Hz",
            flush=True,
        )
    # def

    def stop(self):
        self.running = False

        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None
    # def

    def _run(self):
        delay = 1.0 / self.rate_hz

        while self.running:
            if self.is_enabled():
                self.send()

            time.sleep(delay)
    # def
