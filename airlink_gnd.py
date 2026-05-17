#!/home/pi/mavenv/bin/python

# Test path:
# Air test -> WFB p0 -> GS UDP 9000
#
# Mavlink path:
# Downlink: Air serial -> WFB p1 -> GS UDP 9001 -> QGC 14550
# Uplink:   QGC 14555 -> GS UDP 9002 -> WFB p3 -> Air UDP 9002 -> serial
#
# Video path:
# Air PiCam -> WFB p2 -> GS UDP 9003 -> GStreamer display
#

import time

from wfb_common import (
    WfbConfig,
    WifiRadioSetup,
    ProcessRunner,
    WfbTx,
    WfbRx,
    UdpTestReceiver,
    UdpRtpH264VideoDisplay,
    QgcMavlinkGateway,
    DynamicUdpForwarder
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

mavlinkSender = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/gs.key",
    udp_port=9002,
    radio_port="2",
)

videoReceiver = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/gs.key",
    udp_port=9003,
    radio_port="3",
)

testRx = None
mavlinkGateway = None
videoRx = None

try:
    WifiRadioSetup(testReceiver).run()

    # WFB receive channels
    WfbRx(testReceiver, runner).start(suppress_output=True)
    WfbRx(mavlinkReceiver, runner).start(suppress_output=True)
    WfbTx(mavlinkSender, runner).start(suppress_output=True)
    WfbRx(videoReceiver, runner).start(suppress_output=True)

    # Debug/test receiver
    testRx = UdpTestReceiver(name="TEST", port=testReceiver.udp_port,)

    # QGC MAVLink bridge:
    mavlinkGateway = QgcMavlinkGateway(name="MAVLINK", downlink_in_port=mavlinkReceiver.udp_port, qgc_register_port=14555, qgc_out_port=14550, uplink_out_port=mavlinkSender.udp_port,)

    # Video display
    if(False):
        videoRx = UdpRtpH264VideoDisplay(name="VIDEO", port=videoReceiver.udp_port, width=320, height=180,)
    else:
        videoRx = DynamicUdpForwarder(name="VIDEO", in_port=videoReceiver.udp_port, get_out_host=mavlinkGateway.get_client_ip,out_port=5600,)
    # if

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("stopping")

finally:
    if testRx is not None:
        testRx.stop()

    if mavlinkGateway is not None:
        mavlinkGateway.stop()

    if videoRx is not None:
        videoRx.stop()

    runner.stop_all()
