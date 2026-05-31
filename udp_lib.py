#!/usr/bin/env python3
import threading
import socket
import subprocess
import time
from pymavlink import mavutil

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
        timeout_sec: float = 0.2,
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

        self.rx_count = 0
        self.overrun_count = 0

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
        print(f"\r[{self.name}] Listening on UDP 127.0.0.1:{self.port}")

        last_packet_time = time.time()
        warning_active = False

        while self.running:
            try:
                data, _ = self.sock.recvfrom(4096)
                self.rx_count += 1

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

                delay_ms = (now - last_packet_time) * 1000.0

                if ( (delay_ms >= self.timeout_sec * 1000.0) and (not warning_active) ):
                    self.overrun_count += 1
                    print(
                        f"\r"
                        f"[{self.name}] WARNING: "
                        f"No packet received for "
                        f"{delay_ms:.1f} ms",
                        f"{self.overrun_count:d}/{self.rx_count:d} overruns",
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
        led = None,
        auto_start: bool = True,
    ):
        self.name = name
        self.client_addr = None
        self.running = False
        self.thread = None
        self.led = led

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
    # def

    def get_client_ip(self):
        if self.client_addr is None:
            return None
        return self.client_addr[0]
    # def

    def _decode_mavlink_packet(self, data: bytes):
        msg_types = []

        print("\rDecoding [" + str(len(data)) + "]")
        for b in data:
            try:
                msg = self.mav.parse_char(bytes([b]))

                if msg is not None:
                    msg_types.append(msg.get_type())

            except Exception as e:
                msg_types.append(f"DECODE_ERROR:{e}")
                break

        return msg_types
    # def

    def start(self):
        if self.thread is not None:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    # def

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
                # print(f"\rGot [{len(data)}]",flush=True)
                self.led.activity()

                if self.client_addr is not None:
                    # self._decode_mavlink_packet(data)
                    self.qgc_sock.sendto(data, self.client_addr)

            except socket.timeout:
                pass
    # def
    
    def stop(self):
        self.running = False
    # def

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
                # print("\rMavlink[" + (msg_type) + "] to [" + str(self.udp_port) + "]",flush=True)
                self.sock.sendto(packet,("127.0.0.1", self.udp_port))
# class


class DynamicUdpForwarder:

    def __init__(self, name, in_port, get_out_host, out_port, auto_start=True):
        self.name = name
        self.in_port = in_port
        self.get_out_host = get_out_host
        self.out_port = out_port
        self.running = False
        self.thread = None

        self.in_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.in_sock.bind(("127.0.0.1", in_port))
        self.in_sock.settimeout(0.02)

        self.out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if auto_start:
            self.start()
    # def

    def start(self):
        if self.thread is not None:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    # def

    def stop(self):
        self.running = False
    # def

    def _run(self):
        print(
            f"\r"
            f"[{self.name}] Dynamic UDP forwarding "
            f"127.0.0.1:{self.in_port} -> client:{self.out_port}",
            flush=True,
        )

        while self.running:
            try:
                data, _ = self.in_sock.recvfrom(65535)

                out_host = self.get_out_host()
                if out_host is not None:
                    self.out_sock.sendto(data, (out_host, self.out_port))

            except socket.timeout:
                pass
            # try
    # def

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
    # def

    def start(self):
        if self.thread is not None:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    # def

    def stop(self):
        self.running = False
        self.ser.close()
    # def

    def _run(self):
        print(f"\r[{self.name}] UDP {self.udp_port} -> {self.serial_device}", flush=True)

        while self.running:
            try:
                data, _ = self.sock.recvfrom(4096)
                self.ser.write(data)
            except socket.timeout:
                pass
    # def
# class

