import time
import threading
import serial


class SerialByteOutput:
    def __init__(self, serial_device="/dev/ttyAMA1", baudrate=420000):
        self.ser = serial.Serial(
            serial_device,
            baudrate,
            timeout=0,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

    def write(self, data: bytes):
        self.ser.write(data)

    def close(self):
        self.ser.close()
    # def
# class

class PigpioSerialByteOutput:
    def __init__(self, tx_gpio=4, baudrate=420000):
        import pigpio
        import subprocess

        self.tx_gpio = tx_gpio
        self.baudrate = baudrate

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
        self.pi.write(self.tx_gpio, 1)
    # def

    def write(self, data: bytes):
        self.pi.wave_clear()

        self.pi.wave_add_serial(
            self.tx_gpio,
            self.baudrate,
            data,
        )

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
        self.pi.write(self.tx_gpio, 1)
        self.pi.stop()
    # def


class CrsfRcOutput:
    CRSF_ADDRESS_FLIGHT_CONTROLLER = 0xC8
    CRSF_FRAMETYPE_RC_CHANNELS_PACKED = 0x16

    def __init__(
        self,
        name="CRSF",
        serial_device="/dev/ttyAMA1",
        baudrate=420000,
        use_pigpio=True,
        tx_gpio=4,
        rate_hz=50,
        auto_start=True,
    ):
        self.name = name
        self.rate_hz = rate_hz
        self.enabled = False

        if use_pigpio:
            self.output = PigpioSerialByteOutput(
                tx_gpio=tx_gpio,
                baudrate=baudrate,
            )
        else:
            self.output = SerialByteOutput(
                serial_device=serial_device,
                baudrate=baudrate,
            )

        # CRSF channel values:
        # 172=1000us, 992=1500us, 1811=2000us approx
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
    def _crc8_dvb_s2(data: bytes) -> int:
        crc = 0

        for b in data:
            crc ^= b

            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0xD5) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF

        return crc
    # def

    @staticmethod
    def us_to_crsf(us: int) -> int:
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

    def set_channels_us(self,ch1,ch2,ch3,ch4,ch5,ch6,ch7,ch8,ch9,ch10,ch11,ch12):
        values = [ch1,ch2,ch3,ch4,ch5,ch6,ch7,ch8,ch9,ch10,ch11,ch12]

        with self.lock:
            for i, us in enumerate(values):
                us = max(1000, min(2000, int(us)))
                self.channels[i] = self.us_to_crsf(us)

            self.update_count += 1
    # def

    def set_channels_crsf(self, ch1_to_ch12):
        if len(ch1_to_ch12) != 12:
            raise ValueError("Expected exactly 12 channel values")

        with self.lock:
            for i, value in enumerate(ch1_to_ch12):
                self.channels[i] = max(172, min(1811, int(value)))

            self.update_count += 1
    # def

    def _pack_channels(self) -> bytes:
        with self.lock:
            channels = list(self.channels)

        value = 0

        for i, ch in enumerate(channels):
            value |= (ch & 0x7FF) << (11 * i)

        return value.to_bytes(22, byteorder="little")
    # def

    def make_frame(self) -> bytes:
        payload = self._pack_channels()

        frame_type_and_payload = bytes([
            self.CRSF_FRAMETYPE_RC_CHANNELS_PACKED
        ]) + payload

        crc = self._crc8_dvb_s2(frame_type_and_payload)

        frame = bytes([
            self.CRSF_ADDRESS_FLIGHT_CONTROLLER,
            len(frame_type_and_payload) + 1,
        ]) + frame_type_and_payload + bytes([crc])

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
        # while
    # def
# class
