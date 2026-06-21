#!/usr/bin/env python3

import signal
import subprocess


class PiCamVideoToUdp:
    def __init__(
        self,
        name="VIDEO",
        udp_port=9004,
        width=640,
        height=480,
        framerate=30,
        bitrate=2_000_000,
        mtu=1200,
        auto_start=True,
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
        cmd = [
            "bash",
            "-c",
            (
                f"rpicam-vid "
                f"-t 0 "
                f"--nopreview "
                f"--low-latency "
                f"--codec h264 "
                f"--intra 1 "
                f"--inline "
                f"--width {self.width} "
                f"--height {self.height} "
                f"--framerate {self.framerate} "
                f"--bitrate {self.bitrate} "
                f"-o - "
                f"| gst-launch-1.0 -q "
                f"fdsrc "
                f"! h264parse "
                f"! rtph264pay config-interval=1 pt=96 mtu={self.mtu} "
                f"! udpsink host=127.0.0.1 port={self.udp_port}"
            ),
        ]

        print(f"\r[{self.name}] PiCam -> UDP {self.udp_port}", flush=True)
        self.proc = subprocess.Popen(cmd)

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()


class UsbCameraVideoToUdp:
    def __init__(
        self,
        name="VIDEO",
        device="/dev/video0",
        udp_port=9004,
        width=640,
        height=480,
        framerate=30,
        bitrate=2_000_000,
        input_format="h264",   # "mjpeg", "h264", or "yuyv422"
        mtu=1200,
        auto_start=True,
    ):
        self.name = name
        self.device = device
        self.udp_port = udp_port
        self.width = width
        self.height = height
        self.framerate = framerate
        self.bitrate = bitrate
        self.input_format = input_format
        self.mtu = mtu
        self.proc = None

        if auto_start:
            self.start()

    def start(self):
        if self.input_format.lower() == "h264":
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "warning",
                "-f", "v4l2",
                "-input_format", "h264",
                "-video_size", f"{self.width}x{self.height}",
                "-framerate", str(self.framerate),
                "-i", self.device,
                "-an",
                "-c:v", "copy",
                "-f", "rtp",
                f"rtp://127.0.0.1:{self.udp_port}?pkt_size={self.mtu}",
            ]

        else:
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "warning",
                "-f", "v4l2",
                "-input_format", self.input_format,
                "-video_size", f"{self.width}x{self.height}",
                "-framerate", str(self.framerate),
                "-i", self.device,
                "-an",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-b:v", str(self.bitrate),
                "-g", "1",
                "-bf", "0",
                "-f", "rtp",
                f"rtp://127.0.0.1:{self.udp_port}?pkt_size={self.mtu}",
            ]

        print(
            f"\r[{self.name}] USB camera {self.device} "
            f"{self.input_format} -> UDP {self.udp_port}",
            flush=True,
        )

        self.proc = subprocess.Popen(cmd)

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()


class UdpRtpH264VideoDisplay:
    def __init__(
        self,
        name="VIDEO",
        port=9004,
        width=640,
        height=480,
        auto_start=True,
    ):
        self.name = name
        self.port = port
        self.width = width
        self.height = height
        self.proc = None

        if auto_start:
            self.start()

    def start(self):
        cmd = [
            "gst-launch-1.0",
            "-v",
            "udpsrc",
            "address=127.0.0.1",
            f"port={self.port}",
            "!",
            "application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000",
            "!",
            "rtph264depay",
            "!",
            "h264parse",
            "!",
            "queue",
            "max-size-buffers=1",
            "leaky=downstream",
            "!",
            "avdec_h264",
            "!",
            "videoscale",
            "!",
            f"video/x-raw,width={self.width},height={self.height}",
            "!",
            "videoconvert",
            "!",
            "autovideosink",
            "sync=false",
        ]

        print(f"\r[{self.name}] Display UDP {self.port}", flush=True)
        self.proc = subprocess.Popen(cmd)

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()