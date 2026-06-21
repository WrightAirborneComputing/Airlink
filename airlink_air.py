#!/home/pi/mavenv/bin/python

import time
import threading

from debug_lib import print_banner
from process_lib import ProcessRunner
from gui_lib import AirlinkGui

from wfb_lib import (
    WfbConfig,
    WifiRadioSetup,
    WfbTx,
    WfbRx,
    WfbInstrumentationParser,
)

from led_lib import ActivityLed
from udp_lib import MavlinkSerialToUdp, UdpToSerial
from rc_lib import RcPacketReceiver
from video_lib import PiCamVideoToUdp, UsbCameraVideoToUdp
from crsf_lib import CrsfRcOutput
from sbus_lib import SbusRcOutput


runner = ProcessRunner()
stop_event = threading.Event()

rcStats = None
mavStats = None

rcRxer = None
rcSerialTxer = None
mavlinkRxer = None
mavlinkTxer = None
videoTxer = None

mavlinkLed = None
rcLed = None


def cleanup():
    global rcRxer, rcSerialTxer, mavlinkRxer, mavlinkTxer, videoTxer
    global mavlinkLed, rcLed

    stop_event.set()
    print("stopping")

    if rcRxer is not None:
        rcRxer.stop()

    if rcSerialTxer is not None:
        rcSerialTxer.close()

    if mavlinkRxer is not None:
        mavlinkRxer.stop()

    if mavlinkTxer is not None:
        mavlinkTxer.stop()

    if videoTxer is not None:
        videoTxer.stop()

    if mavlinkLed is not None:
        mavlinkLed.stop()

    if rcLed is not None:
        rcLed.stop()

    runner.stop_all()


def run_airlink():
    global rcStats, mavStats
    global rcRxer, rcSerialTxer, mavlinkRxer, mavlinkTxer, videoTxer
    global mavlinkLed, rcLed

    try:
        print_banner(
            "AIRLINK AIR",
            udp_ports=[9000, 9001, 9002, 9003, 9004],
            serial_ports=["/dev/serial0"],
            gpios=["CRSF/SBUS TX GPIO4", "LED20 RC", "LED21 MAVLINK"],
            radio_ports=[
                "0 RC-UP",
                "1 RC-ACK",
                "2 MAVLINK-UP",
                "3 MAVLINK-DN",
                "4 VIDEO-DN",
            ],
        )

        WIFI_IFACE = "wlan1"
        WIFI_CHANNEL = 17
        WIFI_TXPOWER_DBM = 30
        WIFI_KEY = "/etc/wfb/drone.key"

        rcRxerConfig = WfbConfig(
            iface=WIFI_IFACE,
            channel=WIFI_CHANNEL,
            txpower_dbm=WIFI_TXPOWER_DBM,
            rx_key=WIFI_KEY,
            udp_port=9000,
            radio_port=0,
        )

        rcTxerConfig = WfbConfig(
            iface=WIFI_IFACE,
            channel=WIFI_CHANNEL,
            txpower_dbm=WIFI_TXPOWER_DBM,
            tx_key=WIFI_KEY,
            udp_port=9001,
            radio_port=1,
        )

        mavlinkRxerConfig = WfbConfig(
            iface=WIFI_IFACE,
            channel=WIFI_CHANNEL,
            txpower_dbm=WIFI_TXPOWER_DBM,
            rx_key=WIFI_KEY,
            udp_port=9002,
            radio_port=2,
        )

        mavlinkTxerConfig = WfbConfig(
            iface=WIFI_IFACE,
            channel=WIFI_CHANNEL,
            txpower_dbm=WIFI_TXPOWER_DBM,
            tx_key=WIFI_KEY,
            udp_port=9003,
            radio_port=3,
        )

        videoTxerConfig = WfbConfig(
            iface=WIFI_IFACE,
            channel=WIFI_CHANNEL,
            txpower_dbm=WIFI_TXPOWER_DBM,
            tx_key=WIFI_KEY,
            udp_port=9004,
            radio_port=4,
        )

        rcStats = WfbInstrumentationParser("RC-RX")
        mavStats = WfbInstrumentationParser("MAVLINK-RX")

        mavlinkLed = ActivityLed(21, timeout_sec=1.0)
        rcLed = ActivityLed(20)

        WifiRadioSetup(rcRxerConfig).run()

        WfbRx(rcRxerConfig, runner).start(
            suppress_output=False,
            line_callback=rcStats.handle_line,
            name="RC-RX",
        )

        WfbTx(rcTxerConfig, runner).start()

        WfbRx(mavlinkRxerConfig, runner).start(
            suppress_output=False,
            line_callback=mavStats.handle_line,
            name="MAVLINK-RX",
        )

        WfbTx(mavlinkTxerConfig, runner).start()
        WfbTx(videoTxerConfig, runner).start()

        if True:
            rcSerialTxer = CrsfRcOutput(
                name="CRSF",
                use_pigpio=True,
                tx_gpio=4,
                baudrate=420000,
                rate_hz=50,
            )
        else:
            rcSerialTxer = SbusRcOutput(
                name="SBUS",
                use_pigpio=True,
                tx_gpio=4,
                rate_hz=50,
            )

        rcRxer = RcPacketReceiver(
            name="RC-UP",
            in_port=rcRxerConfig.udp_port,
            ack_port=rcTxerConfig.udp_port,
            channel_callback=rcSerialTxer.set_channels_us,
            led=rcLed,
            rssi_getter=rcStats.get_rssi,
            rc_timeout_sec=1.0,
            rc_active_callback=rcSerialTxer.set_enabled,
        )

        mavlinkRxer = UdpToSerial(
            name="MAVLINK-UP",
            udp_port=mavlinkRxerConfig.udp_port,
            serial_device="/dev/serial0",
            baudrate=115200,
            led=mavlinkLed,
        )

        mavlinkTxer = MavlinkSerialToUdp(
            name="MAVLINK-DN",
            serial_device="/dev/serial0",
            baudrate=115200,
            udp_port=mavlinkTxerConfig.udp_port,
        )

        if(False):
            videoTxer = PiCamVideoToUdp(
                name="VIDEO",
                udp_port=videoTxerConfig.udp_port,
                width=320,
                height=240,
                framerate=2,
                bitrate=700000,
                mtu=1200,
            )
        else:
            videoTxer = UsbCameraVideoToUdp(
                name="VIDEO",
                udp_port=videoTxerConfig.udp_port,
                width=320,
                height=240,
                framerate=30,
                bitrate=2_000_000,
                input_format="mjpeg",   # "mjpeg", "h264", or "yuyv422"
            )
        # if

        while not stop_event.is_set():
            time.sleep(0.2)

    except Exception as e:
        print(f"Air app exception: {e}", flush=True)

    finally:
        cleanup()


if __name__ == "__main__":
    gui = AirlinkGui(
        title="Airlink Air",
        rssi_getter=lambda: rcStats.get_rssi() if rcStats is not None else None,
        worker_callback=run_airlink,
        cleanup_callback=cleanup,
    )
    gui.run()