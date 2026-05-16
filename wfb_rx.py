#!/home/pi/mavenv/bin/python

import time

from wfb_common import (
    WfbConfig,
    WifiRadioSetup,
    ProcessRunner,
    WfbRx,
    UdpTestReceiver,
    UdpRtpH264VideoDisplay,
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

testRx = None
mavlinkRx = None
videoRx = None

try:
    WifiRadioSetup(testReceiver).run()

    WfbRx(testReceiver, runner).start(suppress_output=True)
    WfbRx(mavlinkReceiver, runner).start(suppress_output=True)
    WfbRx(videoReceiver, runner).start(suppress_output=True)

    testRx = UdpTestReceiver(
        name="TEST",
        port=testReceiver.udp_port,
    )

    mavlinkRx = UdpTestReceiver(
        name="MAVLINK",
        port=mavlinkReceiver.udp_port,
    )

    videoRx = UdpRtpH264VideoDisplay(
        name="VIDEO",
        port=videoReceiver.udp_port,
        width=320,
        height=180,
    )

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("stopping")

finally:
    if testRx is not None:
        testRx.stop()

    if mavlinkRx is not None:
        mavlinkRx.stop()

    if videoRx is not None:
        videoRx.stop()

    runner.stop_all()