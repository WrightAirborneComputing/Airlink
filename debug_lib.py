import os
import socket
import platform


def print_banner(
    name,
    udp_ports=None,
    serial_ports=None,
    gpios=None,
    radio_ports=None,
):
    print("\r")
    print("=" * 70)
    print(f"\r{name}")
    print("=" * 70)

    print(f"\rPID        : {os.getpid()}")
    print(f"\rHostname   : {socket.gethostname()}")
    print(f"\rPython     : {platform.python_version()}")

    if udp_ports:
        print(f"\rUDP Ports  : {udp_ports}")

    if serial_ports:
        print(f"\rSerial     : {serial_ports}")

    if gpios:
        print(f"\rGPIOs      : {gpios}")

    if radio_ports:
        print(f"\rRadioPorts : {radio_ports}")

    print("=" * 70)
    print(flush=True)

    import subprocess
# def

def print_competing_processes():
    print("\rExisting processes:\r")

    subprocess.run(
        [
            "bash",
            "-c",
            (
                "ps aux | egrep "
                "'airlink|python|wfb_|pigpiod|rpicam|gst-launch'"
            )
        ]
    )

    print("\r")

# def