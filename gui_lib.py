#!/usr/bin/env python3

import sys
import queue
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText


class QueueWriter:
    def __init__(self, q):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(text)

    def flush(self):
        pass


class AirlinkGui:
    def __init__(
        self,
        title,
        rssi_getter=None,
        worker_callback=None,
        cleanup_callback=None,
    ):
        self.title = title
        self.rssi_getter = rssi_getter
        self.worker_callback = worker_callback
        self.cleanup_callback = cleanup_callback

        self.log_queue = queue.Queue()

    def log(self, text):
        self.log_queue.put(str(text))

    def run(self):
        sys.stdout = QueueWriter(self.log_queue)
        sys.stderr = QueueWriter(self.log_queue)

        self.root = tk.Tk()
        self.root.title(self.title)

        rssi_frame = tk.Frame(self.root)
        rssi_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(
            rssi_frame,
            text="RC RSSI",
            font=("Arial", 24),
        ).pack()

        self.rssi_var = tk.StringVar(value="---")

        tk.Label(
            rssi_frame,
            textvariable=self.rssi_var,
            font=("Arial", 72, "bold"),
        ).pack()

        self.console = ScrolledText(
            self.root,
            height=28,
            width=120,
            font=("Courier", 18),
        )
        self.console.pack(fill="both", expand=True, padx=10, pady=10)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.worker_callback is not None:
            threading.Thread(
                target=self.worker_callback,
                daemon=True,
            ).start()

        self._pump_console()
        self._update_rssi()

        self.root.mainloop()

    def _pump_console(self):
        try:
            while True:
                text = self.log_queue.get_nowait()
                self.console.insert("end", text)
                self.console.see("end")
        except queue.Empty:
            pass

        self.root.after(100, self._pump_console)

    def _update_rssi(self):
        value = None

        if self.rssi_getter is not None:
            try:
                value = self.rssi_getter()
            except Exception:
                value = None

        if value is None:
            self.rssi_var.set("---")
        else:
            self.rssi_var.set(f"{value} dB")

        self.root.after(250, self._update_rssi)

    def _on_close(self):
        if self.cleanup_callback is not None:
            self.cleanup_callback()

        self.root.after(500, self.root.destroy)