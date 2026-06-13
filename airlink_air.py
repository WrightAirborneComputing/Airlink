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

from led_lib import (
    ActivityLed,
    RssiLedBar
)

from udp_lib import (
    MavlinkSerialToUdp,
    UdpToSerial,
)

from rc_lib import (
    RcPacketReceiver,
)

from video_lib import (
    PiCamVideoToUdp,
)

from crsf_lib import (
    CrsfRcOutput,
)

runner = ProcessRunner()

WIFI_IFACE = "wlan1"
if(False):
    WIFI_CHANNEL = 1
    WIFI_TXPOWER_DBM = 20
elif(False):
    WIFI_CHANNEL = 15
    WIFI_TXPOWER_DBM = 30
else:
    WIFI_CHANNEL = 32
    WIFI_TXPOWER_DBM = 23
# if
WIFI_KEY = "/etc/wfb/drone.key"

rcRxerConfig      = WfbConfig(iface=WIFI_IFACE, channel=WIFI_CHANNEL, txpower_dbm=WIFI_TXPOWER_DBM, rx_key=WIFI_KEY, udp_port=9000, radio_port=0, )
rcTxerConfig      = WfbConfig(iface=WIFI_IFACE, channel=WIFI_CHANNEL, txpower_dbm=WIFI_TXPOWER_DBM, tx_key=WIFI_KEY, udp_port=9001, radio_port=1, )
mavlinkRxerConfig = WfbConfig(iface=WIFI_IFACE, channel=WIFI_CHANNEL, txpower_dbm=WIFI_TXPOWER_DBM, rx_key=WIFI_KEY, udp_port=9002, radio_port=2, )
mavlinkTxerConfig = WfbConfig(iface=WIFI_IFACE, channel=WIFI_CHANNEL, txpower_dbm=WIFI_TXPOWER_DBM, tx_key=WIFI_KEY, udp_port=9003, radio_port=3, )
videoTxerConfig   = WfbConfig(iface=WIFI_IFACE, channel=WIFI_CHANNEL, txpower_dbm=WIFI_TXPOWER_DBM, tx_key=WIFI_KEY, udp_port=9004, radio_port=4, )

rcStats  = WfbInstrumentationParser("RC-RX")
mavStats = WfbInstrumentationParser("MAVLINK-RX")

mavlinkLed = ActivityLed(21,timeout_sec=1.0)
rcLed      = ActivityLed(20)

rcRxer      = None
crsfTxer    = None
mavlinkRxer = None
mavlinkTxer = None
videoTxer   = None

try:
    WifiRadioSetup(rcRxerConfig).run()

    # WFB channels
    WfbRx(rcRxerConfig, runner).start(suppress_output=False,line_callback=rcStats.handle_line,name="RC-RX",)
    WfbTx(rcTxerConfig, runner).start()
    WfbRx(mavlinkRxerConfig, runner).start(suppress_output=False,line_callback=mavStats.handle_line,name="MAVLINK-RX",)
    WfbTx(mavlinkTxerConfig, runner).start()
    WfbTx(videoTxerConfig, runner).start()
    
    # CRSF interface
    crsfTxer = CrsfRcOutput(name="CRSF",use_pigpio=True,tx_gpio=4,baudrate=420000,rate_hz=50,)

    # RC uplink receiver, including ack txer
    rcRxer = RcPacketReceiver(name="RC-UP",in_port=rcRxerConfig.udp_port,ack_port=rcTxerConfig.udp_port,channel_callback=crsfTxer.set_channels_us,led=rcLed,rssi_getter=rcStats.get_rssi,)

    # MAVLink uplink/downlink
    mavlinkRxer = UdpToSerial(name="MAVLINK-UP",udp_port=mavlinkRxerConfig.udp_port,serial_device="/dev/serial0",baudrate=115200,led=mavlinkLed,)
    mavlinkTxer = MavlinkSerialToUdp(name="MAVLINK-DN",serial_device="/dev/serial0",baudrate=115200,udp_port=mavlinkTxerConfig.udp_port,)
    videoTxer = PiCamVideoToUdp(name="VIDEO",udp_port=videoTxerConfig.udp_port,width=320,height=240,framerate=2,bitrate=700000,mtu=1200,)

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("stopping")

finally:
    if rcRxer is not None:
        rcRxer.stop()

    if crsfTxer is not None:
        crsfTxer.close()

    if mavlinkRxer is not None:
        mavlinkRxer.stop()

    if mavlinkTxer is not None:
        mavlinkTxer.stop()

    if videoTxer is not None:
        videoTxer.stop()

    runner.stop_all()