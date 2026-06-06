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
    WfbRx,
    WfbInstrumentationParser,
)

from udp_lib import (
    QgcMavlinkGateway,
    DynamicUdpForwarder,
)

from rc_lib import (
    RcPacketSender,
    RcAckReceiver,
)

from led_lib import (
    ActivityLed,
    RssiLedBar
)

from io_reader_lib import (
    PicoJsonRcReader,
)

from video_lib import (
    UdpRtpH264VideoDisplay,
)

runner = ProcessRunner()

WIFI_IFACE = "wlan1"
if(False):
    WIFI_CHANNEL = 1
    WIFI_TXPOWER_DBM = 20
else:
    WIFI_CHANNEL = 15
    WIFI_TXPOWER_DBM = 30
# if
WIFI_KEY = "/etc/wfb/gs.key"

rcTxerConfig      = WfbConfig(iface=WIFI_IFACE, channel=WIFI_CHANNEL, txpower_dbm=WIFI_TXPOWER_DBM, tx_key=WIFI_KEY, udp_port=9000, radio_port=0)
rcRxerConfig      = WfbConfig(iface=WIFI_IFACE, channel=WIFI_CHANNEL, txpower_dbm=WIFI_TXPOWER_DBM, rx_key=WIFI_KEY, udp_port=9001, radio_port=1)
mavlinkTxerConfig = WfbConfig(iface=WIFI_IFACE, channel=WIFI_CHANNEL, txpower_dbm=WIFI_TXPOWER_DBM, tx_key=WIFI_KEY, udp_port=9002, radio_port=2)
mavlinkRxerConfig = WfbConfig(iface=WIFI_IFACE, channel=WIFI_CHANNEL, txpower_dbm=WIFI_TXPOWER_DBM, rx_key=WIFI_KEY, udp_port=9003, radio_port=3)
videoRxerConfig   = WfbConfig(iface=WIFI_IFACE, channel=WIFI_CHANNEL, txpower_dbm=WIFI_TXPOWER_DBM, rx_key=WIFI_KEY, udp_port=9004, radio_port=4)

rcTxer         = None
rcRxer         = None
picoRcReader   = None
mavlinkGateway = None
videoRxer      = None

rcStats    = WfbInstrumentationParser("RC-RX")
mavStats   = WfbInstrumentationParser("MAVLINK-RX")
videoStats = WfbInstrumentationParser("VIDEO-RX")

mavlinkLed = ActivityLed(21)
rcLed      = ActivityLed(20)
rssiBar    = RssiLedBar()

try:
    WifiRadioSetup(rcTxerConfig).run()

    # WFB channels
    WfbTx(rcTxerConfig, runner).start()
    WfbRx(rcRxerConfig, runner).start(suppress_output=False,line_callback=rcStats.handle_line,name="RC-RX",)
    WfbTx(mavlinkTxerConfig, runner).start()
    WfbRx(mavlinkRxerConfig, runner).start(suppress_output=True,line_callback=mavStats.handle_line,name="MAVLINK-RX",)
    WfbRx(videoRxerConfig, runner).start(suppress_output=True,line_callback=videoStats.handle_line,name="VIDEO-RX",)

    # RC uplink and ACK receiver
    rcTxer = RcPacketSender(name="RC-UP",port=rcTxerConfig.udp_port)
    rcRxer = RcAckReceiver(name="RC-ACK",port=rcRxerConfig.udp_port,led=rcLed,rssi_getter=rcStats.get_rssi,rssi_led_bar=rssiBar,)

    # Pico joystick/switch JSON -> RC channels
    picoRcReader = PicoJsonRcReader(name="PICO-RC",serial_device="/dev/serial0",baudrate=115200,rc_sender=rcTxer,)

    # QGC MAVLink bridge
    mavlinkGateway = QgcMavlinkGateway(name="MAVLINK",downlink_in_port=mavlinkRxerConfig.udp_port,qgc_register_port=14555,qgc_out_port=14550,uplink_out_port=mavlinkTxerConfig.udp_port,led=mavlinkLed,)

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

    mavlinkLed.stop()
    rcLed.stop()

    runner.stop_all()