#!/usr/bin/env python3
import subprocess
from dataclasses import dataclass

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

    def start(self, suppress_output=True):
        return self.runner.start([
            "sudo", "wfb_rx",
            "-K", self.config.rx_key,
            "-u", str(self.config.udp_port),
            "-p", self.config.radio_port,
            self.config.iface
        ], suppress_output=suppress_output)
# class
