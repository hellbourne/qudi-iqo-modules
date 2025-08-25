# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware file to control SRS SG devices.

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
import socket
from core.module import Base
from core.configoption import ConfigOption
from core.util.helpers import byte_to_utf8, utf8_to_byte
from interface.microwave_interface import MicrowaveInterface
from interface.microwave_interface import MicrowaveLimits
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge
#
#
# """Static functions used within methods in this file"""
#
#
# def byte_to_utf8(mybytes):
#     """
#     Convenience function for code refactoring
#     @param bytes mybytes the byte message to be decoded
#     @return the decoded string in uni code
#     """
#     return mybytes.decode()
#
#
# def utf8_to_byte(myutf8):
#     """
#     Convenience function for code refactoring
#     @param string myutf8 the message to be encoded
#     @return the encoded message in bytes
#     """
#     return myutf8.encode('utf-8')


class MicrowaveSGS(Base, MicrowaveInterface):
    """ Hardware control class to controls R&S SGS100 devices.  """

    _modclass = 'MicrowaveSGS100'
    _modtype = 'hardware'
    ip_addr = ConfigOption('sgs_ip_address', missing='error')
    port = ConfigOption('sgs_port', missing='error')

    def on_activate(self):
        """ Initialization performed during activation of the module. """
        socket.setdefaulttimeout(3)
        try:
            self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.timeout:
            self.log.error("socket timeout for SGS100")
        self.soc.connect((self.ip_addr, self.port))
        self.soc.send(utf8_to_byte('*IDN?\n'))
        self.name, self.model, self.serial, self.fw = byte_to_utf8(self.soc.recv(1024)).split('\n')[0].split(',')

    def on_deactivate(self):
        """ Deinitialization performed during deactivation of the module."""
        self.soc.close()
        return

    def cw_on(self):
        """
        Switches on cw microwave output.
        Must return AFTER the device is actually running.

        @return int: error code (0:OK, -1:error)
        """
        return self._write(':OUTP:STAT 1')

    def off(self):
        """
        Switches off cw microwave output.
        Must return AFTER the device is actually running.

        @return int: error code (0:OK, -1:error)
        """
        # self.set_mod(on=False)
        return self._write(':OUTP:STAT 0')

    def get_status(self):
        """
        Gets the current status of the MW source, i.e. the mode (cw, list or
        sweep) and the output state (stopped, running)

        @return str, bool: mode ['cw', 'list', 'sweep'], is_running [True, False]
        """
        self._write(':OUTP:STAT?')
        self.is_running = bool(int(self._read()))
        self._write(':SOUR:IQ:STAT?')
        self.is_iq = bool(int(self._read()))
        if self.is_iq:
            mode = 'MOD'
        else:
            mode = 'CW'
        return mode, int(self.is_running)

    def get_power(self):
        """ Gets the microwave output power.

        @return float: the power set at the device in dBm
        """
        self._write(':SOUR:POW:POW?')
        self.power = float(self._read())
        return self.power

    def get_frequency(self):
        """ Gets the frequency of the microwave output.

        @return float: frequency (in Hz), which is currently set for this device
        """
        self._write('SOUR:FREQ:CW?')
        self.freq = float(self._read())
        return self.freq

    def set_cw(self, frequency=None, power=None):
        """
        Configures the device for cw-mode and optionally sets frequency and/or power

        @param float frequency: frequency to set in Hz
        @param float power: power to set in dBm

        @return tuple(float, float, str): with the relation
            current frequency in Hz,
            current power in dBm,
            current mode
        """
        error = 0

        # disable modulation:

        # self.set_iq_mode(iq_mode='OFF')

        if frequency is not None:
            error = self._set_frequency(frequency)

        set_freq = self.get_frequency()

        if power is not None:
            error = self._set_power(power)

        actual_power = self.get_power()
        running, iq_status = self.get_status()

        return set_freq, actual_power, iq_status

    def set_mod(self, on=False):
        err = -1
        if type(on) is not bool:
            raise ValueError('set_mod expected boolean, received ', type(on))
        else:
            if on:
                self._write(':SOUR:IQ:SOUR ANAL') # This is an SGT option (w/baseband modulation capability)
                err = self._write(':SOUR:IQ:STAT ON')
                self.is_iq = True
            if not on:
                err = self._write(':SOUR:IQ:STAT OFF')
                self.is_iq = False
        return err

    def list_on(self):
        return -1

    def get_limits(self):
        """ Return the device-specific limits in a nested dictionary.

          @return MicrowaveLimits: Microwave limits object
        """
        limits = MicrowaveLimits()
        limits.supported_modes = (MicrowaveMode.CW, MicrowaveMode.MOD)

        limits.min_frequency = 1e6
        limits.max_frequency = 6e9

        limits.min_power = -120
        limits.max_power = 10 #This isn't the actual limit, but set here to protect the amplifier

        return limits


    """Methods required by the interface but are unused in this file"""

    def sweep_on(self):
        return

    def set_list(self, frequency=None, power=None):
        return

    def reset_listpos(self):
        return

    def set_sweep(self, start=None, stop=None, step=None, power=None):
        return

    def reset_sweeppos(self):
        return

    def set_ext_trigger(self, pol=TriggerEdge.RISING):
        return

    def trigger(self):
        return

    def _write(self, string):
        return self.soc.send(utf8_to_byte(string + '\n'))

    def _read(self):
        return byte_to_utf8(self.soc.recv(1024)).split('\n')[0]

    def _set_power(self, power):
        self._write(':SOUR:POW:POW %f' %float(power))
        return

    def _set_iq_mode(self, iq_mode='OFF'):
        if not iq_mode in ['ON', 'OFF']:
            raise ValueError('Wrong vector modulation state given: ' + iq_mode)
        else:
            self._write(':SOUR:IQ:STAT ' + iq_mode)
            if iq_mode:
                self._internal_mode = 'iq'
        return

    def _set_frequency(self, freq):
        self._write('SOUR:FREQ:CW ' + str(freq))
        return

    def _set_wideband_state(self, wb_mode = 'OFF'):
        self._write(':SOUR:IQ:WBST ' + wb_mode)
        return
