#!/usr/bin/env python3

from wfb_common import (
    WfbConfig,
    WifiRadioSetup,
    ProcessRunner,
    WfbRx,
    UdpTestReceiver,
)

config = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/gs.key",
    udp_port=9000,
    radio_port="0",
)

runner = ProcessRunner()

try:
    # Ensure interface is configured every run
    WifiRadioSetup(config).run()

    # Start WFB RX
    WfbRx(config, runner).start(suppress_output=True)

    # Start packet receiver
    UdpTestReceiver(
        port=config.udp_port,
        timeout_sec=0.250
    ).run_forever()

except KeyboardInterrupt:
    print("stopping")

finally:
    runner.stop_all()