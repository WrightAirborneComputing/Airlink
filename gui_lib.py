#!/usr/bin/env python3

import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

import sys

class GuiStdout:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, text):
        self.text_widget.after(0, self._append, text)

    def flush(self):
        pass

    def _append(self, text):
        self.text_widget.insert(tk.END, text)
        self.text_widget.see(tk.END)


class AirlinkGui:
    def __init__(
        self,
        title,
        worker_callback,
        cleanup_callback,
        rssi_getter=None,
        voltage_getter=None,
        altitude_getter=None,
    ):
        self.worker_callback = worker_callback
        self.cleanup_callback = cleanup_callback

        self.rssi_getter = rssi_getter
        self.voltage_getter = voltage_getter
        self.altitude_getter = altitude_getter

        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("1100x700")

        ###########################################################
        # Telemetry panel
        ###########################################################

        telemetry = tk.Frame(self.root)
        telemetry.pack(fill=tk.X, padx=10, pady=10)

        title_font = ("Helvetica", 18, "bold")
        value_font = ("Courier New", 34, "bold")

        #
        # RSSI
        #

        rssi_frame = tk.Frame(telemetry)
        rssi_frame.pack(side=tk.LEFT, padx=25)

        tk.Label(
            rssi_frame,
            text="RSSI",
            font=title_font,
        ).pack()

        self.rssi_label = tk.Label(
            rssi_frame,
            text="---",
            width=8,
            font=value_font,
            fg="green",
        )

        self.rssi_label.pack()

        #
        # Battery
        #

        batt_frame = tk.Frame(telemetry)
        batt_frame.pack(side=tk.LEFT, padx=25)

        tk.Label(
            batt_frame,
            text="Battery",
            font=title_font,
        ).pack()

        self.voltage_label = tk.Label(
            batt_frame,
            text="---",
            width=8,
            font=value_font,
            fg="blue",
        )

        self.voltage_label.pack()

        #
        # Altitude
        #

        alt_frame = tk.Frame(telemetry)
        alt_frame.pack(side=tk.LEFT, padx=25)

        tk.Label(
            alt_frame,
            text="Altitude",
            font=title_font,
        ).pack()

        self.altitude_label = tk.Label(
            alt_frame,
            text="---",
            width=8,
            font=value_font,
            fg="purple",
        )

        self.altitude_label.pack()

        ###########################################################
        # Console
        ###########################################################

        self.console = ScrolledText(
            self.root,
            font=("Courier New", 14),
        )

        self.console.pack(
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=10,
        )

        sys.stdout = GuiStdout(self.console)
        sys.stderr = GuiStdout(self.console)

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self._close,
        )

    ###############################################################

    def run(self):

        threading.Thread(
            target=self.worker_callback,
            daemon=True,
        ).start()

        self._update_display()

        self.root.mainloop()

    ###############################################################

    def _update_display(self):

        #
        # RSSI
        #

        if self.rssi_getter is not None:
            try:
                rssi = self.rssi_getter()

                if rssi is None:
                    self.rssi_label.config(text="---")
                else:
                    self.rssi_label.config(
                        text=f"{rssi} dBm"
                    )
            except Exception:
                self.rssi_label.config(text="ERR")

        #
        # Battery
        #

        if self.voltage_getter is not None:
            try:
                v = self.voltage_getter()

                if v is None:
                    self.voltage_label.config(text="---")
                else:
                    self.voltage_label.config(
                        text=f"{v:.1f} V"
                    )
            except Exception:
                self.voltage_label.config(text="ERR")

        #
        # Altitude
        #

        if self.altitude_getter is not None:
            try:
                alt = self.altitude_getter()

                if alt is None:
                    self.altitude_label.config(text="---")
                else:
                    self.altitude_label.config(
                        text=f"{alt:.1f} m"
                    )
            except Exception:
                self.altitude_label.config(text="ERR")

        self.root.after(
            200,
            self._update_display,
        )

    ###############################################################

    def _close(self):
        try:
            self.cleanup_callback()
        finally:
            self.root.destroy()