#!/usr/bin/env python3

import socket
import threading
import time

class RcPacketSender:
    def __init__(
        self,
        name: str,
        port: int,
        interval_sec: float = 0.04,
        auto_start: bool = True,
    ):
        self.name = name
        self.port = port
        self.interval_sec = interval_sec
        self.enabled = True

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
        # if
    # def

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
    # def

    def set_enabled(self, enabled: bool):
        enabled = bool(enabled)
        if enabled != self.enabled:
            self.enabled = enabled
            state = "ENABLED" if enabled else "DISABLED"
            print(f"\r[{self.name}] TX {state}",flush=True,)
        # if
    # def

    def is_enabled(self):
        return self.enabled
    # def

    def start(self):
        if self.thread is not None:
            return
        # if

        self.running = True
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self.thread.start()
    # def

    def stop(self):
        self.running = False
    # def

    def _run(self):
        print(
            f"\r[{self.name}] RC sender -> UDP {self.port} "
            f"period={self.interval_sec:.3f}s "
            f"rate={1.0 / self.interval_sec:.1f}Hz",
            flush=True,
        )

        last_send_time = None
        period_sum_ms = 0.0
        period_count = 0
        max_period_ms = 0.0
        last_print_time = time.time()

        while self.running:
            now = time.time()

            if last_send_time is not None:
                period_ms = (now - last_send_time) * 1000.0
                period_sum_ms += period_ms
                period_count += 1
                max_period_ms = max(max_period_ms, period_ms)
            # if

            last_send_time = now
            tx_time = now
            tx_enabled = True
            with self.lock:
                channels = list(self.channels)
                tx_enabled = channels[8] > 1500 # i.e. Channel-9
            # with

            payload = (
                f"{self.frame_count} "
                f"{tx_time:.6f} "
                + " ".join(str(v) for v in channels)
            )

            # Check if TX is enabled by switch
            self.set_enabled(tx_enabled)
            if self.enabled:
                self.sock.sendto(payload.encode("ascii"),("127.0.0.1", self.port),)
                self.frame_count += 1

                if now - last_print_time >= 1.0:
                    avg_period_ms = (
                        period_sum_ms / period_count
                        if period_count > 0
                        else 0.0
                    )

                    if(False):
                        print(
                            f"\r[{self.name}] "
                            f"tx={self.frame_count} "
                            f"avg_period={avg_period_ms:.1f} ms "
                            f"max_period={max_period_ms:.1f} ms",
                            flush=True,
                        )
                    # if

                    last_print_time = now
                    period_sum_ms = 0.0
                    period_count = 0
                    max_period_ms = 0.0
                # if
            # if

            sleep_time = self.interval_sec - (time.time() - now)
            if sleep_time > 0:
                time.sleep(sleep_time)
            # if
        # while
    # def


class RcPacketReceiver:
    def __init__(
        self,
        name: str,
        in_port: int,
        ack_port: int,
        led=None,
        rssi_led_bar=None,
        rssi_getter=None,
        channel_callback=None,
        rc_active_callback=None,
        rc_timeout_sec: float = 0.5,
        period_warn_ms: float = 250.0,
        print_every_sec: float = 1.0,
        auto_start: bool = True,
    ):
        self.name = name
        self.in_port = in_port
        self.ack_port = ack_port
        self.led = led
        self.rssi_led_bar = rssi_led_bar
        self.rssi_getter = rssi_getter
        self.channel_callback = channel_callback
        self.rc_active_callback = rc_active_callback

        self.rc_timeout_sec = rc_timeout_sec
        self.period_warn_ms = period_warn_ms
        self.print_every_sec = print_every_sec

        self.running = False
        self.thread = None

        self.rc_active = False
        self.last_packet_time = time.time()

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
        self.late_count = 0

        self.last_rx_time = None
        self.period_sum_ms = 0.0
        self.period_count = 0
        self.max_period_ms = 0.0
        self.max_frame_gap = 0

        self.last_print_time = time.time()

        if auto_start:
            self.start()
        # if
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
    # def

    def stop(self):
        self.running = False
        self._set_rc_active(False)
    # def

    def _set_rc_active(self, active: bool):
        if self.rc_active == active:
            return

        self.rc_active = active

        state = "ACTIVE" if active else "TIMEOUT"
        print(f"\r[{self.name}] RC {state}", flush=True)

        if self.rc_active_callback is not None:
            try:
                self.rc_active_callback(active)
            except Exception as e:
                print(
                    f"\r[{self.name}] rc_active_callback exception: {e}",
                    flush=True,
                )
    # def

    def _recv_latest(self):
        try:
            return self.sock.recvfrom(4096)
        except BlockingIOError:
            return None
        except socket.error:
            return None
    # def

    def _maybe_print_summary(self):
        rssi = None
        rssi_text = "Unknown"

        if self.rssi_getter is not None:
            try:
                rssi = self.rssi_getter()
                if rssi is not None:
                    rssi_text = f"{rssi}"
            except Exception:
                pass

        if self.rssi_led_bar is not None:
            self.rssi_led_bar.set_rssi(rssi)

        now = time.time()
        if now - self.last_print_time < self.print_every_sec:
            return

        self.last_print_time = now

        avg_period_ms = 0.0
        if self.period_count > 0:
            avg_period_ms = self.period_sum_ms / self.period_count

        print(
            f"\r[{self.name}] "
            f"rssi={rssi_text} "
            f"active={self.rc_active} "
            f"rx={self.rx_count} "
            f"lost={self.lost_count} "
            f"avg_period={avg_period_ms:.1f} ms "
            f"max_period={self.max_period_ms:.1f} ms "
            f"max_gap={self.max_frame_gap}",
            flush=True,
        )

        self.period_sum_ms = 0.0
        self.period_count = 0
        self.max_period_ms = 0.0
        self.max_frame_gap = 0
    # def

    def _run(self):
        print(
            f"\r[{self.name}] RC receiver UDP {self.in_port}",
            flush=True,
        )

        while self.running:
            latest = self._recv_latest()

            if latest is None:
                if time.time() - self.last_packet_time > self.rc_timeout_sec:
                    self._set_rc_active(False)

                self._maybe_print_summary()
                time.sleep(0.001)
                continue

            data, _ = latest
            rx_time = time.time()

            if self.last_rx_time is not None:
                period_ms = (rx_time - self.last_rx_time) * 1000.0
                self.period_sum_ms += period_ms
                self.period_count += 1
                self.max_period_ms = max(self.max_period_ms, period_ms)

                if period_ms > self.period_warn_ms:
                    self.late_count += 1

            self.last_rx_time = rx_time

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
                    frame_gap = frame_count - self.last_frame
                    self.max_frame_gap = max(self.max_frame_gap, frame_gap)

                    expected = self.last_frame + 1
                    lost = frame_count - expected

                    if lost > 0:
                        print(f"\rLost [{lost}]")
                        self.lost_count += lost

                    elif frame_count <= self.last_frame:
                        print(
                            f"\rBad frame count "
                            f"[{frame_count}/{self.last_frame}]"
                        )
                        self.last_frame = frame_count
                else:
                    self.max_frame_gap = max(self.max_frame_gap, 1)

                self.last_frame = frame_count
                self.rx_count += 1
                self.frame_count = frame_count
                self.channels = channels

                self.last_packet_time = rx_time
                self._set_rc_active(True)

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
    # def

# class

class RcAckReceiver:
    def __init__(
        self,
        name: str,
        port: int,
        led=None,
        rssi_led_bar = None,
        rssi_getter=None,
        latency_warn_sec: float = 0.25,
        print_every_sec: float = 1.0,
        auto_start: bool = True,
    ):
        self.name = name
        self.port = port
        self.led = led
        self.rssi_led_bar = rssi_led_bar
        self.rssi_getter = rssi_getter

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
        self.late_count = 0

        self.last_print_time = time.time()
        self.last_ack_time = time.time()

        self.max_total_ms = 0.0
        self.latency_sum_ms = 0.0
        self.latency_count = 0

        if auto_start:
            self.start()
        # if
    # def

    def start(self):
        if self.thread is not None:
            return
        # if

        self.running = True
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self.thread.start()
    # def

    def stop(self):
        self.running = False
    # def

    def _recv_latest(self):
        try:
            return self.sock.recvfrom(4096)
        except BlockingIOError:
            return None
        except socket.error:
            return None
    # def

    def _handle_ack(self, frame_count, tx_time, now):
        if self.last_frame is not None:
            expected = self.last_frame + 1
            lost = frame_count - expected

            if lost > 0:
                print(f"\rLost [{lost}]")
                self.lost_count += lost
            elif frame_count <= self.last_frame:
                print(f"\nWarning! Bad frame count [{frame_count}/{self.last_frame}]")
                self.last_frame = frame_count
            # if
        # if

        self.last_frame = frame_count
        self.rx_count += 1
        self.last_ack_time = now

        if self.led is not None:
            self.led.activity()
        # if

        total_ms = (now - tx_time) * 1000.0
        self.max_total_ms = max(self.max_total_ms,total_ms,)
        self.latency_sum_ms += total_ms
        self.latency_count += 1

        if total_ms > self.latency_warn_sec * 1000.0:
            self.late_count += 1
            print(f"\r[{self.name}] LATE frame={frame_count} "f"total={total_ms:.1f} ms",flush=True,)
        # if

        self._maybe_print_summary(now)
    # def

    def _maybe_print_summary(self, now):

        # Process RSSI
        rssi_text = f"Unknown"
        if self.rssi_getter is not None:
            try:
                rssi = self.rssi_getter()

                if rssi is not None:
                    rssi_text = f"{rssi}"
            except Exception:
                pass
            # try
        # if

        # Always refresh RSSI bar
        if self.rssi_led_bar is not None:
            self.rssi_led_bar.set_rssi(rssi)
        # if

        # Sometimes refresh text output
        if now - self.last_print_time < self.print_every_sec:
            return
        # if

        self.last_print_time = now
        total_seen = self.rx_count + self.lost_count
        avg_total_ms = 0.0
        if self.latency_count > 0:
            avg_total_ms = (self.latency_sum_ms /self.latency_count)
        # if

        print(
            f"\r[{self.name}] "
            f"rssi={rssi_text} "
            f"rx={self.rx_count} "
            f"lost={self.lost_count} "
            f"late>{self.latency_warn_sec * 1000:.0f}ms="
            f"{self.late_count} "
            f"avg_total={avg_total_ms:.1f} ms "
            f"max_total={self.max_total_ms:.1f} ms ",
            flush=True,
        )

        self.max_total_ms = 0.0
        self.latency_sum_ms = 0.0
        self.latency_count = 0
    # def

    def _run(self):
        print(f"\r[{self.name}] ACK receiver UDP {self.port}", flush=True)

        while self.running:
            latest = self._recv_latest()
            now = time.time()

            if latest is None:
                if now - self.last_ack_time > self.latency_warn_sec:
                    self._maybe_print_summary(now)

                time.sleep(0.001)
                continue
            # if

            data, _ = latest

            try:
                text = data.decode("ascii").strip()
                fields = text.split()

                if len(fields) != 3:
                    continue

                frame_count = int(fields[0])
                tx_time = float(fields[1])

                self._handle_ack(
                    frame_count,
                    tx_time,
                    now,
                )

            except Exception as e:
                print(f"\r[{self.name}] ack exception: {e}", flush=True)
            # try
        # while
    # def
