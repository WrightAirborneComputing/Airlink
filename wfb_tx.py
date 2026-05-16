#!/home/pi/mavenv/bin/python

import time

from wfb_common import (
    WfbConfig,
    WifiRadioSetup,
    ProcessRunner,
    WfbTx,
    UdpTestSender,
    MavlinkSerialToUdp,
    PiCamVideoToUdp,
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

videoSender = WfbConfig(
    iface="wlan1",
    channel="1",
    tx_key="/etc/wfb/drone.key",
    udp_port=9002,
    radio_port="2",
)

try:
    WifiRadioSetup(testSender).run()

    WfbTx(testSender,    runner).start(suppress_output=True)
    WfbTx(mavlinkSender, runner).start(suppress_output=True)
    WfbTx(videoSender,   runner).start(suppress_output=True)

    # Start all test packet generators
    testTx    = UdpTestSender(name="TEST", port=testSender.udp_port, interval_sec=0.02,)
    mavlinkTx = MavlinkSerialToUdp(name="MAVLINK", serial_device="/dev/serial0", baudrate=115200, udp_port=mavlinkSender.udp_port,)
    videoTx = PiCamVideoToUdp(name="VIDEO", udp_port=videoSender.udp_port, width=640, height=480, framerate=8, bitrate=700000, mtu=1200,)

    # Keep main thread alive
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("stopping")

finally:
    testTx.stop()
    mavlinkTx.stop()
    videoTx.stop()
    runner.stop_all()