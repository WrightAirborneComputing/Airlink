from gpiozero import LED
import threading
import time


class ActivityLed:
    def __init__(
        self,
        gpio_pin,
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

    def activity(self):
        self.last_activity = time.time()

    def stop(self):
        self.running = False
        self.led.off()

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

            time.sleep(0.05)