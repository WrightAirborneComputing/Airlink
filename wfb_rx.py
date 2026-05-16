#!/usr/bin/env python3

import time

from wfb_common import (
    WfbConfig,
    WifiRadioSetup,
    ProcessRunner,
    WfbRx,
    UdpTestReceiver,
)

runner = ProcessRunner()

testReceiver = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/gs.key",
    udp_port=9000,
    radio_port="0",
)

mavlinkReceiver = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/gs.key",
    udp_port=9001,
    radio_port="1",
)

videoReceiver = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/gs.key",
    udp_port=9002,
    radio_port="2",
)

try:
    WifiRadioSetup(testReceiver).run()

    WfbRx(testReceiver, runner).start(suppress_output=True)
    WfbRx(mavlinkReceiver, runner).start(suppress_output=True)
    WfbRx(videoReceiver, runner).start(suppress_output=True)

    testRx    = UdpTestReceiver(name="TEST", port=9000,)
    mavlinkRx = UdpTestReceiver(name="MAVLINK", port=9001,)
    videoRx   = UdpTestReceiver(name="VIDEO", port=9002,)

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("stopping")

finally:
    testRx.stop()
    mavlinkRx.stop()
    videoRx.stop()
    runner.stop_all()