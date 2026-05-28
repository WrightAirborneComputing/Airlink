import time
import serial
import json
import threading

class PicoJsonRcReader:
    def __init__(
        self,
        name,
        serial_device,
        baudrate,
        rc_sender,
        auto_start=True,
    ):
        self.name = name
        self.serial_device = serial_device
        self.baudrate = baudrate
        self.rc_sender = rc_sender

        self.running = False
        self.thread = None

        self.ser = serial.Serial(
            serial_device,
            baudrate,
            timeout=0,
        )

        self.rx_buffer = ""

        if auto_start:
            self.start()

    def start(self):
        if self.thread is not None:
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.running = False

        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None

        self.ser.close()

    def _volts_to_us(self, volts):
        # Assumes joystick axis is 0.0V -> 1000, 3.3V -> 2000
        value = 1000 + (float(volts) / 3.3) * 1000
        return max(1000, min(2000, int(value)))

    def _sw1_to_us(self, sw):
        # 3-position switch: 0/1/2 -> 1000/1500/2000
        if sw == 0:
            return 1000
        if sw == 1:
            return 1500
        if sw == 2:
            return 2000
        return 1500

    def _sw_to_us(self, sw):
        # single switch: 0/1 -> 1000/2000
        return 2000 if int(sw) else 1000

    def _packet_to_channels(self, p):
        ch1 = self._volts_to_us(p.get("p1_a0_v", 1.65))
        ch2 = self._volts_to_us(p.get("p1_a1_v", 1.65))
        ch3 = self._volts_to_us(p.get("p2_a0_v", 0.0))
        ch4 = self._volts_to_us(p.get("p2_a1_v", 1.65))

        ch5 = self._sw1_to_us(p.get("p1_sw1", 1))
        ch6 = self._sw_to_us(p.get("p1_sw2", 0))
        ch7 = self._sw_to_us(p.get("p1_sw3", 0))
        ch8 = self._sw1_to_us(p.get("p2_sw1", 1))

        return ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8

    def _handle_line(self, line):
        try:
            packet = json.loads(line)

            channels = self._packet_to_channels(packet)

            self.rc_sender.set_channels(*channels)

            print(
                "\r"
                f"[{self.name}] RC channels: "
                f"{channels}",
                flush=True,
            )

        except Exception as e:
            print(
                "\r"
                f"[{self.name}] Bad Pico JSON: {line}  {e}",
                flush=True,
            )

    def _run(self):
        print(
            f"\r[{self.name}] reading {self.serial_device}@{self.baudrate}",
            flush=True,
        )

        while self.running:
            data = self.ser.read(256)

            if data:
                try:
                    self.rx_buffer += data.decode("utf-8")
                except Exception:
                    self.rx_buffer = ""
                    continue

                while "\n" in self.rx_buffer:
                    line, self.rx_buffer = self.rx_buffer.split("\n", 1)
                    line = line.strip()

                    if line:
                        self._handle_line(line)

            time.sleep(0.005)


