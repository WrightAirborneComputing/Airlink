#!/usr/bin/env python3

import time

from pymavlink.dialects.v20 import common as mavlink2


class MavlinkMonitor:
    def __init__(self):
        self.parser = mavlink2.MAVLink(None)

        self.last_update = 0.0

        self.battery_voltage = None
        self.battery_current = None
        self.battery_remaining = None

        self.relative_altitude = None
        self.absolute_altitude = None
        self.hud_altitude = None

        self.airspeed = None
        self.groundspeed = None
        self.heading = None
        self.throttle = None
        self.climb = None

        self.mode = None
        self.armed = None

        self.gps_fix = None
        self.gps_satellites = None

    ####################################################################
    # Feed raw MAVLink bytes into the parser
    ####################################################################

    def feed(self, data: bytes):
        for b in data:
            msg = self.parser.parse_char(bytes([b]))

            if msg is not None:
                self._handle_message(msg)

    ####################################################################

    def _handle_message(self, msg):
        self.last_update = time.time()

        mtype = msg.get_type()

        ###############################################################

        if mtype == "SYS_STATUS":
            self.battery_voltage = msg.voltage_battery / 1000.0

            if msg.current_battery != -1:
                self.battery_current = msg.current_battery / 100.0

            self.battery_remaining = msg.battery_remaining

        ###############################################################

        elif mtype == "GLOBAL_POSITION_INT":
            self.relative_altitude = msg.relative_alt / 1000.0
            self.absolute_altitude = msg.alt / 1000.0

        ###############################################################

        elif mtype == "VFR_HUD":
            self.airspeed = msg.airspeed
            self.groundspeed = msg.groundspeed
            self.heading = msg.heading
            self.throttle = msg.throttle
            self.climb = msg.climb
            self.hud_altitude = msg.alt

        ###############################################################

        elif mtype == "GPS_RAW_INT":
            self.gps_fix = msg.fix_type
            self.gps_satellites = msg.satellites_visible

        ###############################################################

        elif mtype == "HEARTBEAT":

            # self.mode = mavlink2.mode_string_v20(msg)

            self.armed = (
                msg.base_mode &
                mavlink2.MAV_MODE_FLAG_SAFETY_ARMED
            ) != 0

    ####################################################################
    # timeout helper
    ####################################################################

    def _fresh(self):
        return (time.time() - self.last_update) < 5.0

    ####################################################################
    # Getters
    ####################################################################

    def get_voltage(self):
        if not self._fresh():
            return None
        return self.battery_voltage

    def get_current(self):
        if not self._fresh():
            return None
        return self.battery_current

    def get_remaining(self):
        if not self._fresh():
            return None
        return self.battery_remaining

    def get_relative_altitude(self):
        if not self._fresh():
            return None
        return self.relative_altitude

    def get_hud_altitude(self):
        if not self._fresh():
            return None
        return self.hud_altitude

    def get_absolute_altitude(self):
        if not self._fresh():
            return None
        return self.absolute_altitude

    def get_airspeed(self):
        if not self._fresh():
            return None
        return self.airspeed

    def get_groundspeed(self):
        if not self._fresh():
            return None
        return self.groundspeed

    def get_heading(self):
        if not self._fresh():
            return None
        return self.heading

    def get_throttle(self):
        if not self._fresh():
            return None
        return self.throttle

    def get_climb(self):
        if not self._fresh():
            return None
        return self.climb

    def get_mode(self):
        if not self._fresh():
            return None
        return self.mode

    def get_armed(self):
        if not self._fresh():
            return None
        return self.armed

    def get_gps_fix(self):
        if not self._fresh():
            return None
        return self.gps_fix

    def get_satellites(self):
        if not self._fresh():
            return None
        return self.gps_satellites