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
from qudi.core.module import Base
from qudi.core.configoption import ConfigOption
from qudi.util.mutex import Mutex
# from qudi.core.util.helpers import byte_to_utf8, utf8_to_byte
from qudi.interface.microwave_interface import MicrowaveInterface, MicrowaveConstraints
# from qudi.interface.microwave_interface import MicrowaveLimits
# from qudi.interface.microwave_interface import MicrowaveMode
# from qudi.interface.microwave_interface import TriggerEdge
from qudi.util.enums import SamplingOutputMode, TriggerEdge


#
# """Static functions used within methods in this file"""
#
#
def byte_to_utf8(mybytes):
    """
    Convenience function for code refactoring
    @param bytes mybytes the byte message to be decoded
    @return the decoded string in uni code
    """
    return mybytes.decode()


def utf8_to_byte(myutf8):
    """
    Convenience function for code refactoring
    @param string myutf8 the message to be encoded
    @return the encoded message in bytes
    """
    return myutf8.encode('utf-8')


class MicrowaveSGS(MicrowaveInterface):
    """ Hardware control class to controls R&S SGS100 devices.  """

    # _modclass = 'MicrowaveSGS100'
    # _modtype = 'hardware'
    ip_addr = ConfigOption('sgs_ip_address', missing='error')
    port = ConfigOption('sgs_port', missing='error')


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._thread_lock = Mutex()
        self._rm = None
        self._device = None
        self._constraints = None
        self._scan_power = -20
        self._scan_frequencies = None
        self._scan_sample_rate = 0.
        self._in_cw_mode = True

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
        self.log.info(self.name + self.model + self.serial + self.fw)

        freq_limits = (1e6, 6e9)
        self._constraints = MicrowaveConstraints(
            power_limits=(-120, 10),
            frequency_limits=freq_limits,
            scan_size_limits=(2, 2000),
            sample_rate_limits=(1e-6, 50e3),  # FIXME: Look up the proper specs for sample rate
            scan_modes=(SamplingOutputMode.JUMP_LIST,)
        )

        self._scan_frequencies = None
        self._scan_power = self._constraints.min_power
        self._scan_sample_rate = self._constraints.max_sample_rate
        self._in_cw_mode = True

    def on_deactivate(self):
        """ Deinitialization performed during deactivation of the module."""
        self.soc.close()
        return

    @property
    def constraints(self):
        return self._constraints

    @property
    def scan_power(self):
        """The microwave power in dBm used for scanning. Must implement setter as well.

        @return float: The currently set scanning microwave power in dBm
        """
        with self._thread_lock:
            return self._scan_power

    @property
    def scan_frequencies(self):
        """The microwave frequencies used for scanning. Must implement setter as well.

        In case of scan_mode == SamplingOutputMode.JUMP_LIST, this will be a 1D numpy array.
        In case of scan_mode == SamplingOutputMode.EQUIDISTANT_SWEEP, this will be a tuple
        containing 3 values (freq_begin, freq_end, number_of_samples).
        If no frequency scan has been specified, return None.

        @return float[]: The currently set scanning frequencies. None if not set.
        """
        with self._thread_lock:
            return self._scan_frequencies

    @property
    def scan_sample_rate(self):
        """Read-only property returning the currently configured scan sample rate in Hz.

        @return float: The currently set scan sample rate in Hz
        """
        with self._thread_lock:
            return self._scan_sample_rate

    @property
    def scan_mode(self):
        """Scan mode Enum. Must implement setter as well.

        @return SamplingOutputMode: The currently set scan mode Enum
        """
        with self._thread_lock:
            return SamplingOutputMode.JUMP_LIST

    @property
    def is_scanning(self):
        """Read-Only boolean flag indicating if a scan is running at the moment. Can be used together with
        module_state() to determine if the currently running microwave output is a scan or CW.
        Should return False if module_state() is 'idle'.

        @return bool: Flag indicating if a scan is running (True) or not (False)
        """
        with self._thread_lock:
            return (self.module_state() != 'idle') and not self._in_cw_mode

    @property
    def cw_power(self):
        """The CW microwave power in dBm. Must implement setter as well.

        @return float: The currently set CW microwave power in dBm.
        """
        with self._thread_lock:
            self._write(':SOUR:POW:POW?')
            self.power = float(self._read())
            return self.power

    @property
    def cw_frequency(self):
        """The CW microwave frequency in Hz. Must implement setter as well.

        @return float: The currently set CW microwave frequency in Hz.
        """
        with self._thread_lock:
            self._write('SOUR:FREQ:CW?')
            self.freq = float(self._read())
            return self.freq

    def configure_scan(self, power, frequencies, mode, sample_rate):
        """
        currently not used in the sgs100 module. needs further development if needed
        """
        return
        # with self._thread_lock:
            # Sanity checks
            # if self.module_state() != 'idle':
                # raise RuntimeError('Unable to configure frequency scan. Microwave output active.')
            # self._assert_scan_configuration_args(power, frequencies, mode, sample_rate)

            # configure scan according to scan mode
            # self._scan_sample_rate = sample_rate
            # self._scan_power = power
            # self._scan_frequencies = np.asarray(frequencies, dtype=np.float64)
            # self._write_list()

    def reset_scan(self):
        """
        not implemented in sgs100 right now.
        """
        return
        # with self._thread_lock:
        #     if self.module_state() == 'idle':
        #         return
        #     if self._in_cw_mode:
        #         raise RuntimeError('Can not reset frequency scan. CW microwave output active.')

    def cw_on(self):
        """
        Switches on cw microwave output.
        Must return AFTER the device is actually running.

        @return int: error code (0:OK, -1:error)
        """
        reply = self._write(':OUTP:STAT 1')
        status = self.get_status()[1]
        if status==1:
            self.module_state.lock()
        return reply

    def off(self):
        """
        Switches off cw microwave output.
        Must return AFTER the device is actually running.

        @return int: error code (0:OK, -1:error)
        """
        # self.set_mod(on=False)
        reply = self._write(':OUTP:STAT 0')
        status = self.get_status()[1]
        if status == 0:
            self.module_state.unlock()
        return reply

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

    def start_scan(self):
        """
        not implemented
        """
        return
        # with self._thread_lock:
        #     if self.module_state() != 'idle':
        #         if not self._in_cw_mode:
        #             return
        #         raise RuntimeError('Unable to start frequency scan. CW microwave output is active.')
        #     assert self._scan_frequencies is not None, \
        #         'No scan_frequencies set. Unable to start scan.'
        #
        #     self._in_cw_mode = False
        #     self._rf_on()
        #     self.module_state.lock()

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