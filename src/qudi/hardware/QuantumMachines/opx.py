# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware interface for pulsing devices.

Copyright (c) 2021, the qudi developers. See the AUTHORS.md file at the top-level directory of this
distribution and on <https://github.com/Ulm-IQO/qudi-iqo-modules/>

This file is part of qudi.

Qudi is free software: you can redistribute it and/or modify it under the terms of
the GNU Lesser General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

Qudi is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along with qudi.
If not, see <https://www.gnu.org/licenses/>.
"""

import numpy as np
from qm import QuantumMachinesManager
from qudi.hardware.QuantumMachines.Config_OPX2 import config  # this is the config file from the folder

from qudi.core.configoption import ConfigOption
from qudi.core.statusvariable import StatusVar
from qudi.interface.pulser_interface import PulserInterface, PulserConstraints


class OPX(PulserInterface):
    """ Methods to control the QM OPX+ as a pulser

    Example config for copy-paste:

    opx:
        module.Class: 'QuantumMachines.opx.OPX'
        options:
            opx_ip: '132.77.54.180'
            cluster_name: 'Cluster_1'
            config: 'QuantumMachines.Config.config'
    """

    _opx_ip = ConfigOption('opx_ip', '132.77.54.180', missing='warn')
    _cluster_name = ConfigOption('cluster_name', 'Cluster_1', missing='warn')
    _qmm = ''
    _qm = ''
    _job = ''
    __current_status = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def on_activate(self):
        """ Establish connection to pulse streamer and tell it to cancel all operations """
        self._qmm = QuantumMachinesManager(host=self._opx_ip, cluster_name=self._cluster_name)  # should add the config file, too.
        self._qm = self._qmm.open_qm(config)  # this line configures the OPX with a config file from the folder

    def on_deactivate(self):
        self._qmm.close_all_qms()
        del self._qmm

    def get_constraints(self):
        """
        Retrieve the hardware constrains from the Pulsing device.

        @return constraints object: object with pulser constraints as attributes.

        Provides all the constraints (e.g. sample_rate, amplitude, total_length_bins,
        channel_config, ...) related to the pulse generator hardware to the caller.

            SEE PulserConstraints CLASS IN pulser_interface.py FOR AVAILABLE CONSTRAINTS!!!

        If you are not sure about the meaning, look in other hardware files to get an impression.
        If still additional constraints are needed, then they have to be added to the
        PulserConstraints class.

        Each scalar parameter is an ScalarConstraints object defined in core.util.interfaces.
        Essentially it contains min/max values as well as min step size, default value and unit of
        the parameter.

        PulserConstraints.activation_config differs, since it contain the channel
        configuration/activation information of the form:
            {<descriptor_str>: <channel_set>,
             <descriptor_str>: <channel_set>,
             ...}

        If the constraints cannot be set in the pulsing hardware (e.g. because it might have no
        sequence mode) just leave it out so that the default is used (only zeros).

        # Example for configuration with default values:
        constraints = PulserConstraints()

        constraints.sample_rate.min = 10.0e6
        constraints.sample_rate.max = 12.0e9
        constraints.sample_rate.step = 10.0e6
        constraints.sample_rate.default = 12.0e9

        constraints.a_ch_amplitude.min = 0.02
        constraints.a_ch_amplitude.max = 2.0
        constraints.a_ch_amplitude.step = 0.001
        constraints.a_ch_amplitude.default = 2.0

        constraints.a_ch_offset.min = -1.0
        constraints.a_ch_offset.max = 1.0
        constraints.a_ch_offset.step = 0.001
        constraints.a_ch_offset.default = 0.0

        constraints.d_ch_low.min = -1.0
        constraints.d_ch_low.max = 4.0
        constraints.d_ch_low.step = 0.01
        constraints.d_ch_low.default = 0.0

        constraints.d_ch_high.min = 0.0
        constraints.d_ch_high.max = 5.0
        constraints.d_ch_high.step = 0.01
        constraints.d_ch_high.default = 5.0

        constraints.waveform_length.min = 80
        constraints.waveform_length.max = 64800000
        constraints.waveform_length.step = 1
        constraints.waveform_length.default = 80

        constraints.waveform_num.min = 1
        constraints.waveform_num.max = 32000
        constraints.waveform_num.step = 1
        constraints.waveform_num.default = 1

        constraints.sequence_num.min = 1
        constraints.sequence_num.max = 8000
        constraints.sequence_num.step = 1
        constraints.sequence_num.default = 1

        constraints.subsequence_num.min = 1
        constraints.subsequence_num.max = 4000
        constraints.subsequence_num.step = 1
        constraints.subsequence_num.default = 1

        # If sequencer mode is available then these should be specified
        constraints.repetitions.min = 0
        constraints.repetitions.max = 65539
        constraints.repetitions.step = 1
        constraints.repetitions.default = 0

        constraints.event_triggers = ['A', 'B']
        constraints.flags = ['A', 'B', 'C', 'D']

        constraints.sequence_steps.min = 0
        constraints.sequence_steps.max = 8000
        constraints.sequence_steps.step = 1
        constraints.sequence_steps.default = 0

        # the name a_ch<num> and d_ch<num> are generic names, which describe UNAMBIGUOUSLY the
        # channels. Here all possible channel configurations are stated, where only the generic
        # names should be used. The names for the different configurations can be customary chosen.
        activation_conf = OrderedDict()
        activation_conf['yourconf'] = {'a_ch1', 'd_ch1', 'd_ch2', 'a_ch2', 'd_ch3', 'd_ch4'}
        activation_conf['different_conf'] = {'a_ch1', 'd_ch1', 'd_ch2'}
        activation_conf['something_else'] = {'a_ch2', 'd_ch3', 'd_ch4'}
        constraints.activation_config = activation_conf
        """
        constraints = PulserConstraints()

        # The file formats are hardware specific.

        constraints.sample_rate.min = 1e9
        constraints.sample_rate.max = 1e9
        constraints.sample_rate.step = 0
        constraints.sample_rate.default = 1e9

        constraints.d_ch_low.min = 0.0
        constraints.d_ch_low.max = 0.0
        constraints.d_ch_low.step = 0.0
        constraints.d_ch_low.default = 0.0

        constraints.d_ch_high.min = 3.3
        constraints.d_ch_high.max = 3.3
        constraints.d_ch_high.step = 0.0
        constraints.d_ch_high.default = 3.3

        # sample file length max is not well-defined for PulseStreamer, which collates sequential
        # identical pulses into one.
        # Total number of not-sequentially-identical pulses which can be stored: 1 M.
        constraints.waveform_length.min = 1
        constraints.waveform_length.max = 134217728
        constraints.waveform_length.step = 1
        constraints.waveform_length.default = 1

        # the name a_ch<num> and d_ch<num> are generic names, which describe UNAMBIGUOUSLY the
        # channels. Here all possible channel configurations are stated, where only the generic
        # names should be used. The names for the different configurations can be customary chosen.
        activation_config = dict()
        activation_config['all'] = frozenset(
            {'d_ch1', 'd_ch2', 'd_ch3', 'd_ch4', 'd_ch5', 'd_ch6', 'd_ch7', 'd_ch8', 'd_ch9', 'd_ch10',
             'a_ch1', 'a_ch2', 'a_ch3', 'a_ch4', 'a_ch5', 'a_ch6', 'a_ch7', 'a_ch8', 'a_ch9', 'a_ch10'}
        )
        constraints.activation_config = activation_config

        return constraints

    def pulser_on(self, prog):
        """ Switches the pulsing device on.

        @return int: error code (0:OK, -1:error)
        """
        if prog:
            self._job = self._qm.execute(prog, duration_limit=0, data_limit=0, flags=["skip-loop-unrolling"])
            self.__current_status = 1
            return 0
        else:
            self.log.error('no program was defined for the OPX')
            self.pulser_off()  # not sure if this is necessary with OPX
            self.__current_status = -1
            return -1

    def pulser_off(self):
        """ Switches the pulsing device off.

        @return int: error code (0:OK, -1:error)
        """
        self.__current_status = 0
        if self._job:
            self._job.halt()
        # self._qm.set_io1_value(1)  # this is what Inbar was using, but job.halt should be more appropriate
        return

    def load_waveform(self, load_dict):
        """
        In the OPX this will actually not do anything, as the "waveform" will be defined in the "prog" variable
        defined in the predefined_methods
        """
        return

    def get_loaded_assets(self):
        """
        Also here the OPX will show nothing, unless we write something.
        """
        return

    def load_sequence(self, sequence_name):
        """
        Sequencing is not relevant for the OPX
        """
        self.log.debug('sequencing not relevant for the OPX')
        return

    def clear_all(self):
        """
        There is probably nothing stored in the OPX memory, so nothing to clear.
        """
        return

    def get_status(self):
        """
        Retrieves the status of the OPX
        """
        return

    def get_sample_rate(self):
        """ Get the sample rate of the pulse generator hardware

        @return float: The current sample rate of the device (in Hz)

        Do not return a saved sample rate in a class variable, but instead
        retrieve the current sample rate directly from the device.
        """
        return

    def set_sample_rate(self, sample_rate):
        """
        not relevant for OPX
        """
        self.log.debug('OPX sample rate cannot be configured')
        return

    def get_analog_level(self, amplitude=None, offset=None):
        """
        eventually write something here
        """
        return

    def set_analog_level(self, amplitude=None, offset=None):
        """
        eventually write something here
        """
        return

    def get_digital_level(self, low=None, high=None):
        """
        eventually write something here
        """
        return

    def set_digital_level(self, low=None, high=None):
        """"
        eventually write something here
        """
        return

    def get_active_channels(self, ch=None):
        """
        eventually write something here
        """
        return
    
    def set_active_channels(self, ch=None):
        """
        eventually write something here
        """
        return

    def write_waveform(self, name, analog_samples, digital_samples, is_first_chunk, is_last_chunk,
                       total_number_of_samples):
        """
        eventually write something here
        """
        return

    def write_sequence(self, name, sequence_parameters):
        """
        eventually write something here
        """
        return

    def get_waveform_names(self):
        """
        eventually write something here
        """
        return

    def get_sequence_names(self):
        """
        eventually write something here
        """
        return

    def delete_waveform(self, waveform_name):
        """
        eventually write something here
        """
        return

    def delete_sequence(self, sequence_name):
        """
        eventually write something here
        """
        return

    def get_interleave(self):
        """
        eventually write something here
        """
        return False

    def set_interleave(self, state=False):
        """
        eventually write something here
        """
        return False

    def reset(self):
        """
        no such command for the OPX
        """
        return

    def has_sequence_mode(self):
        """
        eventually write something here
        """
        return False