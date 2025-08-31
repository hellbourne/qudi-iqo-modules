from hardware.swabian_instruments import TimeTagger as tt
import time
import numpy as np
import matplotlib.pyplot as plt
from logic.save_logic import SaveLogic
import datetime


from logic.generic_logic import GenericLogic
from core.connector import Connector
from core.configoption import ConfigOption



class MagnetScanFunctions(GenericLogic):

    save_logic = Connector(interface='SaveLogic')
    scanner = Connector(interface='ConfocalScannerInterface')
    serialNum = ConfigOption('serialNum', '386', missing='warn')


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.anc_interface = kwargs['anc350']
        # self.anc_interface = self._scanner()

        self.file_prefix = 'C:\\Data\\Measurements\\magnet scan\\z='
        self.file_path = ''
        self.ranges = dict()
        self.ranges['x'] = [0, 0]
        self.ranges['y'] = [0, 0]
        self.pixels = 10
        self.frequency = 500
        self.time_per_pix = 0.3
        self._stop = False

    def on_activate(self):
        self._save_logic = self.save_logic()
        serial = self.serialNum
        self.anc_interface = self.scanner()
        self.anc_interface.connect_device(serial)
        self.z_position = self.anc_interface.get_scanner_position('z', serial=self.serialNum)

    def on_deactivate(self):
        pass

    def initiate_tagger(self):
        self.tagger = tt.createTimeTagger()
        self.combined_channel = tt.Combiner(tagger=self.tagger, channels=[0, 1])
        self.counter = tt.Countrate(tagger=self.tagger, channels=[self.combined_channel.getChannel()])

    def set_scan_parameters(self, frequency=None, pixels=None, time_per_pix=None):
        if frequency is not None:
            self.frequency = frequency
        if self.frequency is not None:
            self.anc_interface.set_frequency(0, self.frequency, serial=self.serialNum)
            self.anc_interface.set_frequency(1, self.frequency, serial=self.serialNum)
        if pixels is not None:
            self.pixels = pixels
        if time_per_pix is not None:
            self.time_per_pix = time_per_pix

    def set_scan_range(self,x=None,y=None):
        if x is not None:
            self.ranges['x'] = x
        if y is not None:
            self.ranges['y'] = y

        # the range is set to be the same length in x and y
        axis = ['x','y']
        self.ranges[axis[1]][1] = self.ranges[axis[1]][0] + (self.ranges[axis[0]][1] - self.ranges[axis[0]][0])

        limit_axis_1 = self.anc_interface._scanner_position_ranges[1][1]
        if self.ranges[axis[1]][1] > limit_axis_1:
            self.ranges[axis[1]][1] = limit_axis_1
            self.ranges[axis[1]][0] = limit_axis_1 - (self.ranges[axis[0]][1] - self.ranges[axis[0]][0])

    def set_slice(self, z_position):
        self.z_position = z_position
        self.anc_interface.scanner_set_position(z=z_position, serial=self.serialNum)

    def create_path(self):
        axis = ['x','y']
        axis_values = {}
        for axis_name in axis:
            axis_values[axis_name] = np.linspace(start=self.ranges[axis_name][0], stop=self.ranges[axis_name][1],
                                                 num=self.pixels)
        back_map = []
        path = []
        axis0_last = None
        axis1_last = None
        for j in range(self.pixels):
            for i in range(self.pixels):
                if (j % 2) == 1:
                    i = self.pixels - 1 - i
                back_map.append((i, j))
                new_pos = {}
                if not axis_values[axis[0]][i] == axis0_last:
                    new_pos[axis[0]] = axis_values[axis[0]][i]
                if not axis_values[axis[1]][j] == axis1_last:
                    new_pos[axis[1]] = axis_values[axis[1]][j]
                path.append(new_pos)
                axis0_last, axis1_last = axis_values[axis[0]][i], axis_values[axis[1]][j]
        return path, back_map

    def scan_from_path(self, path, back_map):
        self.stop(val=False)
        data_array = np.zeros([self.pixels, self.pixels])
        for n in range(len(path)):

            if self._stop:
                break

            try:
                xp = path[n]['x']
            except KeyError:
                xp = None
            try:
                yp = path[n]['y']
            except KeyError:
                yp = None
            self.anc_interface.scanner_set_position(x=xp, y=yp, serial=self.serialNum)
            data_array[back_map[n]] = self.measure_fluorescence()

        return data_array

    def draw_and_save_plot(self, data_array, plot=False, save_tag=''):
        # get current z_position (in case it was changed without the command set_slice)

        self.z_position = self.anc_interface.get_scanner_position('z', serial=self.serialNum)
        z_formatted = "{:.{}f}".format(1000 * self.z_position[0], 2)
        filelabel = z_formatted + '_mm_' + save_tag
        file_path = self._save_logic.get_path_for_module('Magnet Scan')
        timestamp = datetime.datetime.now()
        # filename = timestamp.strftime('%Y%m%d-%H%M-%S' + '_' + filelabel)

        # file_path = self.file_prefix + z_formatted + '_mm_' + save_tag + '.png'

        axis = ['x', 'y']
        plot_axis = {}
        plot_mesh = {}
        pix_size = (self.ranges[axis[0]][1] - self.ranges[axis[0]][0]) / (self.pixels - 1)  # in m
        for axis_name in axis:
            plot_axis[axis_name] = np.linspace(start=self.ranges[axis_name][0] - pix_size / 2,
                                               stop=self.ranges[axis_name][1] + pix_size / 2, num=self.pixels + 1)

        plot_mesh[axis[0]], plot_mesh[axis[1]] = np.meshgrid(plot_axis[axis[0]], plot_axis[axis[1]])

        fig = plt.figure()

        plt.pcolormesh(plot_mesh[axis[0]], plot_mesh[axis[1]], np.transpose(data_array))
        plt.colorbar()
        plt.ylabel(axis[0] + ' [m]')
        plt.ylabel('Magnet scan - fluorescence')
        title = save_tag + z_formatted + ' mm'
        plt.title(title)
        # filename = filelabel
        # file_path_png = file_path + '\\' + filename + '.png'
        # plt.savefig(file_path_png)


        params = dict()
        params['x'] = self.ranges['x']
        params['y'] = self.ranges['y']
        params['z'] = self.anc_interface.get_scanner_position('z',serial=self.serialNum)
        params['time per pixel'] = self.time_per_pix
        params['pixels'] = self.pixels

        header = ''
        if save_tag is not None:
            header += save_tag
            header += '\n'
        for entry, param in params.items():
            if isinstance(param, float):
                header += '{0}: {1:.16e}\n'.format(entry, param)
            else:
                header += '{0}: {1}\n'.format(entry, param)
        header += '\n'
        # file_path_csv = file_path + '\\' + filename + '.csv'
        # np.savetxt(file_path_csv, X=data_array, delimiter=',', comments='#', header=header)
        data_dict = dict()
        data_dict['Counts per pixel'] = data_array
        self._save_logic.save_data(data_dict,
                                   filepath=file_path,
                                   parameters=params,
                                   filelabel=filelabel,
                                   fmt='%.6e',
                                   delimiter='\t',
                                   timestamp=timestamp,
                                   plotfig=fig)
        if plot is True:
            plt.show()
        else:
            plt.close()

    def free_tagger(self):
        tt.freeTimeTagger(self.counter)

    def measure_fluorescence(self):
        self.counter.clear()
        time.sleep(self.time_per_pix)
        count_rate = self.counter.getData()
        return int(count_rate[0])

    def run_single_scan(self, plot=False, save_tag=None):
        path, back_map = self.create_path()
        data_array = self.scan_from_path(path, back_map)
        self.draw_and_save_plot(data_array, plot=plot, save_tag=save_tag)
        return data_array

    def stop(self, val=True):
        if val:
            self._stop = True
        else:
            self._stop = False
        return self._stop


# example run

# scanner = MagnetScanFunctions()
# scanner.initiate_tagger()
# scanner.set_scan_range(x=[5000e-6,9000e-6], y=[8000e-6])
# # if moving in z
# scanner.set_slice(z_position=5000e-6)
# # change scan parameters - pixels, speed, time_per_pixel
# scanner.set_scan_parameters(frequency=500, pixels=20, time_per_pix=0.5)
# data_array = scanner.run_single_scan(plot=False)
# scanner.free_tagger()
