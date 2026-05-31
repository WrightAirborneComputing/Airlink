#!/usr/bin/env python3
import subprocess

class PiCamVideoToUdp:
    def __init__(
        self,
        name: str,
        udp_port: int,
        width: int = 320,
        height: int = 240,
        framerate: int = 5,
        bitrate: int = 300000,
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

        print(f"\r" f"\r[{self.name}] Displaying RTP/H264 from UDP 127.0.0.1:{self.port}", flush=True)

        cmd = [
            "gst-launch-1.0", "-v",

            "udpsrc", "address=127.0.0.1", f"port={self.port}",
                "!","application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000",
                "!","rtph264depay",
                "!","h264parse",
                "!","queue","max-size-buffers=1","leaky=downstream",
                "!","avdec_h264",
                "!",f"video/x-raw,width={self.width},height={self.height}",
                "!","videoconvert",
                "!","autovideosink","sync=false",
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
