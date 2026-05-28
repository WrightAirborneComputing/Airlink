# main.py

from machine import ADC, Pin, UART
import time
import json

uart = UART(
    0,
    baudrate=115200,
    tx=Pin(0),
    rx=Pin(1),
)

adc0 = ADC(26)   # GP26 / ADC0
adc1 = ADC(27)   # GP27 / ADC1

in18 = Pin(18, Pin.IN, Pin.PULL_UP)
in19 = Pin(19, Pin.IN, Pin.PULL_UP)
in20 = Pin(20, Pin.IN, Pin.PULL_UP)
in21 = Pin(21, Pin.IN, Pin.PULL_UP)

SEND_HZ = 10.0
SEND_PERIOD = 1.0 / SEND_HZ

while True:
    raw0 = adc0.read_u16()
    raw1 = adc1.read_u16()

    volts0 = raw0 * 3.3 / 65535.0
    volts1 = raw1 * 3.3 / 65535.0

    gp18 = in18.value()
    gp19 = in19.value()
    gp20 = in20.value()
    gp21 = in21.value()

    if gp19 == 0 and gp20 == 1:
        sw1 = 0
    elif gp19 == 1 and gp20 == 1:
        sw1 = 1
    elif gp19 == 1 and gp20 == 0:
        sw1 = 2
    else:
        sw1 = -1

    sw2 = 1 if gp21 == 0 else 0
    sw3 = 1 if gp18 == 0 else 0

    packet = {
        "a0_v": round(volts0, 3),
        "a1_v": round(volts1, 3),
        "sw1": sw1,
        "sw2": sw2,
        "sw3": sw3,
    }

    line = json.dumps(packet)

    print(line)
    uart.write(line + "\r\n")

    time.sleep(SEND_PERIOD)