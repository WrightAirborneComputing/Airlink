# main.py
#
# Same script runs on both Picos.
#
# GP13 LOW  -> Pico #1 aggregator
# GP13 HIGH -> Pico #2 source
#
# UART0:
#   TX = GP0
#   RX = GP1

from machine import ADC, Pin, UART
import time
import json

#
# UART
#
uart = UART(
    0,
    baudrate=115200,
    tx=Pin(0),
    rx=Pin(1),
)

#
# ADC inputs
#
adc0 = ADC(26)
adc1 = ADC(27)

#
# Role select
#
role_pin = Pin(13, Pin.IN, Pin.PULL_UP)

#
# Switch inputs
#
in18 = Pin(18, Pin.IN, Pin.PULL_UP)
in19 = Pin(19, Pin.IN, Pin.PULL_UP)
in20 = Pin(20, Pin.IN, Pin.PULL_UP)
in21 = Pin(21, Pin.IN, Pin.PULL_UP)

#
# Timing
#
SEND_HZ = 10.0
SEND_PERIOD_MS = int(1000 / SEND_HZ)

MAIN_LOOP_DELAY = 0.005

#
# UART RX assembly buffer
#
rx_buffer = ""


def read_local_state(prefix):

    #
    # ADCs
    #
    raw0 = adc0.read_u16()
    raw1 = adc1.read_u16()

    volts0 = raw0 * 3.3 / 65535.0
    volts1 = raw1 * 3.3 / 65535.0

    #
    # GPIOs
    #
    gp18 = in18.value()
    gp19 = in19.value()
    gp20 = in20.value()
    gp21 = in21.value()

    #
    # SW1
    #
    if gp19 == 0 and gp20 == 1:
        sw1 = 0

    elif gp19 == 1 and gp20 == 1:
        sw1 = 1

    elif gp19 == 1 and gp20 == 0:
        sw1 = 2

    else:
        sw1 = -1

    #
    # SW2 / SW3
    #
    sw2 = 1 if gp21 == 0 else 0
    sw3 = 1 if gp18 == 0 else 0

    #
    # Return JSON fragment
    #
    return (
        '"%s_a0_v":%.3f,'
        '"%s_a1_v":%.3f,'
        '"%s_sw1":%d,'
        '"%s_sw2":%d,'
        '"%s_sw3":%d'
        % (
            prefix,
            volts0,

            prefix,
            volts1,

            prefix,
            sw1,

            prefix,
            sw2,

            prefix,
            sw3,
        )
    )


def read_uart_line():

    global rx_buffer

    data = uart.read()

    if data is None:
        return None

    try:
        rx_buffer += data.decode("utf-8")

    except Exception:
        return None

    if "\n" not in rx_buffer:
        return None

    line, rx_buffer = rx_buffer.split("\n", 1)

    return line.strip()


def send_line(line):

    print(line)

    uart.write(line + "\r\n")


#
# Determine role
#
is_pico_1 = (role_pin.value() == 0)

if is_pico_1:
    print("ROLE: Pico #1 aggregator")

else:
    print("ROLE: Pico #2 source")


last_send = time.ticks_ms()

while True:

    #
    # Pico #1
    #
    if is_pico_1:

        line = read_uart_line()

        if line is not None:

            try:
                #
                # Parse packet from Pico #2
                #
                p2_packet = json.loads(line)

                #
                # Read local state
                #
                p1_state = read_local_state("p1")

                #
                # Build combined packet
                #
                out_line = (
                    "{"
                    '"p2_a0_v":%.3f,'
                    '"p2_a1_v":%.3f,'
                    '"p2_sw1":%d,'
                    '"p2_sw2":%d,'
                    '"p2_sw3":%d,'
                    "%s"
                    "}"
                    % (
                        p2_packet.get("p2_a0_v", 0),
                        p2_packet.get("p2_a1_v", 0),

                        p2_packet.get("p2_sw1", -1),
                        p2_packet.get("p2_sw2", 0),
                        p2_packet.get("p2_sw3", 0),

                        p1_state,
                    )
                )

                #
                # Forward to RPi4
                #
                send_line(out_line)

            except Exception as e:

                print(
                    "Bad JSON from Pico #2:",
                    line,
                    e
                )

    #
    # Pico #2
    #
    else:

        now = time.ticks_ms()

        if time.ticks_diff(now, last_send) >= SEND_PERIOD_MS:

            last_send = now

            out_line = (
                "{"
                + read_local_state("p2")
                + "}"
            )

            send_line(out_line)

    time.sleep(MAIN_LOOP_DELAY)