#!/home/pi/mavenv/bin/python

import time

from debug_lib import print_banner

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
    UdpTestReceiver,
    UdpTestSender,
    MavlinkSerialToUdp,
    UdpToSerial
)

from rc_lib import (
    RcPacketReceiver
)

from video_lib import (
    PiCamVideoToUdp
)

from crsf_lib import (
    CrsfRcOutput
)

print_banner(
    "AIRLINK AIR",
    udp_ports=[
        9000,
        9001,
        9002,
        9003,
    ],
    serial_ports=[
        "/dev/serial0",
    ],
    gpios=[
        "CRSF TX GPIO4",
    ],
    radio_ports=[
        "0 RC",
        "1 MAVLINK-DN",
        "2 MAVLINK-UP",
        "3 VIDEO",
    ],
)

runner = ProcessRunner()

rcRxerConfig = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/drone.key",
    udp_port=9000,
    radio_port="0",
)

rcTxerConfig = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/drone.key",
    udp_port=9001,
    radio_port="1",
)

mavlinkRxerConfig = WfbConfig(
    iface="wlan1",
    channel="1",
    rx_key="/etc/wfb/drone.key",
    udp_port=9002,
    radio_port="2",
)

mavlinkTxerConfig = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/drone.key",
    udp_port=9003,
    radio_port="3",
)

videoTxerConfig = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/drone.key",
    udp_port=9004,
    radio_port="4",
)

rcRxer = None
rcTxer = None
mavlinkRxer = None
mavlinkTxer = None
videoTxer = None

try:
    WifiRadioSetup(rcRxerConfig).run()

    # WFB transmit channels
    WfbRx(rcRxerConfig, runner).start(suppress_output=True)
    WfbTx(rcTxerConfig, runner).start(suppress_output=True)
    WfbRx(mavlinkRxerConfig, runner).start(suppress_output=True)
    WfbTx(mavlinkTxerConfig, runner).start(suppress_output=True)
    WfbTx(videoTxerConfig, runner).start(suppress_output=True)

    # CRSF interface
    rcTxer = CrsfRcOutput(name="CRSF", use_pigpio=True, tx_gpio=4, baudrate=420000, rate_hz=50,)

    # RC 
    rcRxer = RcPacketReceiver(name="RC-UP", in_port=rcRxerConfig.udp_port, ack_port=rcTxerConfig.udp_port, channel_callback=rcTxer.set_channels_us,)

    # MAVLink
    mavlinkRxer = UdpToSerial(name="MAVLINK-UP",udp_port=mavlinkRxerConfig.udp_port,serial_device="/dev/serial0",baudrate=115200,)
    mavlinkTxer = MavlinkSerialToUdp(name="MAVLINK-DN",serial_device="/dev/serial0",baudrate=115200,udp_port=mavlinkTxerConfig.udp_port,)

    # VIDEO downlink: PiCam -> local UDP 
    videoTxer = PiCamVideoToUdp(name="VIDEO",udp_port=videoTxerConfig.udp_port,width=640,height=480,framerate=2,bitrate=700000,mtu=1200,)

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("stopping")

finally:

    if rcRxer is not None:
        rcRxer.stop()

    if rcTxer is not None:
        rcTxer.close()

    if mavlinkRxer is not None:
        mavlinkRxer.stop()

    if mavlinkTxer is not None:
        mavlinkTxer.stop()

    if videoTxer is not None:
        videoTxer.stop()

    runner.stop_all()