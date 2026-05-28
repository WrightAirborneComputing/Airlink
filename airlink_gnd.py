#!/home/pi/mavenv/bin/python

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
    QgcMavlinkGateway,
    DynamicUdpForwarder,
)

from rc_lib import (
    RcPacketSender,
    RcAckReceiver,
)

from io_reader_lib import (
    PicoJsonRcReader,
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
picoRcReader = None
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

    # RC uplink and ACK receiver
    rcTxer = RcPacketSender(
        name="RC-UP",
        port=rcTxerConfig.udp_port,
        interval_sec=0.05,
    )

    rcRxer = RcAckReceiver(
        name="RC-ACK",
        port=rcRxerConfig.udp_port,
    )

    # Pico joystick/switch JSON -> RC channels
    picoRcReader = PicoJsonRcReader(
        name="PICO-RC",
        serial_device="/dev/serial0",
        baudrate=115200,
        rc_sender=rcTxer,
    )

    # QGC MAVLink bridge
    mavlinkGateway = QgcMavlinkGateway(
        name="MAVLINK",
        downlink_in_port=mavlinkRxerConfig.udp_port,
        qgc_register_port=14555,
        qgc_out_port=14550,
        uplink_out_port=mavlinkTxerConfig.udp_port,
    )

    # Video display/rebro
    if False:
        videoRxer = UdpRtpH264VideoDisplay(
            name="VIDEO",
            port=videoRxerConfig.udp_port,
            width=320,
            height=180,
        )
    else:
        videoRxer = DynamicUdpForwarder(
            name="VIDEO",
            in_port=videoRxerConfig.udp_port,
            get_out_host=mavlinkGateway.get_client_ip,
            out_port=5600,
        )

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("stopping")

finally:
    if picoRcReader is not None:
        picoRcReader.stop()

    if rcTxer is not None:
        rcTxer.stop()

    if rcRxer is not None:
        rcRxer.stop()

    if mavlinkGateway is not None:
        mavlinkGateway.stop()

    if videoRxer is not None:
        videoRxer.stop()

    runner.stop_all()