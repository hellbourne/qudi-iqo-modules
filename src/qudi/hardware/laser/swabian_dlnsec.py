# -*- coding: utf-8 -*-
"""
This module controls Swabian Instruments Diode Lasers (now manufactured by Labs) lasers.

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

from core.module import Base
from core.configoption import ConfigOption
from core.statusvariable import StatusVar
import visa
from interface.diode_laser_interface import DiodeLaserInterface
import time


class SwabianDLnSec(Base, DiodeLaserInterface):
    """ Swabian nsec diode laser

    Example config for copy-paste:

    swabian_dlnsec:
        module.Class: 'swabian_dlnsec.SwabianDLnSec'
    """

    serial_interface = ConfigOption('interface', missing='error')

    # Laser status variables
    mode = StatusVar('mode', 'cw')
    laser_state = StatusVar('laser_state', 0)
    power = StatusVar('power', 5)
    # Internal trigger status variables
    repetition_rate = StatusVar('repetition_rate', 62745)
    duty_cycle = StatusVar('duty_cycle', 0.1)

    def __init__(self, **kwargs):
        """ """
        super().__init__(**kwargs)
        self.model = 'DLnsecXXXX'
        self.serial_num = 'YYYYY'
        self.rm = visa.ResourceManager()
        self.idn = 'DLnsecXXXX_YYYYY'
        self.resource = self.serial_interface
        self.power = 5

    def on_activate(self):
        """ Activate Module.
        """
        err_msg = 'Empty error message'
        try:
            self.laser_device = self.rm.open_resource(self.resource, read_termination='\n', write_termination='\n',
                                                      send_end=True)
            self.laser_device.timeout = 1000
            idn = self.laser_device.query('*IDN')
            if 'Lnsec' in idn:
                if idn.startswith('\r'):
                    idn = idn[1:]
                self.idn = idn
                error = 0
            else:
                error = -1
                err_msg = 'Device IDN at configured resource is not DLnsec'
        except visa.VisaIOError as e:
            error = -1
            err_msg = 'Laser is not connected at configured port\n' + e.args[0]

        if not error:
            (self.model, self.serial_num) = self.idn.split('_')
            self.log.info(self.model + ' laser found in ' + self.resource + ' and connected')

            # Applying the saved status of the laser
            self.set_power(self.power)
            time.sleep(0.1)
            self.set_diode_mode(self.mode)
            if self.laser_state:
                self.on()
            self.set_clock(self.repetition_rate)
            self.set_pulse_width(self.duty_cycle)

            return True
        else:
            self.laser_device.close()
            self.log.error(err_msg)
            return False

    def on_deactivate(self):
        """ Deactivate module
        """
        self.laser_device.close()
        self.rm.close()

    def _write(self, command):
        if type(command) is not str:
            self.log.error('Laser command must be string')
            return -1
        else:
            self.laser_device.write(command)
            return 0

    def _query(self, command):
        try:
            reply = self.laser_device.query(command)
            if reply.startswith('\r'):
                return reply[1:]
            else:
                return reply
        except visa.VisaIOError:
            self.log.error('Querying laser failed')
            return False

    def _read(self):
        try:
            reply = self.laser_device.read()
            if reply.startswith('\r'):
                return reply[1:]
            else:
                return reply
        except visa.VisaIOError:
            self.log.error('Querying laser failed')
            return False

    def on(self):
        self._write('*ON')
        self.laser_state = 1
        return

    def off(self):
        self._write('*OFF')
        self.laser_state = 0

    def set_power(self, power):
        if type(power) is not (int or float) in range(0, 100):
            self.log.error('Laser power setting must be a number in the range 0-100')
        else:
            if type(power) is float:
                power = round(power)
                self.log.warn('Laser power setting needs to be an integer, rounded to %.0f' % power)
            self._write('PWR %.0f' % power)
            self.power = self.get_power()
        return

    def get_power(self):
        return int(self._query('PWR?'))

    def set_cw(self):
        self._write('LAS')
        self.mode = 'cw'
        return

    def set_ext_trig(self):
        self._write('EXT')
        self.mode = 'external'
        return

    def set_int_trig(self):
        self._write('INT')
        self.mode = 'internal'
        return

    def identify(self):
        return self._query('*IDN')

    def reboot(self):
        self._write('*RBT')
        return

    def check_error(self):
        return self._query('ERR?')

    def set_clock(self, frequency=1000):
        """
        Set frequency in Hz, which is approximated to one of 5 available frequencies given by prescalers of the
        16 MHz internal clock
        """
        allowed_prescalers = [1, 8, 64, 256, 1024]
        prescaler = 16e6 / (255*frequency)
        self.clock_prescaler = allowed_prescalers[min(range(len(allowed_prescalers)),
                                                    key=lambda i: abs(allowed_prescalers[i] - prescaler))]
        self.repetition_rate = int(16e6 / (255 * self.clock_prescaler))
        self._write('PRE {0}'.format(self.clock_prescaler))
        self.log.info('DLnsec internal triggering set to closest allowed repetition rate: {0} Hz'
                      .format(self.repetition_rate))
        self.set_pulse_width(self.duty_cycle)
        return

    def get_clock(self):
        self.clock_prescaler = float(self._query('PRE?'))
        self.repetition_rate = int(16e6 / (255 * self.clock_prescaler))
        return self.repetition_rate

    def set_pulse_width(self, fraction):
        """Set a fraction from 0 to 1"""
        pulse_width = round(fraction * 255) # Converted duty cycle out of 255
        if pulse_width not in range(0, 256):
            self.log.error('Pulse width must be between 0 to 1')
        self._write('WID {0}'.format(pulse_width))
        self.duty_cycle = pulse_width / 255
        self.pulse_time = (1/self.repetition_rate)*self.duty_cycle
        return

    def get_pulse_width(self):
        width = round(int(self._query('WID?')) / 255, 2)
        return width

    # @staticmethod
    def allowed_diode_modes(self):
        return ['cw', 'external', 'internal']

    def set_diode_mode(self, mode):
        if mode not in self.allowed_diode_modes():
            self.log.error('Diode laser operation mode incorrect, was not changed')
        else:
            if mode == 'cw':
                self.set_cw()
            elif mode == 'external':
                self.set_ext_trig()
            elif mode == 'internal':
                self.set_int_trig()
        return self.mode

    def get_diode_mode(self):
        return self.mode

    def get_laser_state(self):
        return self.laser_state
