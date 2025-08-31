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

from interface.correlation_interface import CorrelationInterface
import numpy as np
import TimeTagger as tt
from core.module import Base
from core.configoption import ConfigOption
from core.connector import Connector


class TimeTaggerCorrelation(Base, CorrelationInterface):
    """ Hardware class to controls a Time Tagger from Swabian Instruments.

    Example config for copy-paste:

    fastcounter_timetagger:
        module.Class: 'swabian_instruments.timetagger_fast_counter.TimeTaggerFastCounter'
        timetagger_channel_apd_0: 0
        timetagger_channel_apd_1: 1
        timetagger_channel_detect: 2
        timetagger_channel_sequence: 3
        timetagger_sum_channels: 4

    """
    timetagger_base = Connector(interface='TimeTaggerBase')

    _channel_apd_0 = ConfigOption('timetagger_channel_apd_0', missing='error')
    _channel_apd_1 = ConfigOption('timetagger_channel_apd_1', missing='error')

    def on_activate(self):
        """ Connect and configure the access to the FPGA.
        """
        self._tt_base = self.timetagger_base()
        self._tagger = self._tt_base._tagger

        # self._tagger = tt.createTimeTagger()
        # self._tagger.reset()

        self._bin_width = 1000  # in picoseconds
        self._n_bins = int(1000)

        self.log.info('TimeTagger (correlation) configured to use  channels {0}, {1}'
                      .format(self._channel_apd_0, self._channel_apd_1))

        self.statusvar = 0
        self.configure(self._bin_width, self._n_bins)

    def get_constraints(self):
        """ Retrieve the hardware constrains from the Fast counting device.

        @return dict: dict with keys being the constraint names as string and
                      items are the definition for the constaints.

         The keys of the returned dictionary are the str name for the constraints
        (which are set in this method).

                    NO OTHER KEYS SHOULD BE INVENTED!

        If you are not sure about the meaning, look in other hardware files to
        get an impression. If still additional constraints are needed, then they
        have to be added to all files containing this interface.

        The items of the keys are again dictionaries which have the generic
        dictionary form:
            {'min': <value>,
             'max': <value>,
             'step': <value>,
             'unit': '<value>'}

        Only the key 'hardware_binwidth_list' differs, since they
        contain the list of possible binwidths.

        If the constraints cannot be set in the fast counting hardware then
        write just zero to each key of the generic dicts.
        Note that there is a difference between float input (0.0) and
        integer input (0), because some logic modules might rely on that
        distinction.

        ALL THE PRESENT KEYS OF THE CONSTRAINTS DICT MUST BE ASSIGNED!
        """

        constraints = dict()

        # the unit of those entries are seconds per bin. In order to get the
        # current binwidth in seonds use the get_binwidth method.
        constraints['binwidth min'] = 1e-12
        constraints['binwidth max'] = 1

        return constraints

    def on_deactivate(self):
        """ Deactivate the FPGA.
        """
        if self.module_state() == 'locked':
            self.correlator.stop()
        self.correlator.clear()
        self.correlator = None

    def configure(self, bin_width, n_bins):

        """ Configuration of the correlator.

        @param float bin_width: Length of a single time bin in the time trace
                                  histogram in nanoseconds.

        @param int n_bins: Number of bins to perform measurement.
        """
        self._bin_width = bin_width
        self._n_bins = int(n_bins)
        self.statusvar = 1

        self.correlator = tt.Correlation(
                                tagger=self._tagger,
                                channel_1=self._channel_apd_0,
                                channel_2=self._channel_apd_1,
                                binwidth=int(self._bin_width),
                                n_bins=self._n_bins)

        self.correlator.stop()

        return bin_width, n_bins

    def start_measure(self):
        """ Start the correlator. """
        self.module_state.lock()
        self.correlator.clear()
        self.correlator.start()
        self._tagger.sync()
        self.statusvar = 2
        return 0

    def stop_measure(self):
        """ Stop the correlator. """
        if self.module_state() == 'locked':
            self.correlator.stop()
            self.module_state.unlock()
        self.statusvar = 1
        return 0

    def restart_measure(self):
        self.stop_measure()
        self.start_measure()
        return 0

    def pause_measure(self):
        """ Pauses the current measurement.

        Correlator must be initially in the run state to make it pause.
        """
        if self.module_state() == 'locked':
            self.correlator.stop()
            self.statusvar = 3
        return 0

    def continue_measure(self):
        """ Continues the current measurement.

        If correlator is in pause state, then fast counter will be continued.
        """
        if self.module_state() == 'locked':
            self.correlator.start()
            self.count_triggers.start()
            self._tagger.sync()
            self.statusvar = 2
        return 0

    def get_data(self):
        """ Polls the current timetrace data from the correlator.

        @return numpy.array: 2 dimensional array of dtype = int64. This counter
                             is gated the the return array has the following
                             shape:
                                returnarray[gate_index, timebin_index]

        The binning, specified by calling configure() in forehand, must be taken
        care of in this hardware class. A possible overflow of the histogram
        bins must be caught here and taken care of.
        """
        elapsed_time = self.correlator.getCaptureDuration()*1e-12 # Gives the time in seconds
        data = np.array(self.correlator.getData(), dtype='int64')
        data_norm = np.array(self.correlator.getDataNormalized())
        time_bins = np.array(self.correlator.getIndex()*1e-3, dtype='int64')  # in nanoseconds

        info_dict = {'elapsed_time': elapsed_time}
        return time_bins, data, data_norm, info_dict
        # return time_bins, data, info_dict

    def get_status(self):
        """ Receives the current status of the correlator and outputs it as
            return value.

        0 = unconfigured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        return self.statusvar

    def get_binwidth(self):
        """ Returns the width of a single timebin in the correlation in nanoseconds. """
        return self._bin_width

