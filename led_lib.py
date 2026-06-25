from gpiozero import LED
import threading
import time

class OnLed:
    def __init__(
        self,
        gpio_pin,
    ):
        self.led = LED(gpio_pin)
        self.led.on()
    # def

    def stop(self):
        self.led.off()
    # def

# class

class ActivityLed:
    def __init__(
        self,
        gpio_pin,
        on = False,
        timeout_sec=0.25,
    ):
        self.led = LED(gpio_pin)

        self.timeout_sec = timeout_sec

        self.last_activity = 0.0
        self.running = True

        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self.thread.start()
    # def

    def activity(self):
        self.last_activity = time.time()
    # def

    def stop(self):
        self.running = False
        self.led.off()
    # def

    def _run(self):
        while self.running:

            active = (
                time.time() - self.last_activity
                < self.timeout_sec
            )

            if active:
                self.led.on()
            else:
                self.led.off()
            # if

            time.sleep(0.05)
        # while
    # def
# class


class RssiLedBar:
    def __init__(
        self,
        gpio_pins=(26,19,13,6,5),
        max_db=-20,
        min_db=-85,
    ):
        # gpio_pins ordered top -> bottom
        self.leds = [LED(pin) for pin in gpio_pins]
        self.min_db = min_db
        self.max_db = max_db
    # def

    def set_rssi(self, rssi):
        if rssi is None:
            level = 0
        else:
            rssi = max(self.min_db, min(self.max_db, float(rssi)))
            fraction = (rssi - self.min_db) / (self.max_db - self.min_db)
            level = int(round(fraction * len(self.leds)))
        # if

        # bottom LEDs light first, top LED lights last
        for i, led in enumerate(self.leds):
            led_index_from_bottom = len(self.leds) - 1 - i

            if led_index_from_bottom < level:
                led.on()
            else:
                led.off()
            # if
        # for
    # def

    def off(self):
        for led in self.leds:
            led.off()
    # def

    def stop(self):
        self.off()# class
    # def
