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

from process_lib import (
    ProcessRunner,
)

from wfb_lib import (
    WfbConfig,
    WifiRadioSetup,
    WfbTx,
    WfbRx,
)

from udp_lib import (
    UdpTestSender,
    UdpTestReceiver,
    QgcMavlinkGateway,
    DynamicUdpForwarder
)

from video_lib import (
    UdpRtpH264VideoDisplay,
)

runner = ProcessRunner()

rcTxerConfig = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/gs.key",
    udp_port=9000,
    radio_port="0",
)

rcRxerConfig = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/gs.key",
    udp_port=9001,
    radio_port="1",
)

mavlinkTxerConfig = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/gs.key",
    udp_port=9002,
    radio_port="2",
)

mavlinkRxerConfig = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/gs.key",
    udp_port=9003,
    radio_port="3",
)

videoRxerConfig = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/gs.key",
    udp_port=9004,
    radio_port="4",
)

rcTxer = None
rcRxer = None
mavlinkGateway = None
videoRxer = None

try:
    WifiRadioSetup(rcTxerConfig).run()

    # WFB channels
    WfbTx(rcTxerConfig, runner).start(suppress_output=True)
    WfbRx(rcRxerConfig, runner).start(suppress_output=True)
    WfbTx(mavlinkTxerConfig, runner).start(suppress_output=True)
    WfbRx(mavlinkRxerConfig, runner).start(suppress_output=True)
    WfbRx(videoRxerConfig, runner).start(suppress_output=True)

    # RC
    rcTxer = UdpTestSender(name="RC-DN",port=rcTxerConfig.udp_port,interval_sec=0.1,)
    rcRxer = UdpTestReceiver(name="RC-DN", port=rcRxerConfig.udp_port,)

    # QGC MAVLink bridge:
    mavlinkGateway = QgcMavlinkGateway(name="MAVLINK", downlink_in_port=mavlinkRxerConfig.udp_port, qgc_register_port=14555, qgc_out_port=14550, uplink_out_port=mavlinkTxerConfig.udp_port,)

    # Video display/rebro
    if(False):
        videoRxerConfig = UdpRtpH264VideoDisplay(name="VIDEO", port=videoRxerConfig.udp_port, width=320, height=180,)
    else:
        videoRxerConfig = DynamicUdpForwarder(name="VIDEO", in_port=videoRxerConfig.udp_port, get_out_host=mavlinkGateway.get_client_ip,out_port=5600,)
    # if

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("stopping")

finally:
    if rcTxer is not None:
        rcTxer.stop()

    if rcRxer is not None:
        rcTxer.stop()

    if mavlinkGateway is not None:
        mavlinkGateway.stop()

    if videoRxer is not None:
        videoRxerConfig.stop()

    runner.stop_all()
