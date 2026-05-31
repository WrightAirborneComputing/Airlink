from gpiozero import LED
import threading
import time


class ActivityLed:
    def __init__(
        self,
        gpio_pin,
        flash_hz=2.0,
        timeout_sec=1.0,
    ):
        self.led = LED(gpio_pin)

        self.flash_period = 1.0 / flash_hz
        self.timeout_sec = timeout_sec

        self.last_activity = 0.0
        self.running = True

        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self.thread.start()

    def activity(self):
        self.last_activity = time.time()

    def stop(self):
        self.running = False
        self.led.off()

    def _run(self):
        led_state = False

        while self.running:

            active = (
                time.time() - self.last_activity
                < self.timeout_sec
            )

            if active:
                led_state = not led_state

                if led_state:
                    self.led.on()
                else:
                    self.led.off()

                time.sleep(self.flash_period / 2.0)

            else:
                led_state = False
                self.led.off()
                time.sleep(0.1)