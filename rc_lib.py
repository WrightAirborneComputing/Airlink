#!/usr/bin/env python3

import socket
import threading
import time


class RcPacketSender:
    def __init__(
        self,
        name: str,
        port: int,
        interval_sec: float = 0.02,
        auto_start: bool = True,
    ):
        self.name = name
        self.port = port
        self.interval_sec = interval_sec

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        self.frame_count = 0

        self.channels = [
            1500, 1500, 1500, 1500,
            1000, 1000, 1000, 1000,
            1000, 1000, 1000, 1000,
        ]

        if auto_start:
            self.start()

    def set_channels(
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
        print(f"\r[{self.name}] RC sender -> UDP {self.port}", flush=True)

        while self.running:
            tx_time = time.time()

            with self.lock:
                channels = list(self.channels)

            payload = (
                f"{self.frame_count} "
                f"{tx_time:.6f} "
                + " ".join(str(v) for v in channels)
            )

            self.sock.sendto(
                payload.encode("ascii"),
                ("127.0.0.1", self.port),
            )

            self.frame_count += 1
            time.sleep(self.interval_sec)


class RcPacketReceiver:
    def __init__(
        self,
        name: str,
        in_port: int,
        ack_port: int,
        led=None,
        channel_callback=None,
        latency_warn_ms: float = 250.0,
        print_every_sec: float = 1.0,
        auto_start: bool = True,
    ):
        self.name = name
        self.in_port = in_port
        self.ack_port = ack_port
        self.led = led
        self.channel_callback = channel_callback

        self.latency_warn_ms = latency_warn_ms
        self.print_every_sec = print_every_sec

        self.running = False
        self.thread = None

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        self.sock.bind(("127.0.0.1", in_port))
        self.sock.setblocking(False)

        self.ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.channels = [1500] * 12
        self.frame_count = -1

        self.last_frame = None
        self.rx_count = 0
        self.lost_count = 0
        self.dropped_stale = 0
        self.late_count = 0

        self.last_print_time = time.time()
        self.max_latency_ms = 0.0

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

    def _recv_latest(self):
        latest = None
        drained = 0

        while True:
            try:
                latest = self.sock.recvfrom(4096)
                drained += 1
            except BlockingIOError:
                break
            except socket.error:
                break

        if drained > 1:
            self.dropped_stale += drained - 1

        return latest

    def _maybe_print_summary(self):
        now = time.time()

        if now - self.last_print_time < self.print_every_sec:
            return

        self.last_print_time = now

        total_seen = self.rx_count + self.lost_count

        loss_pct = 0.0
        if total_seen > 0:
            loss_pct = 100.0 * self.lost_count / total_seen

        late_pct = 0.0
        if self.rx_count > 0:
            late_pct = 100.0 * self.late_count / self.rx_count

        print(
            f"\r[{self.name}] "
            f"rx={self.rx_count} "
            f"lost={self.lost_count} "
            f"loss={loss_pct:.1f}% "
            f"stale_drop={self.dropped_stale} "
            f"late>{self.latency_warn_ms:.0f}ms="
            f"{self.late_count} ({late_pct:.1f}%) "
            f"max_latency={self.max_latency_ms:.1f} ms",
            flush=True,
        )

        self.max_latency_ms = 0.0

    def _run(self):
        print(
            f"\r[{self.name}] RC receiver UDP {self.in_port}",
            flush=True,
        )

        while self.running:
            latest = self._recv_latest()

            if latest is None:
                self._maybe_print_summary()
                time.sleep(0.002)
                continue

            data, _ = latest
            rx_time = time.time()

            try:
                text = data.decode("ascii").strip()
                fields = text.split()

                if len(fields) != 14:
                    print(
                        f"\r[{self.name}] Bad RC packet field count: "
                        f"{len(fields)} text={text}",
                        flush=True,
                    )
                    continue

                frame_count = int(fields[0])
                tx_time = float(fields[1])
                channels = [int(v) for v in fields[2:]]

                if self.last_frame is not None:
                    expected = self.last_frame + 1

                    if frame_count > expected:
                        self.lost_count += frame_count - expected

                    elif frame_count <= self.last_frame:
                        continue

                self.last_frame = frame_count
                self.rx_count += 1

                latency_ms = (rx_time - tx_time) * 1000.0
                self.max_latency_ms = max(
                    self.max_latency_ms,
                    latency_ms,
                )

                if latency_ms > self.latency_warn_ms:
                    self.late_count += 1

                self.frame_count = frame_count
                self.channels = channels

                if self.led is not None:
                    self.led.activity()

                if self.channel_callback is not None:
                    try:
                        self.channel_callback(*self.channels)
                    except Exception as e:
                        print(
                            f"\r[{self.name}] "
                            f"channel_callback exception: {e}",
                            flush=True,
                        )

                ack = f"{frame_count} {tx_time:.6f} {rx_time:.6f}"

                self.ack_sock.sendto(
                    ack.encode("ascii"),
                    ("127.0.0.1", self.ack_port),
                )

                self._maybe_print_summary()

            except Exception as e:
                print(
                    f"\r[{self.name}] receiver exception: {e}",
                    flush=True,
                )


class RcAckReceiver:
    def __init__(
        self,
        name: str,
        port: int,
        led=None,
        latency_warn_sec: float = 0.25,
        print_every_sec: float = 1.0,
        auto_start: bool = True,
    ):
        self.name = name
        self.port = port
        self.led = led

        self.latency_warn_sec = latency_warn_sec
        self.print_every_sec = print_every_sec

        self.running = False
        self.thread = None

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        self.sock.bind(("127.0.0.1", port))
        self.sock.setblocking(False)

        self.last_frame = None

        self.rx_count = 0
        self.lost_count = 0
        self.stale_drop_count = 0
        self.late_count = 0

        self.last_print_time = time.time()
        self.last_ack_time = time.time()

        self.max_total_ms = 0.0

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

    def _recv_latest(self):
        latest = None
        drained = 0

        while True:
            try:
                latest = self.sock.recvfrom(4096)
                drained += 1
            except BlockingIOError:
                break
            except socket.error:
                break

        if drained > 1:
            self.stale_drop_count += drained - 1

        return latest

    def _handle_ack(self, frame_count, tx_time, now):
        if self.last_frame is not None:
            expected = self.last_frame + 1

            if frame_count > expected:
                self.lost_count += frame_count - expected

            elif frame_count <= self.last_frame:
                return

        self.last_frame = frame_count
        self.rx_count += 1
        self.last_ack_time = now

        if self.led is not None:
            self.led.activity()

        total_ms = (now - tx_time) * 1000.0
        self.max_total_ms = max(self.max_total_ms, total_ms)

        if total_ms > self.latency_warn_sec * 1000.0:
            self.late_count += 1
            print(
                f"\r[{self.name}] LATE frame={frame_count} "
                f"total={total_ms:.1f} ms",
                flush=True,
            )

        self._maybe_print_summary(now)

    def _maybe_print_summary(self, now):
        if now - self.last_print_time < self.print_every_sec:
            return

        self.last_print_time = now

        total_seen = self.rx_count + self.lost_count

        loss_pct = 0.0
        if total_seen > 0:
            loss_pct = 100.0 * self.lost_count / total_seen

        late_pct = 0.0
        if self.rx_count > 0:
            late_pct = 100.0 * self.late_count / self.rx_count

        age_ms = (now - self.last_ack_time) * 1000.0

        print(
            f"\r[{self.name}] "
            f"rx={self.rx_count} "
            f"lost={self.lost_count} "
            f"loss={loss_pct:.1f}% "
            f"stale_drop={self.stale_drop_count} "
            f"late>{self.latency_warn_sec * 1000:.0f}ms="
            f"{self.late_count} ({late_pct:.1f}%) "
            f"max_total={self.max_total_ms:.1f} ms "
            f"last_age={age_ms:.0f} ms",
            flush=True,
        )

        self.max_total_ms = 0.0

    def _run(self):
        print(f"\r[{self.name}] ACK receiver UDP {self.port}", flush=True)

        while self.running:
            latest = self._recv_latest()
            now = time.time()

            if latest is None:
                if now - self.last_ack_time > self.latency_warn_sec:
                    self._maybe_print_summary(now)

                time.sleep(0.002)
                continue

            data, _ = latest

            try:
                text = data.decode("ascii").strip()
                fields = text.split()

                if len(fields) != 3:
                    continue

                frame_count = int(fields[0])
                tx_time = float(fields[1])

                self._handle_ack(frame_count, tx_time, now)

            except Exception as e:
                print(f"\r[{self.name}] ack exception: {e}", flush=True)