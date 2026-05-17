#!/usr/bin/env python3
import signal
import subprocess

class ProcessRunner:
    def __init__(self):
        self.processes = []

    def start(self, args, suppress_output=False):
        stdout = subprocess.DEVNULL if suppress_output else None
        stderr = subprocess.DEVNULL if suppress_output else None
        proc = subprocess.Popen(args, stdout=stdout, stderr=stderr)
        self.processes.append(proc)
        return proc

    def stop_all(self):
        for proc in self.processes:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
# class
