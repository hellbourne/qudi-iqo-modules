# -*- coding: utf-8 -*-

"""
This file contains a gui for the laser controller logic.

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

import numpy as np
import os
import pyqtgraph as pg
import time

from qudi.core.connector import Connector
from qudi.util import units
from qudi.util.colordefs import QudiPalettePale as palette
from qudi.core.module import GuiBase
from qudi.interface.diode_laser_interface import DiodeMode, LaserState
from PySide2 import QtCore
from PySide2 import QtWidgets
from qudi.util import uic



class TimeAxisItem(pg.AxisItem):
    """ pyqtgraph AxisItem that shows a HH:MM:SS timestamp on ticks.
        X-Axis must be formatted as (floating point) Unix time.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enableAutoSIPrefix(False)

    def tickStrings(self, values, scale, spacing):
        """ Hours:Minutes:Seconds string from float unix timestamp. """
        return [time.strftime("%H:%M:%S", time.localtime(value)) for value in values]


class LaserWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_laser_hwp.ui')

        # Load it
        super(LaserWindow,self).__init__()
        uic.loadUi(ui_file, self)
        self.show()


class CalibrationWindow(QtWidgets.QMainWindow):
    """ Create the calibration control windows based on the *.ui file."""

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_laser_hwp_cal.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)


class LaserGUI(GuiBase):
    """ FIXME: Please document
    """

    ## declare connectors
    laserlogic = Connector(interface='LaserHWPLogic')

    sigLaser = QtCore.Signal(bool)
    sigDiodePower = QtCore.Signal(int)
    sigLaserPower = QtCore.Signal(float)
    sigDiodeMode = QtCore.Signal(str)

    sigHWPangle = QtCore.Signal(float)
    sigHWPhome = QtCore.Signal()

    sigRunHWP = QtCore.Signal(bool)
    sigApplyCalibration = QtCore.Signal()
    sigCalibratePhotodiode = QtCore.Signal(float)

    # HWP related signals
    sigStartHwpScan = QtCore.Signal()
    sigStopHwpScan = QtCore.Signal()
    sigContinueHwpScan = QtCore.Signal()
    sigClearData = QtCore.Signal()
    sigFitChanged = QtCore.Signal(str)
    sigSaveMeasurement = QtCore.Signal(str, list, list)
    sigHwpSweepParamsChanges = QtCore.Signal(int, int, float)
    sigStartMeasure = QtCore.Signal()
    sigStopMeasure = QtCore.Signal()


    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.powerValueChanged = False
        self.hwpAngleChanged = False

    def on_activate(self):
        """ Definition and initialisation of the GUI plus staring the measurement.
        """
        self._laser_logic = self.laserlogic()

        #####################
        # Configuring the dock widgets
        # Use the inherited class 'CounterMainWindow' to create the GUI window
        self._mw = LaserWindow()

        # Setup dock widgets
        self._mw.setDockNestingEnabled(True)
        self._mw.actionReset_View.triggered.connect(self.restoreDefaultView)

        self._mw.start_meas_Action.triggered.connect(self.start_clicked)

        # set up plot
        self._mw.plotWidget = pg.PlotWidget(
            axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self._mw.pwContainer.layout().addWidget(self._mw.plotWidget)

        plot1 = self._mw.plotWidget.getPlotItem()
        plot1.setLabel('left', 'power', units='W', color=palette.c1.name())
        plot1.setLabel('bottom', 'Time', units=None)

        plot2 = pg.ViewBox()
        plot1.scene().addItem(plot2)
        plot1.getAxis('right').linkToView(plot2)
        plot2.setXLink(plot1)

        self.curves = {}
        colorlist = (palette.c2, palette.c3, palette.c4, palette.c5, palette.c6)
        i = 0
        for name in self._laser_logic.data:
            if name != 'time':
                curve = pg.PlotDataItem()
                if name == 'power':
                    curve.setPen(palette.c1)
                    plot1.addItem(curve)
                else:
                    curve.setPen(colorlist[(2*i) % len(colorlist)])
                    plot2.addItem(curve)
                self.curves[name] = curve
                i += 1

        self.plot1 = plot1
        self.plot2 = plot2
        self.updateViews()
        self.plot1.vb.sigResized.connect(self.updateViews)

        self.sigStartMeasure.connect(self._laser_logic.start_query_loop)
        self.sigStopMeasure.connect(self._laser_logic.stop_query_loop)

        self.updateButtonsEnabled()

        #######################
        # Configuring HWP window
        self.init_calibration_ui()

        self._mw.action_Calibration.triggered.connect(self.show_calibration)

        if self._laser_logic.laser_state == 1:
            self._mw.laserButton.setText('Laser: ON')
            self._mw.laserButton.setChecked(True)
            self._mw.laserButton.setStyleSheet('')
        elif self._laser_logic.laser_state == 0:
            self._mw.laserButton.setText('Laser: OFF')
            self._mw.laserButton.setChecked(False)
        else:
            self._mw.laserButton.setText('Laser: ?')
        self._mw.laserButton.clicked.connect(self.changeLaserState)
        self.sigLaser.connect(self._laser_logic.set_laser_state)
        self.sigDiodePower.connect(self._laser_logic.set_diode_power)
        self.sigLaserPower.connect(self._laser_logic.set_laser_power)
        self.sigDiodeMode.connect(self._laser_logic.set_diode_mode)

        # HWP stage controls
        self.sigHWPangle.connect(self._laser_logic.set_hwp_angle)
        self.sigHWPhome.connect(self._laser_logic._hwp_stage.go_home)


        # HWP related control/values-changes signals to logic
        self.sigStartHwpScan.connect(self._laser_logic.start_hwp_sweep, QtCore.Qt.QueuedConnection)
        self.sigStopHwpScan.connect(self._laser_logic.stop_hwp_sweep, QtCore.Qt.QueuedConnection)
        self.sigContinueHwpScan.connect(self._laser_logic.continue_hwp_sweep, QtCore.Qt.QueuedConnection)
        self.sigClearData.connect(self._laser_logic.clear_hwp_sweep, QtCore.Qt.QueuedConnection)
        # self.sigDoFit.connect(self._laser_logic.do_fit, QtCore.Qt.QueuedConnection)
        self.sigSaveMeasurement.connect(self._laser_logic.save_hwp_data, QtCore.Qt.QueuedConnection)


        # Marking the initial mode on startup. This is a dirty fix for now, because I don't think I can query the laser
        # to ask its mode, or if it is working.
        self._mw.cwRadioButton.setChecked(self._laser_logic.diode_mode == 'cw')
        self._mw.extRadioButton.setChecked(self._laser_logic.diode_mode == 'external')
        self._mw.intRadioButton.setChecked(self._laser_logic.diode_mode == 'internal')

        self._mw.setHWPangle.setValue(self._laser_logic.hwp_angle)
        self._mw.setHWPangle.valueChanged.connect(self.update_from_hwp_angle_spin_box)
        self._mw.setHWPhome.clicked.connect(self.homeHWP)
        self._mw.hwpAnglelabel.setText('{0:5.2f} deg'.format(self._laser_logic.hwp_angle))

        self._mw.diodeModeButtonGroup.buttonClicked.connect(self.change_diode_mode)
        self._mw.setDiodePowerSpinBox.setValue(self._laser_logic.diode_power)
        self._mw.setPowerDoubleSpinBox.setValue(self._laser_logic.laser_power)
        self._mw.setDiodePowerSpinBox.editingFinished.connect(self.update_from_diode_power_spin_box)
        self._mw.setPowerDoubleSpinBox.editingFinished.connect(self.update_from_power_spin_box)
        self._mw.setPowerDoubleSpinBox.valueChanged.connect(self.update_from_power_spin_box_aux)


        # Update signals coming from the logic:
        self._laser_logic.sigUpdate.connect(self.updateGui)
        self._laser_logic.sigHwpPlotUpdated.connect(self.update_hwp_plot, QtCore.Qt.QueuedConnection)
        self._laser_logic.sigHwpStateUpdated.connect(self.update_hwp_status, QtCore.Qt.QueuedConnection)
        self._laser_logic.sigHwpFitUpdated.connect(self.update_fit, QtCore.Qt.QueuedConnection)

    def on_deactivate(self):
        """ Deactivate the module properly.
        """
        self.sigStartMeasure.disconnect()
        self.sigStopMeasure.disconnect()
        self._cal.action_run_stop.triggered.disconnect()
        self._cal.action_resume.triggered.disconnect()
        self._mw.close()

    def show(self):

        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def restoreDefaultView(self):
        """ Restore the arrangement of DockWidgets to the default
        """
        # Show any hidden dock widgets
        # self._mw.adjustDockWidget.show()
        self._mw.plotDockWidget.show()

        # re-dock any floating dock widgets
        # self._mw.adjustDockWidget.setFloating(False)
        self._mw.plotDockWidget.setFloating(False)

        # Arrange docks widgets
        # self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(1), self._mw.adjustDockWidget)
        self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(2), self._mw.plotDockWidget)

    @QtCore.Slot()
    def updateViews(self):
        """ Keep plot views for left and right axis identical when resizing the plot widget. """
        # view has resized; update auxiliary views to match
        self.plot2.setGeometry(self.plot1.vb.sceneBoundingRect())

        # need to re-update linked axes since this was called incorrectly while views had different
        # shapes. (probably this should be handled in ViewBox.resizeEvent)
        self.plot2.linkedViewChanged(self.plot1.vb, self.plot2.XAxis)

    @QtCore.Slot(bool)
    def changeLaserState(self, on):
        """ Disable laser power button and give logic signal.
            Logic reaction to that signal will enable the button again.
        """
        self._mw.laserButton.setEnabled(False)
        self.sigLaser.emit(on)

    # @QtCore.Slot(bool)
    # def changeShutterState(self, on):
    #     """ Disable laser shutter button and give logic signal.
    #         Logic reaction to that signal will enable the button again.
    #     """
    #     self._mw.shutterButton.setEnabled(False)
    #     self.sigShutter.emit(on)

    @QtCore.Slot(QtWidgets.QAbstractButton)
    def change_diode_mode(self, buttonId):
        """ Process signal from diode mode radio button group. """
        cw = self._mw.cwRadioButton.isChecked() and self._mw.cwRadioButton.isEnabled()
        external = self._mw.extRadioButton.isChecked() and self._mw.extRadioButton.isEnabled()
        internal = self._mw.intRadioButton.isChecked() and self._mw.intRadioButton.isEnabled()
        if cw and not external and not internal:
            self.sigDiodeMode.emit('cw')
        elif external and not cw and not internal:
            self.sigDiodeMode.emit('external')
        elif internal and not cw and not external:
            self.sigDiodeMode.emit('internal')
        else:
            self.log.error('How did you mess up the radio button group?')

    @QtCore.Slot()
    def updateButtonsEnabled(self):
        """ Logic told us to update our button states, so set the buttons accordingly. """
        self._mw.laserButton.setEnabled(self._laser_logic.laser_can_turn_on)
        if self._laser_logic.laser_state == 1:
            self._mw.laserButton.setText('Laser: ON')
            self._mw.laserButton.setChecked(True)
            self._mw.laserButton.setStyleSheet('')
        elif self._laser_logic.laser_state == 0:
            self._mw.laserButton.setText('Laser: OFF')
            self._mw.laserButton.setChecked(False)
        else:
            self._mw.laserButton.setText('Laser: ?')

        self._mw.cwRadioButton.setEnabled(self._laser_logic.laser_can_cw)
        self._mw.extRadioButton.setEnabled(self._laser_logic.laser_can_ext)
        self._mw.intRadioButton.setEnabled(self._laser_logic.laser_can_int)

        if self._laser_logic.module_state() == 'locked':
            self._mw.start_meas_Action.setText('Stop measure')
            self._mw.start_meas_Action.setChecked(True)
        else:
            self._mw.start_meas_Action.setText('Start measure')
            self._mw.start_meas_Action.setChecked(False)

    @QtCore.Slot()
    def updateGui(self):
        """ Update labels, the plot and button states with new data. """
        self._mw.powerLabel.setText('{0:6.3f} mW'.format(1000 * self._laser_logic.laser_power))
        self._mw.hwpAnglelabel.setText('{0:5.2f} deg'.format(self._laser_logic.hwp_angle))
        self._cal.pdVolt_Label.setText('{0:6.1f}'.format(1000 * self._laser_logic.pd_voltage))

        self.updateButtonsEnabled()
        for name, curve in self.curves.items():
            curve.setData(x=self._laser_logic.data['time'], y=self._laser_logic.data[name])

    @QtCore.Slot()
    def update_from_power_spin_box(self):
        """ The user has changed the spinbox, update all other values from that. """
        if self.powerValueChanged:
            self.sigLaserPower.emit(self._mw.setPowerDoubleSpinBox.value())
            self.powerValueChanged = False

    @QtCore.Slot()
    def update_from_power_spin_box_aux(self):
        self.powerValueChanged = True

    @QtCore.Slot()
    def update_from_diode_power_spin_box(self):
        """ The user has changed the spinbox, update all other values from that. """
        self.sigDiodePower.emit(self._mw.setDiodePowerSpinBox.value())

    @QtCore.Slot()
    def update_from_hwp_angle_spin_box(self):
        """ The user has changed the HWP angle spinbox, update all other values from that. """
        self.sigHWPangle.emit(self._mw.setHWPangle.value())

    @QtCore.Slot()
    def homeHWP(self):
        """ Disable laser power button and give logic signal.
            Logic reaction to that signal will enable the button again.
        """
        self.sigHWPhome.emit()


    # @QtCore.Slot()
    # def updateFromSpinBox(self):
    #     """ The user has changed the spinbox, update all other values from that. """
    #     self._mw.setValueVerticalSlider.setValue(self._mw.setValueDoubleSpinBox.value())
    #     cur = self._mw.currentRadioButton.isChecked() and self._mw.currentRadioButton.isEnabled()
    #     pwr = self._mw.powerRadioButton.isChecked() and  self._mw.powerRadioButton.isEnabled()
    #     if pwr and not cur:
    #         self.sigPower.emit(self._mw.setValueDoubleSpinBox.value())
    #     elif cur and not pwr:
    #         self.sigCurrent.emit(self._mw.setValueDoubleSpinBox.value())
    #
    # @QtCore.Slot()
    # def updateFromSlider(self):
    #     """ The user has changed the slider, update all other values from that. """
    #     cur = self._mw.currentRadioButton.isChecked() and self._mw.currentRadioButton.isEnabled()
    #     pwr = self._mw.powerRadioButton.isChecked() and self._mw.powerRadioButton.isEnabled()
    #     if pwr and not cur:
    #         lpr = self._laser_logic.laser_power_range
    #         self._mw.setValueDoubleSpinBox.setValue(
    #             lpr[0] + self._mw.setValueVerticalSlider.value() / 100 * (lpr[1] - lpr[0]))
    #         self.sigPower.emit(
    #             lpr[0] + self._mw.setValueVerticalSlider.value() / 100 * (lpr[1] - lpr[0]))
    #     elif cur and not pwr:
    #         self._mw.setValueDoubleSpinBox.setValue(self._mw.setValueVerticalSlider.value())
    #         self.sigCurrent.emit(self._mw.setValueDoubleSpinBox.value())

    def start_clicked(self):
        """ Handling the Start button to stop and restart the counter.
        """
        if self._laser_logic.module_state() == 'locked':
            self._mw.start_meas_Action.setText('Start measure')
            self.sigStopMeasure.emit()
        else:
            self._mw.start_meas_Action.setText('Stop measure')
            self.sigStartMeasure.emit()
        return self._laser_logic.module_state()

    def init_calibration_ui(self):
        self._cal = CalibrationWindow()

        # Setup dock widgets
        self._cal.setDockNestingEnabled(True)
        self._cal.actionReset_View.triggered.connect(self.restoreDefaultView)

        # set up plot
        self.hwp_plot = pg.PlotDataItem(self._laser_logic.hwp_angles,
                                          self._laser_logic.hwp_curve,
                                          pen=pg.mkPen(palette.c1, style=QtCore.Qt.DotLine),
                                          symbol='o',
                                          symbolPen=palette.c1,
                                          symbolBrush=palette.c1,
                                          symbolSize=7)
        self.hwp_fit = pg.PlotDataItem(self._laser_logic.hwp_fit_x,
                                              self._laser_logic.hwp_fit_y,
                                              pen=pg.mkPen(palette.c2))

        self._cal.hwp_PlotWidget.addItem(self.hwp_plot)
        self._cal.hwp_PlotWidget.addItem(self.hwp_fit)
        self._cal.hwp_PlotWidget.setLabel('left', 'Power', units='W', color=palette.c1.name())
        self._cal.hwp_PlotWidget.setLabel('bottom', 'Angle', units='deg')

        self.updateViews()

        self.updateButtonsEnabled()

        self._cal.action_run_stop.triggered.connect(self.run_stop_hwp)
        self._cal.action_resume.triggered.connect(self.resume_hwp)

        # Set range of spinboxes
        self._cal.startDeg_spinBox.setMinimum(0)
        self._cal.startDeg_spinBox.setMaximum(359)
        self._cal.stopDeg_spinBox.setMinimum(1)
        self._cal.stopDeg_spinBox.setMaximum(360)
        self._cal.stepDeg_spinBox.setMinimum(0.001)
        self._cal.stepDeg_spinBox.setMaximum(100)
        # Getting values from logic
        self._cal.startDeg_spinBox.setValue(self._laser_logic.sweep_start)
        self._cal.stopDeg_spinBox.setValue(self._laser_logic.sweep_stop)
        self._cal.stepDeg_spinBox.setValue(self._laser_logic.sweep_step)
        self._cal.progressBar.setValue(0)
        self._cal.time_label.setText('0')
        self._cal.calibrated_label.setText(self._laser_logic.update_calibration_status())

        # Connecting spinboxes
        self._cal.startDeg_spinBox.editingFinished.connect(self.change_sweep_params)
        self._cal.stopDeg_spinBox.editingFinished.connect(self.change_sweep_params)
        self._cal.stepDeg_spinBox.editingFinished.connect(self.change_sweep_params)

        self.sigHwpSweepParamsChanges.connect(self._laser_logic.set_sweep_parameters,
                                             QtCore.Qt.QueuedConnection)
        self._cal.calHwpButton.clicked.connect(self.apply_calibration)
        self._cal.pdCal_pushButton.clicked.connect(self.calibrate_photodiode)
        self._cal.pdCal_Label.setText('{0:6.3f} mW/V'.format(self._laser_logic.volt_to_watt * 1000))

        self._laser_logic.sigHwpParameterUpdated.connect(self.update_hwp_parameters, QtCore.Qt.QueuedConnection)
        self.sigApplyCalibration.connect(self._laser_logic.apply_calibration, QtCore.Qt.QueuedConnection)
        self.sigCalibratePhotodiode.connect(self._laser_logic.calibrate_photodiode, QtCore.Qt.QueuedConnection)
        self._laser_logic.sigHwpCalibrated.connect(self.update_calibration_message, QtCore.Qt.QueuedConnection)
        # self._laser_logic.sigPhotodiodeCalibrate.connect

        # self._laser_logic.sigUpdate.connect(self.updateGui)

    def show_calibration(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._cal)
        self._cal.activateWindow()
        self._cal.raise_()

    def run_stop_hwp(self, is_checked):
        if is_checked:
            self._cal.action_run_stop.setEnabled(False)
            self._cal.action_resume.setEnabled(False)
            self.sigStartHwpScan.emit()
        else:
            self._cal.action_run_stop.setEnabled(False)
            self._cal.action_resume.setEnabled(False)
            self.sigStopHwpScan.emit()
        return

    def resume_hwp(self, is_checked):
        if is_checked:
            self._cal.action_run_stop.setEnabled(False)
            self._cal.action_resume.setEnabled(False)
            self.sigContinueHwpScan.emit()
        else:
            self._cal.action_run_stop.setEnabled(False)
            self._cal.action_resume.setEnabled(False)
            self.sigStopHwpScan.emit()

    def update_hwp_plot(self, hwp_curve_x, hwp_curve_y):
        self.hwp_plot.setData(hwp_curve_x, hwp_curve_y)
        self._cal.progressBar.setValue(self.get_progress())
        self._cal.time_label.setText(str(self.get_time()))

    def clear_hwp_data(self):
        self.sigClearData.emit()
        return

    def update_hwp_status(self, is_running):
        self._cal.action_run_stop.blockSignals(True)
        self._cal.action_resume.blockSignals(True)
        if is_running:
            self._cal.action_resume.setEnabled(False)
            self._cal.action_run_stop.setEnabled(True)
            self._cal.action_run_stop.setChecked(True)
            self._cal.action_resume.setChecked(True)
        else:
            self._cal.action_resume.setEnabled(True)
            self._cal.action_resume.setChecked(False)
            self._cal.action_run_stop.setEnabled(True)
            self._cal.action_run_stop.setChecked(False)
        self._cal.action_run_stop.blockSignals(False)
        self._cal.action_resume.blockSignals(False)
        return

    def update_fit(self, x_data, y_data, result_str_dict):
        """ Update the shown fit. """
        # display results as formatted text
        self._cal.fitResultsTextBrowser.clear()
        try:
            formatted_results = units.create_formatted_output(result_str_dict)
        except:
            formatted_results = 'this fit does not return formatted results'
        self._cal.fitResultsTextBrowser.setPlainText(formatted_results)

        # check which Fit method is used and remove or add again the
        # hwp_fit_image, check also whether a hwp_fit_image already exists.
        self.hwp_fit.setData(x=x_data, y=y_data)

        self._cal.hwp_PlotWidget.getViewBox().updateAutoRange()
        return

    def change_sweep_params(self):
        """ Change start, stop and step degree of rotation sweep """
        start = self._cal.startDeg_spinBox.value()
        stop = self._cal.stopDeg_spinBox.value()
        step = self._cal.stepDeg_spinBox.value()
        self.sigHwpSweepParamsChanges.emit(start, stop, step)
        return

    def update_hwp_parameters(self, param_dict):
        """ Update the parameter display in the GUI.

        @param param_dict:
        @return:

        Any change event from the logic should call this update function.
        The update will block the GUI signals from emitting a change back to the
        logic.
        """
        signals_dict = {'sweep_start': self._cal.startDeg_spinBox,
                        'sweep_stop': self._cal.stopDeg_spinBox,
                        'sweep_step': self._cal.stepDeg_spinBox}
        for key, value in signals_dict.items():
            param = param_dict.get(key)
            if param is not None:
                value.blockSignals(True)
                value.setValue(param)
                value.blockSignals(False)
        return

    def get_progress(self):
        elapsed_points = self._laser_logic.elapsed_points
        total_points = len(self._laser_logic.hwp_angles)
        return int(100*elapsed_points/total_points)

    def get_time(self):
        return int(self._laser_logic.elapsed_time)

    def apply_calibration(self):
        self.sigApplyCalibration.emit()
        # self._cal.calibrated_label.setText(self._laser_logic.update_calibration_status())

    def update_calibration_message(self, msg):
        self._cal.calibrated_label.setText(msg)

    def calibrate_photodiode(self):
        powermeter = self._cal.pm_doubleSpinBox.value()
        if powermeter:
            # self.sigCalibratePhotodiode.emit(powermeter)
            new_calibration = self._laser_logic.calibrate_photodiode(powermeter)
            self._cal.pdCal_Label.setText('{0:6.3f} mW/V'.format(new_calibration*1000))






