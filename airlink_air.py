#!/home/pi/mavenv/bin/python

# Test path:
# Air test -> WFB p0 -> GS UDP 9000
#
# MAVLink downlink path:
# Air serial -> UDP 9001 -> WFB p1 -> GS UDP 9001 -> QGC 14550
#
# MAVLink uplink path:
# QGC 14555 -> GS UDP 9002 -> WFB p3 -> Air UDP 9002 -> serial
#
# Video path:
# Air PiCam -> UDP 9003 -> WFB p2 -> GS UDP 9003 -> GStreamer display

import time

from process_lib import (
    ProcessRunner,
)

from wfb_lib import (
    WfbConfig,
    WifiRadioSetup,
    WfbTx,
    WfbRx
)

from udp_lib import (
    UdpTestSender,
    MavlinkSerialToUdp,
    UdpToSerial
)

from video_lib import (
    PiCamVideoToUdp
)

from crsf_lib import (
    CrsfRcOutput
)

runner = ProcessRunner()

testSender = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/drone.key",
    udp_port=9000,
    radio_port="0",
)

mavlinkSender = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/drone.key",
    udp_port=9001,
    radio_port="1",
)

mavlinkReceiver = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/drone.key",
    udp_port=9002,
    radio_port="2",
)

videoSender = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/drone.key",
    udp_port=9003,
    radio_port="3",
)

testTx = None
mavlinkTx = None
mavlinkRx = None
videoTx = None

try:
    WifiRadioSetup(testSender).run()

    # WFB transmit channels
    WfbTx(testSender, runner).start(suppress_output=True)
    WfbTx(mavlinkSender, runner).start(suppress_output=True)
    WfbRx(mavlinkReceiver, runner).start(suppress_output=True)
    WfbTx(videoSender, runner).start(suppress_output=True)

    # TEST generator
    testTx = UdpTestSender(
        name="TEST",
        port=testSender.udp_port,
        interval_sec=0.02,
    )

    # MAVLink downlink: FC serial -> local UDP 9001
    mavlinkTx = MavlinkSerialToUdp(
        name="MAVLINK-DN",
        serial_device="/dev/serial0",
        baudrate=115200,
        udp_port=mavlinkSender.udp_port,
    )

    # MAVLink uplink: local UDP 9002 -> FC serial
    mavlinkRx = UdpToSerial(
        name="MAVLINK-UP",
        udp_port=mavlinkReceiver.udp_port,
        serial_device="/dev/serial0",
        baudrate=115200,
    )

    # VIDEO downlink: PiCam -> local UDP 9003
    videoTx = PiCamVideoToUdp(
        name="VIDEO",
        udp_port=videoSender.udp_port,
        width=640,
        height=480,
        framerate=8,
        bitrate=700000,
        mtu=1200,
    )

    # CRSF interface
    rcSender = CrsfRcOutput()

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("stopping")

finally:
    if testTx is not None:
        testTx.stop()

    if mavlinkTx is not None:
        mavlinkTx.stop()

    if mavlinkRx is not None:
        mavlinkRx.stop()

    if videoTx is not None:
        videoTx.stop()

    runner.stop_all()