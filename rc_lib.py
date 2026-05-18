#!/usr/bin/env python3

import socket
import threading
import time


class RcPacketSender:

    def __init__(
        self,
        name: str,
        port: int,
        interval_sec: float = 0.05,
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

        self.frame_count = 0

        self.channels = [
            1500,
            1500,
            1000,
            1500,
            1000,
            1000,
            1000,
            1000,
        ]

        if auto_start:
            self.start()

    def set_channels(
        self,
        ch1,
        ch2,
        ch3,
        ch4,
        ch5,
        ch6,
        ch7,
        ch8,
    ):
        values = [
            ch1,
            ch2,
            ch3,
            ch4,
            ch5,
            ch6,
            ch7,
            ch8,
        ]

        self.channels = [
            max(1000, min(2000, int(v)))
            for v in values
        ]

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

    def _run(self):

        print(
            f"\r"
            f"[{self.name}] RC sender -> UDP {self.port}",
            flush=True,
        )

        while self.running:

            tx_time = time.time()

            payload = (
                f"{self.frame_count} "
                f"{tx_time:.6f} "
                + " ".join(str(v) for v in self.channels)
            )

            self.sock.sendto(
                payload.encode("ascii"),
                ("127.0.0.1", self.port)
            )

            self.frame_count += 1

            time.sleep(self.interval_sec)


class RcPacketReceiver:

    def __init__(
        self,
        name: str,
        in_port: int,
        ack_port: int,
        channel_callback=None,
        auto_start: bool = True,
    ):
        self.name = name
        self.in_port = in_port
        self.ack_port = ack_port

        self.channel_callback = channel_callback

        self.running = False
        self.thread = None

        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        self.sock.bind(("127.0.0.1", in_port))
        self.sock.settimeout(0.02)

        self.ack_sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        self.channels = [1500] * 8
        self.frame_count = -1

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

    def _run(self):

        print(
            f"\r"
            f"[{self.name}] RC receiver UDP {self.in_port}",
            flush=True,
        )

        while self.running:

            try:
                data, _ = self.sock.recvfrom(4096)

                rx_time = time.time()

                text = data.decode("ascii").strip()

                fields = text.split()

                if len(fields) != 10:
                    continue

                frame_count = int(fields[0])
                tx_time = float(fields[1])

                channels = [
                    int(v)
                    for v in fields[2:]
                ]

                self.frame_count = frame_count
                self.channels = channels

                #
                # IMPORTANT:
                # Do NOT allow callback exceptions
                # to kill the receive thread.
                #
                if self.channel_callback is not None:
                    try:
                        self.channel_callback(
                            *self.channels
                        )
                    except Exception as e:
                        print(
                            f"\r"
                            f"[{self.name}] "
                            f"channel_callback exception: {e}",
                            flush=True,
                        )

                latency_ms = (
                    rx_time - tx_time
                ) * 1000.0

                print(
                    f"\r"
                    f"[{self.name}] "
                    f"frame={frame_count} "
                    f"latency={latency_ms:.1f} ms "
                    f"ch={self.channels}",
                    flush=True,
                )

                ack = (
                    f"{frame_count} "
                    f"{tx_time:.6f} "
                    f"{rx_time:.6f}"
                )

                self.ack_sock.sendto(
                    ack.encode("ascii"),
                    ("127.0.0.1", self.ack_port)
                )

            except socket.timeout:
                pass

            except Exception as e:
                print(
                    f"\r"
                    f"[{self.name}] "
                    f"receiver exception: {e}",
                    flush=True,
                )


class RcAckReceiver:

    def __init__(
        self,
        name: str,
        port: int,
        auto_start: bool = True,
    ):
        self.name = name
        self.port = port

        self.running = False
        self.thread = None

        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        self.sock.bind(("127.0.0.1", port))
        self.sock.settimeout(0.02)

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

    def _run(self):

        print(
            f"\r"
            f"[{self.name}] ACK receiver UDP {self.port}",
            flush=True,
        )

        while self.running:

            try:
                data, _ = self.sock.recvfrom(4096)

                now = time.time()

                text = data.decode("ascii").strip()

                fields = text.split()

                if len(fields) != 3:
                    continue

                frame_count = int(fields[0])
                tx_time = float(fields[1])
                air_rx_time = float(fields[2])

                uplink_ms = (
                    air_rx_time - tx_time
                ) * 1000.0

                downlink_ms = (
                    now - air_rx_time
                ) * 1000.0

                total_latency_ms = (
                    now - tx_time
                ) * 1000.0

                print(
                    f"\r"
                    f"[{self.name}] "
                    f"frame={frame_count} "
                    f"up={uplink_ms:.1f} ms "
                    f"down={downlink_ms:.1f} ms "
                    f"total={total_latency_ms:.1f} ms",
                    flush=True,
                )

            except socket.timeout:
                pass

            except Exception as e:
                print(
                    f"\r"
                    f"[{self.name}] "
                    f"ack exception: {e}",
                    flush=True,
                )
