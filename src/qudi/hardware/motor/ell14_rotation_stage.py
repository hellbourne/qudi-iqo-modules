# -*- coding: utf-8 -*-

"""
This file contains the hardware control of the motorized stage for PI.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import time
import visa
from collections import OrderedDict
import bitstring
from qudi.core.configoption import ConfigOption
from qudi.core.module import Base
from interface.motor_interface import MotorInterface
from enum import Enum
from qudi.core.util.mutex import Mutex


class MotorRotationELL14(Base, MotorInterface):
    """
    unstable: Amit Finkler
    at this point assumes only one Elliptec device is connected (no bus), so address is always zero

    Example config for copy-paste:

    motorstage_ELL14:
        module.Class: 'motor.ell14_rotation_stage.MotorRotationELL14'
        resource_name: 'ASRL9::INSTR'

    """
    _modclass = 'MotorRotation'
    _modtype = 'hardware'

    """
    Configurations
    """
    resource_name = ConfigOption('resource_name', 'ASRL1::INSTR', missing='warn')

    # These used to be defined in the configuration. However, there's no reason to define in this in the configuration,
    # as they are hardware-specific and not system dependent settings.
    # It is more correct to have "hard-coded" within the module.

    _baud_rate = 9600
    _timeout = 8000  # At 50% velocity, it takes the stage ~6.4 sec to move the entire span. The timeout should be longer than this.
    _term_char = '\n'
    _min_angle = 2e-3
    _min_step = 2e-3
    _max_vel = 430  # Degrees per second
    _pulses_per_rev = 143360
    _counts_conversion = _pulses_per_rev/360
    _limits = (-720, 720)
    velocity_percent = 100
    # velocity = (velocity_percent/100) * _max_vel

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.velocity = (self.velocity_percent/100) * self._max_vel
        self.threadlock = Mutex()
        self._home_offset = 0
        self._position = 0

    def on_activate(self):
        """
        Initialization performed during activation of the module.
        """

        self.rm = visa.ResourceManager()
        self._motor_device = self.rm.open_resource(resource_name=self.resource_name,
                                                   write_termination='\n',
                                                   read_termination='\r\n',
                                                   baud_rate=self._baud_rate,
                                                   timeout=self._timeout)
        # self.get_home_offset()
        self._position = self.get_pos()
        return 0

    def on_deactivate(self):
        """
        Deinitialisation performed during deactivation of the module.
        """
        try:
            self._motor_device.close()
        except visa.VisaIOError:
            pass
        return 0

    def get_constraints(self):
        """
        Retrieve the hardware constrains from the motor device.

        @return dict: dict with constraints for the sequence generation and GUI

        Provides all the constraints for the xyz stage  and rot stage (like total
        movement, velocity, ...)
        Each constraint is a tuple of the form
            (min_value, max_value, stepsize)
        """
        constraints = OrderedDict()

        rot = {}
        rot['unit'] = '°'
        rot['pos_min'] = self._min_angle
        rot['pos_step'] = self._min_step
        rot['vel_max'] = self._max_vel

        # assign the parameter container to a name which will identify it
        constraints[rot['label']] = rot
        return constraints

    def move_rel(self, angle):
        """
        Moves stage by a given angle (relative movement)

        @param angle relative movement in deg

        @return dict velocity: Dictionary with final position in deg
        """
        if abs(angle) < self._min_step:
            self.log.warning('Desired step "{0}" is too small. Minimum is "{1}"'
                             .format(angle, self._min_step))
            return self.get_pos()
        new_angle = self._position + angle
        if self._angle_in_limits(new_angle):
            return self._move(angle=angle, mode='rel')
        else:
            return self.get_pos()

    def move_abs(self, angle):
        """
        Moves stage to an absolute angle (absolute movement)

        @param dict target position in deg

        @return dict velocity: Dictionary with final position in deg
        """
        angle = angle % 360  # The motor accepts absolute movements only from 0 to 359.99 degrees
        return self._move(angle=angle, mode='abs')

    def abort(self):
        """
        Stops movement of the stage
        @return int: error code (0:OK, -1:error)
        """
        # The command is 'Ams', but it is not clear if this unit supports this option.
        # From the manual it seems like it should support, but when queried it answers that the command is
        # not supported. Anyhow, it is not crucial at the moment. - Dan

        self.log.warn('ELL14 file does not support an abort option')
        return -1

    def get_pos(self, param_list=None):
        """
        Gets current position of the rotation stage

        @param list param_list: List with axis name

        @return dict pos: Dictionary with axis name and pos in deg    """
        # constraints = self.get_constraints()
        answer = self._query('0gp')
        if answer is Errors:
            return 'VISA error'
        else:
            self._position = self._angle_from_reply(answer)
            return self._position

    def get_status(self, param_list=None):
        """
        Get the status of the position

        @param list param_list: optional, if a specific status of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                status is asked.

        @return dict status:   · 0 - idle, not currently executing any instructions
                        · 1 - executing a home instruction
                        · 10 - executing a manual move (i.e. the manual control knob is turned)
                        · 20 - executing a move absolute instruction
                        · 21 - executing a move relative instruction
                        · 22 - executing a move at constant speed instruction
                        · 23 - executing a stop instruction (i.e. decelerating)
                                """
        status_reply = self._query('0gs')
        if status_reply is Errors:
            return 'VISA Error'
        else:
            status_code, status = self._get_status_code(status_reply)
            return status_code, {0: 'Status code ' + str(status_code) + ': ' + status}

    def go_home(self):
        """
        Calibrates the rotation motor to go home

        @param list param_list: Dictionary with axis name

        @return dict pos: Dictionary with axis name and pos in deg
        """
        # Last byte in the command sets the direction of motion. 0 for clockwise, 1 for counter.
        # Motor can go in both direction, but for simplicity here it is just hardcoded to go clockwise
        # (shouldn't matter at the moment) - Dan
        reply = self._query('0ho0')
        if reply is Errors:
            self.log.error('VISA write error. ELL14 failed to go home')
            return Errors.HOME
        else:
            return self._angle_from_reply(reply=reply)

    def calibrate(self, param_dict=None):
        """ Calibrates the stage.

        @param dict param_list: param_list: optional, if a specific calibration
                                of an axis is desired, then the labels of the
                                needed axis should be passed in the param_list.
                                If nothing is passed, then all connected axis
                                will be calibrated.

        @return int: error code (0:OK, -1:error)

        After calibration the stage moves to home position which will be the
        zero point for the passed axis. The calibration procedure will be
        different for each stage.
        """
        # I am not sure what this was originally intended for, but currently it is offsets the home position of the
        # stage (what is defined as 0 deg), by the angle given.
        # Setting an angle of alpha, shifts the current home position to alpha,
        # so that the "old" home position is now at -alpha
        if 'angle' in param_dict.keys():
            angle = param_dict['angle']
        else:
            self.log.info('Parameter angle missing from dictionary. Home was not offset.')
            return 0
        err = self._query('0so'+self._angle_to_hex(angle=angle))
        if err is Errors:
            self.log.error('ELL14 failed to offset home position.')
            return Errors.OFFSET
        else:
            self._home_offset = self.get_home_offset()
            return self._home_offset

    def get_home_offset(self):
        return self._angle_from_reply(self._query('0go'))

    def get_velocity(self, param_list=None):
        """
        Asks current value for velocity.

        @return velocity: velocity in % of max power applied to the driver
        """
        answer = self._query('0gv')
        if answer is Errors:
            if answer == Errors.WRITE:
                self.log.error('VISA write error')
            elif answer == Errors.READ:
                self.log.error('VISA read error')
            return 'VISA Error'
        else:
            self.velocity_percent = int(answer[3:], 16)
            self.velocity = (self.velocity_percent/100) * self._max_vel
            return self.velocity

    def set_velocity(self, vel):
        """
        Write new value for velocity.

        @param target velocity in % of max power applied to the driver

        @return target velocity in % of max power applied to the driver
        """
        if vel < 50 or vel > 100:
            self.log.error('Velocity must be 50-100 (percent of maximum power). Velocity did not change.')
            return self.velocity_percent
        vel_hex = hex(vel)[2:]
        answer = self._query('0sv'+vel_hex)
        if answer is Errors:
            if answer == Errors.WRITE:
                self.log.error('VISA write error')
            elif answer == Errors.READ:
                self.log.error('VISA read error')
        else:
            self.velocity = self.get_velocity()
            self.velocity_percent = int(100 * self.velocity / self._max_vel)
        return self.velocity_percent

    ######################### internal methods ##################################

    def _write(self, string):
        '''
        sending a command to the rotation stage,
        '''
        try:
            self._motor_device.write(string)
            return 0
        except visa.VisaIOError as exc:
            self.log.error('ELL14 write error: ' + str(exc))
            return Errors.WRITE

    def _read(self):
        '''
        This method reads the answer from the motor!
        '''
        try:
            return self._motor_device.read()
        except visa.VisaIOError as exc:
            self.log.error('ELL14 read error: ' + str(exc))
            return Errors.READ

    def _query(self, string):
        '''
        this method combines writing a command and reading the answer
        @param list list: list encoded command

        @return answer float: answer of motor coded in a single float
        '''
        try:
            return self._motor_device.query(string)
        except visa.VisaIOError as exc:
            self.log.error('ELL14 write error: ' + str(exc))
            return Errors.QUERY

    def _motor_stopped(self):
        '''
        checks if the rotation stage is still moving
        @return: bool stopped: True if motor is not moving, False otherwise'''

        stopped = True
        status = self.get_status()
        if status:
            stopped = False
        return stopped

    @staticmethod
    def _dec_to_hex(num):
        num = int(num)
        return bitstring.BitArray('int:32=' + str(num)).hex.upper()

    def _hex_to_dec(self, hexa_num):
        try:
            dec = bitstring.BitArray('hex:32=' + hexa_num).int
        except bitstring.CreationError:
            self.log.error('Input for hex_to_dec is not a valid 32 bit hexadecimal')
            return -1
        return dec

    def _angle_to_hex(self, angle):
        # return self._dec_to_hex(self._counts_conversion * (angle % 360))
        return self._dec_to_hex(self._counts_conversion * angle)

    def _hex_to_angle(self, hexa_num):
        # return round(self._hex_to_dec(hexa_num) / self._counts_conversion, 3) % 360
        return round(self._hex_to_dec(hexa_num) / self._counts_conversion, 3)

    def _angle_from_reply(self, reply):
        if len(reply) == 11:
            return self._hex_to_angle(reply[3:])
        elif reply.startswith('0GS'):
            status_code, status = self._get_status_code(reply)
            return 'Status code: ' + str(status_code) + ', ' + status
        else:
            self.log.error('ELL14 did not send position')
            return Errors.GENERAL

    @staticmethod
    def _get_status_code(self, reply):
        status_codes_dict = {0: 'OK',
                             3: 'Command error or not supported',
                             9: 'Busy',
                             12: 'Out of range'}
        if reply.startswith('0GS'):
            status_code = int(reply[3:], 16)
            if status_code in status_codes_dict.keys():
                status = status_codes_dict[status_code]
            else:
                status = 'see manual'
            return status_code, status
        else:
            return reply, None

    def _move(self, angle, mode):
        if mode == 'rel':
            command_string = '0mr'
        elif mode == 'abs':
            command_string = '0ma'
        else:
            self.log.error('Move mode must be rel or abs, did not move')
            return self._position
        reply = self._query(command_string + self._angle_to_hex(angle=angle))
        if self._angle_from_reply(reply=reply) is float:
            self._position = self._angle_from_reply(reply=reply)
        return self._angle_from_reply(reply=reply)

    def _angle_in_limits(self, angle):
        if self._limits[0] < angle < self._limits[1]:
            return True
        else:
            self.log.error('Requested position of range of ELL14, stage not moved.')
            return False

    @staticmethod
    def _error_handler(self, message):
        # Not implemented at the moment
            return message


class Errors(Enum):
    GENERAL = 0
    WRITE = 1
    READ = 2
    HOME = 3
    OFFSET = 4
    OUT_OF_RANGE = 5
    QUERY = 6
    UNKNOWN = 99
