#!/usr/bin/env python3
import threading
import socket
import subprocess
import signal
import time
from pymavlink import mavutil
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
# class

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
# class


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
# class


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
# class


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
                        f"\r"
                        f"[{self.name}] "
                        f"Packets resumed after "
                        f"{interval_ms:.1f} ms",
                        flush=True
                    )

                    warning_active = False

                if(False):
                    if latency_ms is None:
                        print(
                            f"\r"
                            f"[{self.name}] "
                            f"Interval: {interval_ms:.1f} ms  "
                            f"Len: {len(text)}",
                            flush=True
                        )

                    else:
                        print(
                            f"\r"
                            f"[{self.name}] "
                            f"Interval: {interval_ms:.1f} ms  "
                            f"Latency: {latency_ms:.1f} ms  "
                            f"Len: {len(text)}",
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
# class


class QgcMavlinkGateway:
    def __init__(
        self,
        name: str,
        downlink_in_port: int,
        qgc_register_port: int,
        qgc_out_port: int,
        uplink_out_port: int,
        auto_start: bool = True,
    ):
        self.name = name
        self.client_addr = None
        self.running = False
        self.thread = None

        self.down_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.down_sock.bind(("127.0.0.1", downlink_in_port))
        self.down_sock.settimeout(0.02)

        self.qgc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.qgc_sock.bind(("0.0.0.0", qgc_register_port))
        self.qgc_sock.settimeout(0.02)

        self.to_qgc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.to_air_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.qgc_out_port = qgc_out_port
        self.uplink_out_port = uplink_out_port

        self.qgc_mav = mavutil.mavlink.MAVLink(None)

        if auto_start:
            self.start()

    def start(self):
        if self.thread is not None:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        print(f"\r[{self.name}] QGC gateway running", flush=True)

        while self.running:
            # QGC -> GS
            # Used both for client registration and MAVLink uplink.
            try:
                data, addr = self.qgc_sock.recvfrom(4096)

                # Learn where to send downlink MAVLink back to.
                self.client_addr = (addr[0], self.qgc_out_port)

                # Registration packet only. Do NOT forward to flight controller.
                if data == b"HELLO_QGC":
                    print(
                        f"\r[{self.name}] Client registered: {self.client_addr}",
                        flush=True
                    )
                else:

                    if(False):
                        msg_type = "UNKNOWN"

                        for b in data:
                            m = self.qgc_mav.parse_char(bytes([b]))
                            if m is not None:
                                msg_type = m.get_type()
                                break

                        print(
                            f"\r"
                            f"[{self.name}] QGC uplink {len(data)} bytes "
                            f"from {addr}: {msg_type}",
                            flush=True
                        )
                    # if

                    # Real MAVLink uplink packet: forward toward air side.
                    self.to_air_sock.sendto(
                        data,
                        ("127.0.0.1", self.uplink_out_port)
                    )

            except socket.timeout:
                pass

            # Air -> GS -> QGC
            try:
                data, _ = self.down_sock.recvfrom(4096)

                if self.client_addr is not None:
                    # print("\rMavlink [" + str(len(data)) + "]")
                    self.qgc_sock.sendto(data, self.client_addr)

            except socket.timeout:
                pass
    
    def stop(self):
        self.running = False

# class


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

        print("\rConnecting mavlink")
        self.master = self.mavutil.mavlink_connection(self.serial_device, baud=self.baudrate,)
        # Wait for the heartbeat msg to find the system ID
        self.master.wait_heartbeat()
        print("\rMavlink connected")

        while self.running:
            msg = self.master.recv_msg()

            if msg is None:
                time.sleep(0.001)
                continue

            packet = msg.get_msgbuf()

            if packet:
                msg_type = msg.get_type()
                if True or msg_type == "PARAM_VALUE":
                    print("\rMavlink[" + (msg_type) + "]",flush=True)
                self.sock.sendto(
                    packet,
                    ("127.0.0.1", self.udp_port)
                )
# class
            
            
class UdpToSerial:
    def __init__(
        self,
        name: str,
        udp_port: int,
        serial_device: str,
        baudrate: int,
        auto_start: bool = True,
    ):
        import serial

        self.name = name
        self.udp_port = udp_port
        self.serial_device = serial_device
        self.baudrate = baudrate

        self.ser = serial.Serial(serial_device, baudrate, timeout=0)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", udp_port))
        self.sock.settimeout(0.02)

        self.running = False
        self.thread = None

        if auto_start:
            self.start()

    def start(self):
        if self.thread is not None:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.ser.close()

    def _run(self):
        print(f"\r[{self.name}] UDP {self.udp_port} -> {self.serial_device}", flush=True)

        while self.running:
            try:
                data, _ = self.sock.recvfrom(4096)
                self.ser.write(data)
            except socket.timeout:
                pass
# class


class PiCamVideoToUdp:
    def __init__(
        self,
        name: str,
        udp_port: int,
        width: int = 640,
        height: int = 480,
        framerate: int = 8,
        bitrate: int = 700000,
        mtu: int = 1200,
        auto_start: bool = True,
    ):
        self.name = name
        self.udp_port = udp_port
        self.width = width
        self.height = height
        self.framerate = framerate
        self.bitrate = bitrate
        self.mtu = mtu
        self.proc = None

        if auto_start:
            self.start()

    def start(self):
        if self.proc is not None:
            return

        print(
            f"\r[{self.name}] PiCam H264 RTP -> UDP 127.0.0.1:{self.udp_port}",
            flush=True
        )

        cmd = (
            f"rpicam-vid -t 0 --nopreview --low-latency "
            f"--codec h264 --inline "
            f"--width {self.width} --height {self.height} "
            f"--framerate {self.framerate} "
            f"--bitrate {self.bitrate} "
            f"--output - | "
            f"gst-launch-1.0 -q "
            f"fdsrc ! h264parse ! "
            f"rtph264pay config-interval=1 pt=96 mtu={self.mtu} ! "
            f"udpsink host=127.0.0.1 port={self.udp_port}"
        )

        self.proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            executable="/bin/bash",
        )

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
# class


class UdpRtpH264VideoDisplay:
    def __init__(
        self,
        name: str,
        port: int,
        width: int = 320,
        height: int = 180,
        auto_start: bool = True,
    ):
        self.name = name
        self.port = port
        self.width = width
        self.height = height
        self.proc = None

        if auto_start:
            self.start()

    def start(self):
        if self.proc is not None:
            return

        print(
            f"\r[{self.name}] Displaying RTP/H264 from UDP 127.0.0.1:{self.port}",
            flush=True
        )

        cmd = [
            "gst-launch-1.0", "-v",
            "udpsrc", f"address=127.0.0.1", f"port={self.port}",
            "!", "application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000",
            "!", "rtph264depay",
            "!", "h264parse",
            "!", "avdec_h264",
            "!", "videoscale",
            "!", f"video/x-raw,width={self.width},height={self.height}",
            "!", "videoconvert",
            "!", "autovideosink", "sync=false",
        ]

        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
# class


class UdpClientLearningRebroadcaster:
    def __init__(
        self,
        name: str,
        in_port: int,
        register_port: int,
        out_port: int = 14550,
        auto_start: bool = True,
    ):
        self.name = name
        self.in_port = in_port
        self.register_port = register_port
        self.out_port = out_port

        self.client_addr = None
        self.running = False
        self.thread = None

        self.in_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.in_sock.bind(("127.0.0.1", in_port))
        self.in_sock.settimeout(0.02)

        self.register_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.register_sock.bind(("0.0.0.0", register_port))
        self.register_sock.settimeout(0.02)

        self.out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if auto_start:
            self.start()

    def start(self):
        if self.thread is not None:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run(self):
        print(
            f"[{self.name}] Waiting for client on UDP {self.register_port}; "
            f"forwarding local {self.in_port} -> client:{self.out_port}",
            flush=True,
        )

        while self.running:
            try:
                _, addr = self.register_sock.recvfrom(1024)
                self.client_addr = (addr[0], self.out_port)
                print(f"[{self.name}] Client registered: {self.client_addr}", flush=True)
            except socket.timeout:
                pass

            try:
                data, _ = self.in_sock.recvfrom(4096)
                if self.client_addr is not None:
                    self.out_sock.sendto(data, self.client_addr)
            except socket.timeout:
                pass
# class
