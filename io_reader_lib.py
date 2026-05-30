import time
import serial
import json
import threading
import os


class PicoJsonRcReader:
    def __init__(
        self,
        name,
        serial_device,
        baudrate,
        rc_sender,
        calibration_file="calibration.json",
        calibration_delay_sec=5,
        auto_start=True,
    ):
        self.name = name
        self.serial_device = serial_device
        self.baudrate = baudrate
        self.rc_sender = rc_sender
        self.calibration_file = calibration_file
        self.calibration_delay_sec = calibration_delay_sec

        self.running = False
        self.thread = None
        self.rx_buffer = ""

        self.ser = serial.Serial(serial_device, baudrate, timeout=0)

        if os.path.exists(self.calibration_file):
            self.calibration = self._load_calibration()
        else:
            self.calibration = self._run_calibration()
            self._save_calibration(self.calibration)

        if auto_start:
            self.start()

    def _load_calibration(self):
        with open(self.calibration_file, "r") as f:
            cal = json.load(f)

        print(f"[{self.name}] Loaded calibration from {self.calibration_file}")
        return cal

    def _save_calibration(self, cal):
        with open(self.calibration_file, "w") as f:
            json.dump(cal, f, indent=4)

        print(f"[{self.name}] Saved calibration to {self.calibration_file}")

    def _drain_uart_for(self, seconds):
        end_time = time.time() + seconds

        while time.time() < end_time:
            data = self.ser.read(256)

            if data:
                try:
                    self.rx_buffer += data.decode("utf-8")
                except Exception:
                    self.rx_buffer = ""

                while "\n" in self.rx_buffer:
                    _, self.rx_buffer = self.rx_buffer.split("\n", 1)

            time.sleep(0.005)

    def _read_uart_line_blocking(self):
        while True:
            data = self.ser.read(256)

            if data:
                try:
                    self.rx_buffer += data.decode("utf-8")
                except Exception:
                    self.rx_buffer = ""
                    continue

                if "\n" in self.rx_buffer:
                    line, self.rx_buffer = self.rx_buffer.split("\n", 1)
                    return line.strip()

            time.sleep(0.005)

    def _read_packet_blocking(self):
        while True:
            line = self._read_uart_line_blocking()

            try:
                return json.loads(line)
            except Exception:
                print(f"[{self.name}] Ignoring bad JSON: {line}")

    def _sample_axis_values(self):
        p = self._read_packet_blocking()

        return {
            "roll": float(p.get("p1_a0_v", 0.0)),
            "pitch": float(p.get("p1_a1_v", 0.0)),
            "throttle": float(p.get("p2_a1_v", 0.0)),
            "yaw": float(p.get("p2_a0_v", 0.0)),
        }

    def _prompt_sample(self, prompt):
        print()
        print("\r" + prompt)
        print("\rSampling in ", end="", flush=True)

        for _ in range(self.calibration_delay_sec):
            print(".", end="", flush=True)
            self._drain_uart_for(1.0)

        print()

        sample = self._sample_axis_values()
        print("\rCaptured:", sample)

        return sample

    def _make_axis_cal(self, low, centre, high):
        return {
            "low": low,
            "centre": centre,
            "high": high,
            "low_scale": 500.0 / (centre - low) if centre != low else 1.0,
            "high_scale": 500.0 / (high - centre) if high != centre else 1.0,
        }

    def _run_calibration(self):
        print()
        print("=== Stick calibration ===")

        vertical_down = self._prompt_sample(
            "Move vertical sticks fully DOWN: throttle low, pitch down."
        )

        vertical_up = self._prompt_sample(
            "Move vertical sticks fully UP: throttle high, pitch up."
        )

        vertical_centre = self._prompt_sample(
            "Move vertical sticks to CENTRE."
        )

        horizontal_left = self._prompt_sample(
            "Move horizontal sticks fully LEFT: yaw left, roll left."
        )

        horizontal_right = self._prompt_sample(
            "Move horizontal sticks fully RIGHT: yaw right, roll right."
        )

        horizontal_centre = self._prompt_sample(
            "Move horizontal sticks to CENTRE."
        )

        return {
            "roll": self._make_axis_cal(
                horizontal_left["roll"],
                horizontal_centre["roll"],
                horizontal_right["roll"],
            ),
            "yaw": self._make_axis_cal(
                horizontal_left["yaw"],
                horizontal_centre["yaw"],
                horizontal_right["yaw"],
            ),
            "pitch": self._make_axis_cal(
                vertical_down["pitch"],
                vertical_centre["pitch"],
                vertical_up["pitch"],
            ),
            "throttle": self._make_axis_cal(
                vertical_down["throttle"],
                vertical_centre["throttle"],
                vertical_up["throttle"],
            ),
        }

    def _axis_to_us(self, axis_name, value):
        c = self.calibration[axis_name]
        value = float(value)
        centre = float(c["centre"])

        if value <= centre:
            pwm = 1500.0 + ((value - centre) * float(c["low_scale"]))
        else:
            pwm = 1500.0 + ((value - centre) * float(c["high_scale"]))

        return max(1000, min(2000, int(round(pwm))))

    def _sw3_to_us(self, sw):
        sw = int(sw)

        if sw == 0:
            return 1000
        if sw == 1:
            return 1500
        if sw == 2:
            return 2000

        return 1500

    def _sw2_to_us(self, sw):
        return 2000 if int(sw) else 1000

    def _packet_to_channels(self, p):
        ch1 = self._axis_to_us("roll", p.get("p1_a0_v", 0.0))
        ch2 = self._axis_to_us("pitch", p.get("p1_a1_v", 0.0))
        ch3 = self._axis_to_us("throttle", p.get("p2_a1_v", 0.0))
        ch4 = self._axis_to_us("yaw", p.get("p2_a0_v", 0.0))

        ch5 = self._sw2_to_us(p.get("p2_sw3", 0))
        ch6 = self._sw3_to_us(p.get("p1_sw1", 0))
        ch7 = self._sw3_to_us(p.get("p2_sw1", 0))
        ch8 = self._sw2_to_us(p.get("p2_sw2", 0))
        ch9 = self._sw2_to_us(p.get("p1_sw2", 0))
        ch10 = self._sw2_to_us(p.get("p1_sw3", 0))
        ch11 = 1000
        ch12 = 1000

        return ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8, ch9, ch10, ch11, ch12

    def _handle_line(self, line):
        try:
            packet = json.loads(line)
            channels = self._packet_to_channels(packet)
            self.rc_sender.set_channels(*channels)

        except Exception as e:
            print(f"\r[{self.name}] Bad Pico JSON: {line}  {e}", flush=True)

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