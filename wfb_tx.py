#!/usr/bin/env python3

from wfb_common import (
    WfbConfig,
    WifiRadioSetup,
    ProcessRunner,
    WfbTx,
    UdpTestSender,
)

config = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/drone.key",
    udp_port=9000,
    radio_port="0",
)

runner = ProcessRunner()

try:
    # Ensure interface is configured every run
    WifiRadioSetup(config).run()

    # Start WFB TX
    WfbTx(config, runner).start(suppress_output=True)

    # Start packet generator
    UdpTestSender(
        port=config.udp_port,
        interval_sec=0.01
    ).run_forever()

except KeyboardInterrupt:
    print("stopping")

finally:
    runner.stop_all()