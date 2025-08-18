# -*- coding: utf-8 -*-
"""
A hardware module for communicating with the fast counter FPGA.

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

# from interface.fast_counter_interface import FastCounterInterface
import numpy as np
import TimeTagger as tt
from core.module import Base
from core.configoption import ConfigOption
import os


class TimeTaggerBase(Base):
    """ Hardware class to create a Time Tagger instance from Swabian Instruments.

    Example config for copy-paste:

    timetagger_base:
        module.Class: 'swabian_instruments.timetagger_base.TimeTaggerBase'
        channel_triggers: '{0: 1, 1: 1}'

    """
    _channel_triggers = ConfigOption('channel_triggers', '{0: 0.5, 1: 0.5}')

    def on_activate(self):
        """ Connect and configure the access to the FPGA.
        """
        self._tagger = tt.createTimeTagger()
        self._tagger.reset()

        self._channel_triggers = eval(self._channel_triggers)
        for ch, level in self._channel_triggers.items():
            self._tagger.setTriggerLevel(ch, level)

        self.log.info('TimeTagger instance initialized')

    def on_deactivate(self):
        """ Deactivate the FPGA.
        """