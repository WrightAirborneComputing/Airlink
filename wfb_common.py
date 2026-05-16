#!/usr/bin/env python3
import threading
import socket
import subprocess
import signal
import time
from dataclasses import dataclass


@dataclass
class WfbConfig:
    iface: str = "wlan1"
    channel: str = "1"
    tx_key: str = "/etc/wfb/drone.key"
    rx_key: str = "/etc/wfb/gs.key"
    radio_port: str = "0"
    udp_port: int = 9000


class ProcessRunner:
    def __init__(self):
        self.processes = []

    def start(self, args, suppress_output=False):
        stdout = subprocess.DEVNULL if suppress_output else None
        stderr = subprocess.DEVNULL if suppress_output else None
        proc = subprocess.Popen(args, stdout=stdout, stderr=stderr)
        self.processes.append(proc)
        return proc

    def stop_all(self):
        for proc in self.processes:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()


class WifiRadioSetup:
    def __init__(self, config: WfbConfig):
        self.config = config

    def run(self):
        iface = self.config.iface
        desired_channel = self.config.channel

        current_type = self._get_interface_type(iface)
        current_channel = self._get_interface_channel(iface)
        power_save = self._get_power_save(iface)

        already_ok = (
            current_type == "monitor" and
            current_channel == desired_channel and
            power_save == "off"
        )

        if already_ok:
            print(f"\r{iface} already configured correctly.")
            print(f"\r  type       : {current_type}")
            print(f"\r  channel    : {current_channel}")
            print(f"\r  power_save : {power_save}")
            return

        print(f"\r{iface} requires setup.")

        self._run(
            ["sudo", "pkill", "-f", f"wpa_supplicant.*{iface}"],
            check=False,
            quiet=True
        )

        self._run(
            ["sudo", "nmcli", "dev", "set", iface, "managed", "no"],
            check=False,
            quiet=True
        )

        self._run(["sudo", "ip", "link", "set", iface, "down"])
        self._run(["sudo", "iw", "dev", iface, "set", "type", "monitor"])
        self._run(["sudo", "ip", "link", "set", iface, "up"])
        self._run(["sudo", "iw", "dev", iface, "set", "channel", desired_channel])

        self._run(
            ["sudo", "iw", "dev", iface, "set", "power_save", "off"],
            check=False
        )

        print("\nFinal interface state:")
        self._run(["iw", "dev", iface, "info"])
        self._run(["iw", "dev", iface, "get", "power_save"], check=False)

    def _run(self, args, check=True, quiet=False):
        if not quiet:
            print(">>>", " ".join(args))

        stdout = subprocess.DEVNULL if quiet else subprocess.PIPE
        stderr = subprocess.DEVNULL if quiet else subprocess.PIPE

        result = subprocess.run(
            args,
            check=check,
            stdout=stdout,
            stderr=stderr,
            text=True
        )

        if not quiet:
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:
                print(result.stderr.strip())

        return result

    def _get_interface_type(self, iface):
        try:
            result = subprocess.run(
                ["iw", "dev", iface, "info"],
                capture_output=True,
                text=True,
                check=True
            )

            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("type "):
                    return line.split()[1]

        except Exception:
            pass

        return None

    def _get_interface_channel(self, iface):
        try:
            result = subprocess.run(
                ["iw", "dev", iface, "info"],
                capture_output=True,
                text=True,
                check=True
            )

            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("channel "):
                    return line.split()[1]

        except Exception:
            pass

        return None

    def _get_power_save(self, iface):
        try:
            result = subprocess.run(
                ["iw", "dev", iface, "get", "power_save"],
                capture_output=True,
                text=True,
                check=True
            )

            for line in result.stdout.splitlines():
                line = line.strip().lower()

                if "power save:" in line:
                    return line.split(":")[1].strip()

        except Exception:
            pass

        return None

class WfbTx:
    def __init__(self, config: WfbConfig, runner: ProcessRunner):
        self.config = config
        self.runner = runner

    def start(self, suppress_output=True):
        return self.runner.start([
            "sudo", "wfb_tx",
            "-K", self.config.tx_key,
            "-u", str(self.config.udp_port),
            "-p", self.config.radio_port,
            self.config.iface
        ], suppress_output=suppress_output)


class WfbRx:
    def __init__(self, config: WfbConfig, runner: ProcessRunner):
        self.config = config
        self.runner = runner

    def start(self, suppress_output=True):
        return self.runner.start([
            "sudo", "wfb_rx",
            "-K", self.config.rx_key,
            "-u", str(self.config.udp_port),
            "-p", self.config.radio_port,
            self.config.iface
        ], suppress_output=suppress_output)


class UdpTestSender:
    def __init__(
        self,
        name: str,
        port: int,
        interval_sec: float = 0.1,
        auto_start: bool = True,
    ):
        self.name = name
        self.port = port
        self.interval_sec = interval_sec

        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        self.running = False
        self.thread = None

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

    def join(self, timeout=None):
        if self.thread is not None:
            self.thread.join(timeout)

    def _run(self):
        i = 0

        print(
            f"\r"
            f"[{self.name}] "
            f"Sending to UDP {self.port}"
        )

        while self.running:
            msg = (
                f"{time.time():.6f} "
                f"{self.name} "
                f"PACKET "
                f"{i:06d}\r\n"
            )

            self.sock.sendto(
                msg.encode("ascii"),
                ("127.0.0.1", self.port)
            )

            i += 1

            time.sleep(self.interval_sec)


class UdpTestReceiver:
    def __init__(
        self,
        name: str,
        port: int,
        timeout_sec: float = 0.250,
        auto_start: bool = True,
    ):
        self.name = name
        self.port = port
        self.timeout_sec = timeout_sec

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_RCVBUF,
            65536
        )

        self.sock.bind(("127.0.0.1", port))
        self.sock.settimeout(timeout_sec)

        self.running = False
        self.thread = None

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

    def join(self, timeout=None):
        if self.thread is not None:
            self.thread.join(timeout)

    def _run(self):
        print(f"[{self.name}] Listening on UDP 127.0.0.1:{self.port}")

        last_packet_time = time.time()
        warning_active = False

        while self.running:
            try:
                data, _ = self.sock.recvfrom(4096)

                now = time.time()

                interval_ms = (
                    now - last_packet_time
                ) * 1000.0

                last_packet_time = now

                text = data.decode(
                    "ascii",
                    errors="replace"
                ).strip()

                latency_ms = None

                try:
                    tx_time = float(text.split()[0])

                    latency_ms = (
                        now - tx_time
                    ) * 1000.0

                except Exception:
                    pass

                if warning_active:
                    print(
                        f"[{self.name}] "
                        f"Packets resumed after "
                        f"{interval_ms:.1f} ms",
                        flush=True
                    )

                    warning_active = False

                if latency_ms is None:
                    print(
                        f"\r"
                        f"[{self.name}] "
                        f"Interval: {interval_ms:.1f} ms  "
                        f"{text}",
                        flush=True
                    )

                else:
                    print(
                        f"\r"
                        f"[{self.name}] "
                        f"Interval: {interval_ms:.1f} ms  "
                        f"Latency: {latency_ms:.1f} ms  "
                        f"{text}",
                        flush=True
                    )

            except socket.timeout:
                now = time.time()

                delay_ms = (
                    now - last_packet_time
                ) * 1000.0

                if (
                    delay_ms >=
                    self.timeout_sec * 1000.0
                    and not warning_active
                ):
                    print(
                        f"\r"
                        f"[{self.name}] WARNING: "
                        f"No packet received for "
                        f"{delay_ms:.1f} ms",
                        flush=True
                    )

                    warning_active = True


class MavlinkSerialToUdp:

    def __init__(
        self,
        name: str,
        serial_device: str,
        baudrate: int,
        udp_port: int,
        auto_start: bool = True,
    ):
        from pymavlink import mavutil

        self.name = name
        self.serial_device = serial_device
        self.baudrate = baudrate
        self.udp_port = udp_port
        self.mavutil = mavutil

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = False
        self.thread = None
        self.master = None

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

        if self.master is not None:
            try:
                self.master.close()
            except Exception:
                pass

    def join(self, timeout=None):
        if self.thread is not None:
            self.thread.join(timeout)

    def _run(self):
        print(
            f"\r"
            f"[{self.name}] Serial MAVLink "
            f"{self.serial_device}@{self.baudrate} "
            f"-> UDP 127.0.0.1:{self.udp_port}",
            flush=True
        )

        print("\r Connecting mavlink")
        self.master = self.mavutil.mavlink_connection(
            self.serial_device,
            baud=self.baudrate,
        )
        # Wait for the heartbeat msg to find the system ID
        print("\rWaiting for heartbeat")
        self.master.wait_heartbeat()
        print("\nHeartbeat System=" + str(self.master.target_system) + " Component=" + str(self.master.target_component) )
        print("\r Connected mavlink")

        while self.running:
            msg = self.master.recv_msg()

            if msg is None:
                time.sleep(0.001)
                continue

            packet = msg.get_msgbuf()

            if packet:
                self.sock.sendto(
                    packet,
                    ("127.0.0.1", self.udp_port)
                )
