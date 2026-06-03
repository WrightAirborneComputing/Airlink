#!/usr/bin/env python3
import subprocess
from dataclasses import dataclass
import time

from process_lib import (
    ProcessRunner,
)

@dataclass
class WfbConfig:
    iface: str = "wlan1"
    channel: str = "1"
    tx_key: str = "/etc/wfb/drone.key"
    rx_key: str = "/etc/wfb/gs.key"
    radio_port: str = "0"
    udp_port: int = 9000

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

    def start(
        self,
        suppress_output=True,
        line_callback=None,
        name=None,
    ):
        return self.runner.start(
            [
                "sudo",
                "wfb_rx",
                "-K",
                self.config.rx_key,
                "-u",
                str(self.config.udp_port),
                "-p",
                self.config.radio_port,
                self.config.iface,
            ],
            suppress_output=suppress_output,
            line_callback=line_callback,
            name=name,
        )
# class

class WfbInstrumentationParser:
    def __init__(
        self,
        name,
        print_every_sec=1.0,
    ):
        self.name = name
        self.print_every_sec = print_every_sec
        self.last_print = 0.0

        self.last_rx = None
        self.last_pkt = None
        self.last_tx = None

    def handle_line(self, line):
        #
        # WFB can emit oddly spaced/indented lines.
        #
        line = line.strip()
        if not line:
            return

        parts = line.split()

        if len(parts) < 2:
            return

        timestamp = parts[0]
        kind = parts[1]

        if kind == "RX_ANT":
            self.last_rx = self._parse_rx_ant(timestamp, parts)

        elif kind == "TX_ANT":
            self.last_tx = line

        elif kind == "PKT":
            self.last_pkt = self._parse_pkt(timestamp, parts)

        self._maybe_print()

    def _parse_rx_ant(self, timestamp, parts):
        #
        # Example:
        # 1002202 RX_ANT 2412:0:20 0 34:-18:-16:-16:0:0:0
        #
        result = {
            "timestamp": timestamp,
            "raw": " ".join(parts),
        }

        try:
            result["freq_info"] = parts[2]
            result["antenna"] = parts[3]

            vals = parts[4].split(":")

            result["count"] = int(vals[0])
            result["rssi"] = [
                int(v)
                for v in vals[1:4]
            ]

        except Exception:
            result["parse_error"] = True

        return result

    def _parse_pkt(self, timestamp, parts):
        #
        # Keep raw plus integer fields. WFB PKT format varies by version.
        #
        result = {
            "timestamp": timestamp,
            "raw": " ".join(parts),
        }

        try:
            result["values"] = [
                int(v)
                for v in parts[2].split(":")
            ]

        except Exception:
            result["parse_error"] = True

        return result

    def _maybe_print(self):
        now = time.time()

        if now - self.last_print < self.print_every_sec:
            return

        self.last_print = now

        msg = f"[{self.name}]"

        if self.last_rx is not None:
            rx = self.last_rx

            if "parse_error" in rx:
                msg += f" RX raw={rx['raw']}"

            else:
                if(False):
                    msg += (
                        f" RX freq={rx['freq_info']} "
                        f"ant={rx['antenna']} "
                        f"count={rx['count']} "
                        f"rssi={rx['rssi']}"
                    )
                # if

        if self.last_pkt is not None:
            pkt = self.last_pkt

            if "parse_error" in pkt:
                msg += f" PKT raw={pkt['raw']}"
            else:
                pass # msg += f" PKT={pkt['values']}"

        # print("\r" + msg, flush=True)
# class