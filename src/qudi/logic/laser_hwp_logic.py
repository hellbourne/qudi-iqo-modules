# -*- coding: utf-8 -*-
"""
Laser management.

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
import numpy as np
from qtpy import QtCore

from collections import OrderedDict
from qudi.util.mutex import Mutex
from qudi.util.helpers import in_range
from qudi.core.connector import Connector
from qudi.core.statusvariable import StatusVar
from qudi.core.configoption import ConfigOption
from qudi.core.module import LogicBase

# from logic.generic_logic import GenericLogic
from qudi.interface.diode_laser_interface import DiodeMode, LaserState
from qudi.hardware.ni_x_series.ni_x_series_in_streamer import AnalogInputChannel


class LaserHWPLogic(LogicBase):
    """ Logic module aggregating multiple hardware switches.
    """
    diode_laser = Connector(interface='DiodeLaserInterface')
    hwp_stage = Connector(interface='MotorInterface')
    # fit_logic = Connector(interface='FitLogic')

    # Status variables
    # fc = StatusVar('fits', None)
    hwp_calibration = StatusVar('hwp_calibration', {})
    isCalibrated = StatusVar('isCalibrated', False)
    sweep_start = StatusVar('sweep_start', 0)
    sweep_stop = StatusVar('sweep_stop', 90)
    sweep_step = StatusVar('sweep_step', 1)
    volt_to_watt = StatusVar('pd_calibration', 0.00174)

    # Laser status variables, to be obtained upon activation from the hardware module
    laser_state = 0
    diode_mode = 'cw'
    diode_power = 5

    # Configurations
    _laser_read_channel = ConfigOption('laser_read_channel', b'/Dev1/ai0', missing='warn')
    _laser_read_voltage_range = ConfigOption('laser_read_voltage_range', [0.0, 5.0], missing='warn')
    _laser_read_sampling_freq = ConfigOption('laser_read_sampling_freq', 1000, missing='warn')
    _laser_read_samples = ConfigOption('laser_read_samples', 50, missing='warn')

    # Updated signals
    sigHwpElapsedTimeUpdated = QtCore.Signal(float, int)
    sigHwpPlotUpdated = QtCore.Signal(np.ndarray, np.ndarray)
    sigHwpStateUpdated = QtCore.Signal(bool)
    # sigHwpFitUpdated = QtCore.Signal(np.ndarray, np.ndarray, dict)
    sigHwpParameterUpdated = QtCore.Signal(dict)
    sigHwpCalibrated = QtCore.Signal(str)
    # sigPhotodiodeCalibrate = QtCore.Signal(float)

    # Internal signals
    sigNextPoint = QtCore.Signal()

    # Update signals, e.g. for GUI module
    sigUpdate = QtCore.Signal()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.threadlock = Mutex()
        self.queryInterval = 50

        # Attributes:
        self.laser_power = 1.0  # In units of mW
        self.hwp_angle = 0  # In degrees

        self.ai_channel = None
        self.elapsed_points = 0
        self.stopHWP = False
        # self.fit_parameters = {}
        self.recalibrated = False
        self.RequestedPowerOutOfRange = False
        self.Sweeping = False

    def on_activate(self):
        """ Prepare logic module for work.
        """
        # Declaring instances of interfacing modules
        self._diode_laser = self.diode_laser()
        self._hwp_stage = self.hwp_stage()
        # self._fit_logic = self.fit_logic()

        self.stopRequest = False
        self.bufferLength = 100
        self.data = {}
        self.set_up_power_acquisition()

        # Getting the previous laser status from the hardware module
        self.diode_power = self._diode_laser.power
        self.diode_mode = self._diode_laser.mode
        self.laser_state = self._diode_laser.laser_state

        # Getting the HWP angle from the hardware module
        self.hwp_angle = self._hwp_stage.get_pos()

        # delay timer for querying laser
        self.queryTimer = QtCore.QTimer()
        self.queryTimer.setInterval(self.queryInterval)
        self.queryTimer.setSingleShot(True)
        self.queryTimer.timeout.connect(self.check_laser_loop, QtCore.Qt.QueuedConnection)

        # get laser capabilities
        self.laser_can_turn_on = self.laser_state <= 1
        self.laser_can_cw = 'cw' in self._diode_laser.allowed_diode_modes()
        self.laser_can_ext = 'external' in self._diode_laser.allowed_diode_modes()
        self.laser_can_int = 'internal' in self._diode_laser.allowed_diode_modes()
        self.init_data_logging()
        # self.start_query_loop()

        # Initialize hwp sweep parameters
        self.hwp_angles = np.arange(start=self.sweep_start, stop=self.sweep_stop, step=self.sweep_step)
        self.hwp_curve = np.zeros(self.hwp_angles.size)
        # self.hwp_fit_x = self.hwp_angles
        # self.hwp_fit_y = self.hwp_curve
        self.update_calibration_status()

        self._initialize_hwp_plot()

        self.sigNextPoint.connect(self._get_hwp_point, QtCore.Qt.QueuedConnection)
        self.stopHWP = False
        return

    def on_deactivate(self):
        """ Deactivate modeule.
        """
        self.stop_query_loop()
        for i in range(5):
            time.sleep(self.queryInterval / 1000)
            QtCore.QCoreApplication.processEvents()

    @QtCore.Slot()
    def check_laser_loop(self):
        """ Get power, current, shutter state and temperatures from laser. """
        if self.stopRequest:
            self.module_state.unlock()
            self.stopRequest = False
            return
        qi = self.queryInterval
        try:
            self.laser_state = self._diode_laser.laser_state
            self.diode_power = self._diode_laser.power
            self.diode_mode = self._diode_laser.mode

            for k in self.data:
                self.data[k] = np.roll(self.data[k], -1)

            self.data['power'][-1] = self.get_laser_power()
            self.data['time'][-1] = time.time()

        except:
            qi = 3000
            self.log.exception("Exception in laser status loop, throttling refresh rate.")

        self.queryTimer.start(qi)
        self.sigUpdate.emit()

    @QtCore.Slot()
    def start_query_loop(self):
        """ Start the readout loop. """
        with self.threadlock:
            # Lock module
            if self.module_state() != 'locked':
                self.module_state.lock()
            else:
                self.log.warning('Laser logger is already running. Method call ignored.')
                return 0
            self.queryTimer.start(self.queryInterval)
            return

    @QtCore.Slot()
    def stop_query_loop(self):
        """ Stop the readout loop. """
        if self.module_state() == 'locked':
            with self.threadlock:
                self.stopRequest = True
        return

    def init_data_logging(self):
        """ Zero all log buffers. """
        self.data['power'] = np.ones(self.bufferLength) * self.get_laser_power()
        self.data['time'] = np.ones(self.bufferLength) * time.time()
        self.data['hwp_angle'] = np.ones(self.bufferLength)

    @QtCore.Slot(str)
    def set_diode_mode(self, operation_mode):
        """ Change whether the laser is controlled by dioe current or output power. """
        if operation_mode in self._diode_laser.allowed_diode_modes():
            self._diode_laser.set_diode_mode(operation_mode)
            self.diode_mode = operation_mode
            self.log.info('Changed diode operation mode to ' + operation_mode)
        else:
            self.log.error('Requested operation mode is not supported by diode laser')

    @QtCore.Slot(bool)
    def set_laser_state(self, state):
        """ Turn laser on or off. """
        if state:
            self._diode_laser.on()
        else:
            self._diode_laser.off()
        self.sigUpdate.emit()
        self.laser_state = self._diode_laser.get_laser_state()

    @QtCore.Slot(int)
    def set_diode_power(self, power):
        """ Set the output power of the diode laser, a number in the range of 0-100. """
        self._diode_laser.set_power(power)
        self.diode_power = self._diode_laser.get_power()

    def set_up_power_acquisition(self):
        self._laser_read_voltage_range = tuple(self._laser_read_voltage_range)
        self.ai_channel = AnalogInputChannel(channel=self._laser_read_channel,
                                             name='photodiode_output',
                                             termination='diff',
                                             voltage_range=self._laser_read_voltage_range,
                                             sample_freq=self._laser_read_sampling_freq,
                                             num_samples=self._laser_read_samples)

    def get_laser_power(self):
        self.pd_voltage, self.pd_dev = self.ai_channel.read_averaged()
        self.laser_power = self.pd_voltage * self.volt_to_watt
        self.laser_power_dev = self.pd_dev * self.volt_to_watt
        return self.laser_power

    def get_hwp_angle(self):
        self.hwp_angle = self._hwp_stage.get_pos()
        return self.hwp_angle

    def set_hwp_angle(self, angle):
        self._hwp_stage.move_abs(angle)
        self.get_hwp_angle()

    @QtCore.Slot()
    def apply_calibration(self):
        if not self.recalibrated:
            self.log.error('No calibration curve available, did not recalibrate')
            return -1
        # for key, value in self.fit_parameters.items():
        #     self.hwp_calibration[key] = value['value']
        self.hwp_calibration['Time of calibration'] = time.strftime('%c')
        self.hwp_calibration['Diode power'] = self.diode_power
        self.isCalibrated = True
        self.update_calibration_status()
        self.log.info('HWP laser power modulation was recalibrated')
        return

    @QtCore.Slot(float)
    def calibrate_photodiode(self, pm_power):
        # Photometer power is expected to be in mW, while the photodiode voltage is in V.
        # We want the calibration to be in W/V
        if pm_power and self.pd_voltage:
            self.volt_to_watt = (pm_power / 1000) / self.pd_voltage
            # self.sigPhotodiodeCalibrate.emit(self.volt_to_watt)
        else:
            self.log.warn('Photodiode voltage or photometer power are zero. Did not calibrate')
        return self.volt_to_watt

    def start_hwp_sweep(self):
        with self.threadlock:
            if self.Sweeping:
                self.log.error('Can not start HWP scan. Logic is already locked.')
                return -1
            self.Sweeping = True
            self._clearHwpData = False
            self.stopHWP = False
            # self.fc.clear_result()

            self.elapsed_time = 0.0
            self.elapsed_points = 0
            self._startTime = time.time()
            self.sigHwpElapsedTimeUpdated.emit(self.elapsed_time, self.elapsed_points)

            self.hwp_angles = np.arange(start=self.sweep_start, stop=self.sweep_stop, step=self.sweep_step)
            self.hwp_curve = np.array([])
            self.sigNextPoint.emit()
            self.sigHwpStateUpdated.emit(True)
            return 0

    def continue_hwp_sweep(self):
        with self.threadlock:
            if self.Sweeping:
                self.log.error('Can not start HWP scan. Logic is already locked.')
                return -1

            self.Sweeping = True
            self.stopHWP = False
            # self.fc.clear_results()

            self._startTime = time.time() - self.elapsed_time
            self.sigHwpElapsedTimeUpdated.emit(self.elapsed_time, self.elapsed_points)

            self.sigNextPoint.emit()
            self.sigHwpStateUpdated.emit(True)
            return 0

    def stop_hwp_sweep(self):
        with self.threadlock:
            if self.Sweeping:
                self.stopHWP = True
            self.sigHwpStateUpdated.emit(False)
            return 0

    def clear_hwp_sweep(self):
        with self.threadlock:
            if self.module_state() == 'locked':
                self._clearHwpData = True
            return

    def _initialize_hwp_plot(self):
        self.hwp_angles = np.arange(0, 91)
        self.hwp_curve = np.zeros(self.hwp_angles.size)
        # self.hwp_fit_x = np.arange(0, 91)
        # self.hwp_fit_y = np.zeros(self.hwp_fit_x.size)

        self.sigHwpPlotUpdated.emit(self.hwp_angles, self.hwp_curve)
        # self.fc.fit_list['Sine with offset']['use_settings'] = {}
        # self.fc.set_current_fit('Sine with offset')
        # current_fit = self.fc.current_fit
        # self.sigHwpFitUpdated.emit(self.hwp_fit_x, self.hwp_fit_y, {})
        return

    def _get_hwp_point(self):
        """ Gets a single HWP point for the plot

        (by angle from 0 to 360)
        """
        with self.threadlock:
            if not self.Sweeping:
                return
            # if self.module_state() != 'locked':
            #     return
            if self.stopHWP:
                self.stopHWP = False
                self.Sweeping = False
                # self.module_state.unlock()
                return

            if self._clearHwpData:
                self.elapsed_points = 0
                self._startTime = time.time()

            if self._clearHwpData:
                self.hwp_curve = np.array([])
            else:
                self.set_hwp_angle(self.hwp_angles[self.elapsed_points])
                time.sleep(0.1)
                self.hwp_curve = np.append(self.hwp_curve, self.get_laser_power())
                plot_angles = self.hwp_angles[0:len(self.hwp_curve)]
                # if self.elapsed_points > 5:
                #     self.do_fit(x_data=plot_angles, y_data=self.hwp_curve)
            self.elapsed_points += 1
            self.elapsed_time = time.time() - self._startTime
            self.sigHwpElapsedTimeUpdated.emit(self.elapsed_time, self.elapsed_points)
            self.sigHwpPlotUpdated.emit(plot_angles, self.hwp_curve)
            if self.elapsed_points >= len(self.hwp_angles):
                self.stopHWP = True
                self.recalibrated = True
                self.elapsed_points = 0
                self.sigHwpStateUpdated.emit(False)
            self.sigNextPoint.emit()
            return

    def save_hwp_data(self):
        return

    # @fc.constructor
    # def sv_set_fits(self, val):
    #     # Setup fit container
    #     fc = self.fit_logic().make_fit_container('HWP rotation', '1d')
    #     fc.set_units(['deg', 'W'])
    #     if isinstance(val, dict) and len(val) > 0:
    #         fc.load_from_dict(val)
    #     else:
    #         d1 = OrderedDict()
    #         d1['Sine with offset'] = {
    #             'fit_function': 'sine',
    #             'estimator': 'generic',
    #             'use_settings': {'amplitude': False,
    #                              'frequency': False,
    #                              'phase': False,
    #                              'offset': False}
    #             }
    #         default_fits = OrderedDict()
    #         default_fits['1d'] = d1
    #         fc.load_from_dict(default_fits)
    #     return fc
    #
    # @fc.representer
    # def sv_get_fits(self, val):
    #     """ save configured fits """
    #     if len(val.fit_list) > 0:
    #         return val.save_to_dict()
    #     else:
    #         return None
    #
    # def do_fit(self, x_data=None, y_data=None):
    #     """
    #     Execute the currently configured fit on the measurement data. Optionally on passed data
    #     """
    #     if (x_data is None) or (y_data is None):
    #         x_data = self.hwp_angles
    #         y_data = self.hwp_curve
    #
    #     self.hwp_fit_x, self.hwp_fit_y, result = self.fc.do_fit(x_data, y_data)
    #
    #     if result is None:
    #         result_str_dict = {}
    #     else:
    #         result_str_dict = result.result_str_dict
    #         del result_str_dict['Contrast'] # We don't need this fit parameter, it is relevant for Rabi and such
    #     self.sigHwpFitUpdated.emit(
    #         self.hwp_fit_x, self.hwp_fit_y, result_str_dict)
    #     self.fit_parameters = result_str_dict
    #     return
    #
    # def get_fit_functions(self):
    #     return list(self.fc.fit_list)

    def set_sweep_parameters(self, start, stop, step):
        """ Set the desired frequency parameters for list and sweep mode

        @param int start: start angle to set in deg
        @param int stop: stop angle to set in deg
        @param float step: step angle to set in deg

        @return int, int, float: current start_deg, current stop_deg, current step_deg
        """
        limits = {'start': (0, 359), 'stop': (1, 360), 'step': (0.001, 100)}

        # if self.module_state() != 'locked':
        if not self.Sweeping:
            if isinstance(start, int):
                self.sweep_start = in_range(start, 0, 359)
            if isinstance(stop, int) and isinstance(step, float):
                if stop <= start:
                    stop = start + step
                self.sweep_stop = in_range(stop, 1, 360)
                self.sweep_step = in_range(step, 0.001, 100)
        else:
            self.log.warning('set_sweep_parameters failed. HWP is sweeping.')

        param_dict = {'sweep_start': self.sweep_start, 'sweep_stop': self.sweep_stop, 'sweep_step': self.sweep_step}
        self.sigHwpParameterUpdated.emit(param_dict)
        return self.sweep_start, self.sweep_stop, self.sweep_step

    @QtCore.Slot(float)
    def set_laser_power(self, target_power):
        """ Set laser output power, in W. """
        calib_power = self.hwp_calibration['Diode power']
        # if not calib_power == self.diode_power:
        #     self.log.error('Current calibration fits diode power of {}'
        #                    ' but diode is currently on {}. Recalibrate or set diode to'
        #                    ' appropriate power level.'.format(calib_power, self.diode_power))
        #     return -1
        holding_time = 0.1
        epsilon = 5*10**-6
        delta = 10**-4
        initial_angle = self._hwp_stage.get_pos()
        target_angle = self._power_to_angle(target_power)
        self.set_hwp_angle(target_angle)

        if self.RequestedPowerOutOfRange:
            return 0

        time.sleep(holding_time)
        delta_power = self._delta_power(target_power)
        if abs(delta_power) > delta:
            self.set_hwp_angle(initial_angle)
            self.log.error('HWP uncalibrated, stage restored to initial position')
            return -1

        counter = 0
        while abs(delta_power) > epsilon:
            if counter > 10:
                self.set_hwp_angle(initial_angle)
                self.log.error('Unable to set desired power. Stage restored to initial position')
                return -1
            self._hwp_stage.move_rel(self._movement_increment(delta_power))
            time.sleep(holding_time)
            delta_power = self._delta_power(target_power)
            counter += 1
        return 0

    def _power_to_angle(self, power):
        # Power should be in Watts!!!
        try:
            shifted_power = (power-self.hwp_calibration['Offset'])/self.hwp_calibration['Amplitude']
            phi = self.hwp_calibration['Phase']
            omega = 2*np.pi*self.hwp_calibration['Frequency']
        except KeyError:
            self.log.error('HWP calibration is missing one or more parameters. Please recalibrate.')
            return
        self.RequestedPowerOutOfRange = False
        if shifted_power < -1:
            self.log.warn('Requested power is below the range, set to lowest power')
            shifted_power = -1
            self.RequestedPowerOutOfRange = True
        if shifted_power > 1:
            self.log.warn('Requested power is above the range, set to highest power')
            shifted_power = 1
            self.RequestedPowerOutOfRange = True
        angle = ((np.arcsin(shifted_power) - np.deg2rad(phi)) / omega)
        return angle

    def _delta_power(self, power):
        self.laser_power = self.get_laser_power()
        delta_power = power - self.laser_power
        return delta_power

    def _movement_increment(self, delta_power):
        current_angle = self._hwp_stage.get_pos()
        func_val = np.cos(2*np.pi*self.hwp_calibration['Frequency']*current_angle +
                          np.deg2rad(self.hwp_calibration['Phase']))
        increment = (delta_power / (2 * np.pi * self.hwp_calibration['Amplitude'] *
                                    self.hwp_calibration['Frequency'] *
                                    func_val))
        return increment

    def update_calibration_status(self):
        if not self.isCalibrated:
            msg = 'Uncalibrated!'
        else:
            try:
                msg = 'Calibrated for\ndiode power {}'.format(self.hwp_calibration['Diode power'])
            except KeyError:
                msg = 'Uncalibrated!'
        self.sigHwpCalibrated.emit(msg)
        return msg
