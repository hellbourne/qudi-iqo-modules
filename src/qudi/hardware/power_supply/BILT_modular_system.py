# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware file to control BiLT power supply devices.

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

import socket
from core.module import Base
from core.configoption import ConfigOption
from core.util.helpers import byte_to_utf8, utf8_to_byte
from interface.power_supply_interface import PowerSupplyInterface
from interface.power_supply_interface import PowerSupplyConstraints
from interface.power_supply_interface import PowerSupplyMode


class BiltPowerSupply(Base, PowerSupplyInterface):
    """ Hardware control class to controls BiLT power supply devices.
        It implements a modular design, with designated classes for BiLT modules, groups and a communication class.
        The Communication class creates a socket connection and has the standard write, read and query methods.
        BiLT modules are automatically loaded on startup.
        Each BiLT module is an instance of the BiltModule class; it has its own designated communication methods, which
        already sends the required preamble for addressing a specific module ('iX;').
        All the module-specific methods are in the module class (e.g. set_current, set_sat_voltage, get_voltage, etc.).
        Channel groups defined in the BiLT are automatically loaded and added as instances of the Group class.
        The Group class at the moment only has on/off/get_state methods, which are the primary operations done with a
        group.
    """

    _modclass = 'BILT_modular_system'
    _modtype = 'hardware'
    _ip_address = ConfigOption('ip_address', missing='error')
    _port = ConfigOption('port', missing='error')
    module = {}
    group = {}

    def on_activate(self):
        """ Initialization performed during activation of the module. """
        self.connection = Communication(log=self.log, ip_address=self._ip_address, port=self._port)
        # self._connect_socket()
        self.get_groups()
        # self.get_modules()

    def on_deactivate(self):
        """ Deinitialization performed during deactivation of the module."""
        self.connection.close()
        return

    def get_constraints(self):

        constraints = PowerSupplyConstraints()
        constraints.supported_modes = PowerSupplyMode.CURRENT
        return constraints

    def get_groups(self):
        reply_array = self._query('p:list?').rsplit(sep=',')
        for counter, value in enumerate(reply_array):
            if not counter % 2:
                number = int(value)
                label = reply_array[counter+1].replace('"', '')
                self.group[label] = Group(connection=self.connection, log=self.log, number=number, label=label)
        return self.group

    def get_modules(self):
        reply_array = self._query('i:list?').rsplit(sep=';')
        for value in reply_array:
            number_str, model = value.rsplit(sep=',')
            number = int(number_str)
            self.module[number] = BiltModule(connection=self.connection, log=self.log,
                                             number=number, model=model)
        return self.module

    def _write(self, string):
        self.connection.write(string)

    def _read(self):
        return self.connection.read()

    def _query(self, string):
        self._write(string)
        return self._read()


class BiltModule:
    """A class representing a single BiLT channel"""

    def __init__(self, connection, number, log, model=None):
        super().__init__()
        self.connection = connection
        self.log = log
        self.number = number
        self.model = model
        self.state = self.get_state()
        self.voltage = self.get_voltage()
        self.current = self.get_current()
        self.sat_voltage = self.get_sat_voltage()
        self.name = self.get_name()

    def on(self):
        self._write('output on')
        return self.get_state()

    def off(self):
        self._write('output off')
        return self.get_state()

    def get_name(self):
        self.name = self._query('name')
        return self.name

    def set_current(self, current):
        self._write('curr {0}'.format(current))
        self.current = current

    def get_current(self):
        self.current = self._query('curr')
        return self.current

    def set_sat_voltage(self, voltage):
        self._write('volt:sat {0}'.format(voltage))

    def get_sat_voltage(self):
        if self.model == '2812':
            self.sat_voltage = self._query('volt:sat')
            return self.sat_voltage
        else:
            self.sat_voltage = 'NaN'
            return self.sat_voltage

    def get_voltage(self):
        self.voltage = self._query('meas:volt')
        return self.voltage

    def get_state(self):
        self.state = self._query('output')
        return self.state

    def _write(self, string):
        self.connection.write('i{0}; {1}'.format(self.number, string))

    def _read(self):
        return self.connection.read()

    def _query(self, string):
        return self.connection.query('i{0}; {1}?'.format(self.number, string))


class Group:

    """A class representing a group of channels, defined as such in the BiLT"""

    def __init__(self, connection, log, number, label=None):
        super().__init__()
        self.connection = connection
        self.log = log
        self.number = number
        self.label = label
        self.state = self.get_state()

    def on(self):
        self._write('p:state on')
        return self.get_state()

    def off(self):
        self._write('p:state off')
        return self.get_state()

    def get_state(self):
        states = ['ND', 0, 1, 'WARNING', 'ALARM', 'TSTOP']
        self.state = states[int(self._query('p:stat'))]
        return self.state

    def set_current(self, current, resistance):
        voltage = current*resistance
        self.set_voltage(voltage)
        return self.get_voltage()

    def set_voltage(self, voltage):
        state = self.get_state()
        if not state:
            self.on()
        command = 'volt {}'.format(voltage)  # command may be 'i3; volt V'.format(V)
        # bilt.group['source_12V']._write(command)
        self._write(command)

    def set_voltage_off(self):
        state = self.get_state()
        if state:
            self.set_voltage(0)
            self.off()

    def get_voltage(self):
        command = 'meas:volt'
        return self._query(command)

    def _write(self, string):
        self.connection.write('p{0}; {1}'.format(self.number, string))

    def _query(self, string):
        return self.connection.query('p{0}; {1} ?'.format(self.number, string))


class Communication:

    def __init__(self, log, ip_address, port):

        self.log = log
        self._ip_address = ip_address
        self._port = port
        self._idn = self.connect_socket()

    def connect_socket(self):
        socket.setdefaulttimeout(3)
        try:
            self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.timeout:
            self.log.error("Socket timeout while trying to connect BiLT")
        self.soc.connect((self._ip_address, self._port))
        return self.query('*IDN?')

    def close(self):
        self.soc.close()

    def write(self, string):
        try:
            self.soc.send(utf8_to_byte(string + '\n'))
        except socket.timeout or ConnectionAbortedError as error:
            if error == socket.timeout:
                self.log.error('Socket timed out')
                return -1
            else:
                self._idn = self.connect_socket()
                self.log.error('Connection has been disrupted but has been reconnected.\nPlease try again.')
                return 0

    def read(self):
        return byte_to_utf8(self.soc.recv(1024)).split('\n')[0]

    def query(self, string):
        if self.write(string):
            return -1
        else:
            return self.read()

