#!/usr/bin/env python3

import signal
import subprocess
import threading


class ProcessRunner:
    def __init__(self):
        self.processes = []
        self.reader_threads = []

    def start(
        self,
        args,
        suppress_output=False,
        line_callback=None,
        name=None,
    ):
        #
        # If line_callback is supplied, capture output even if
        # suppress_output would otherwise hide it.
        #
        capture_output = line_callback is not None

        if suppress_output and not capture_output:
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL

        elif capture_output:
            stdout = subprocess.PIPE
            stderr = subprocess.STDOUT

        else:
            stdout = None
            stderr = None

        proc = subprocess.Popen(
            args,
            stdout=stdout,
            stderr=stderr,
            text=True,
            bufsize=1,
        )

        self.processes.append(proc)

        if capture_output:
            thread = threading.Thread(
                target=self._read_process_output,
                args=(proc, line_callback, name),
                daemon=True,
            )
            thread.start()
            self.reader_threads.append(thread)

        return proc

    def _read_process_output(self, proc, line_callback, name):
        while True:
            line = proc.stdout.readline()

            if line == "" and proc.poll() is not None:
                break

            if not line:
                continue

            line = line.strip()

            if not line:
                continue

            try:
                line_callback(line)

            except Exception as e:
                prefix = f"[{name}] " if name else ""
                print(
                    f"{prefix}line_callback exception: {e} line={line}",
                    flush=True,
                )

    def stop_all(self):
        for proc in self.processes:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)

                try:
                    proc.wait(timeout=3)

                except subprocess.TimeoutExpired:
                    proc.kill()