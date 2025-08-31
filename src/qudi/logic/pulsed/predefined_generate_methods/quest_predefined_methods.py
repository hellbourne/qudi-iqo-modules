import numpy as np
from logic.pulsed.pulse_objects import PulseBlock, PulseBlockEnsemble, PulseSequence
from logic.pulsed.pulse_objects import PredefinedGeneratorBase

"""
General Pulse Creation Procedure:
=================================
- Create at first each PulseBlockElement object
- add all PulseBlockElement object to a list and combine them to a
  PulseBlock object.
- Create all needed PulseBlock object with that idea, that means
  PulseBlockElement objects which are grouped to PulseBlock objects.
- Create from the PulseBlock objects a PulseBlockEnsemble object.
- If needed and if possible, combine the created PulseBlockEnsemble objects
  to the highest instance together in a PulseSequence object.
"""


def add_step_sequence(sequence, ensemble, repetitions, go_to):
    sequence.append(ensemble.name)
    sequence[-1].repetitions = repetitions
    sequence[-1].go_to = go_to
    next_step = go_to + 1
    return sequence, next_step


class BasicPredefinedGenerator(PredefinedGeneratorBase):
    """

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def pix_element(self, phase_shift=0):
        return self._get_iq_mix_element(length=self.rabi_period / 2, increment=0, amp=self.microwave_amplitude,
                                        freq=self.iq_freq_shift, phase=phase_shift)

    def piy_element(self, phase_shift=0):
        return self._get_iq_mix_element(length=self.rabi_period / 2, increment=0, amp=self.microwave_amplitude,
                                        freq=self.iq_freq_shift, phase=90 + phase_shift)

    def generate_simple_sin(self, name='simple_sin', length=1000e-9, amp=0.25,
                            freq=5e7, phase=0, num_of_points=50):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Create the readout PulseBlockEnsemble
        # Get necessary PulseBlockElements

        iq_element = self._get_iq_mix_element(length=length, increment=0, amp=amp, freq=freq, phase=phase)

        # Create PulseBlock and append PulseBlockElements
        signal_block = PulseBlock(name=name)
        signal_block.append(iq_element)
        created_blocks.append(signal_block)
        # Create PulseBlockEnsemble and append block to it
        signal_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        signal_ensemble.append((signal_block.name, 0))

        if self.sync_channel:
            # Create the last readout PulseBlockEnsemble including a sync trigger
            # Get necessary PulseBlockElements
            sync_element = self._get_sync_element()
            # Create PulseBlock and append PulseBlockElements
            sync_block = PulseBlock(name=name)
            sync_block.append(iq_element)
            sync_block.append(sync_element)
            created_blocks.append(sync_block)
            # Create PulseBlockEnsemble and append block to it
            sync_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
            sync_ensemble.append((sync_block.name, 0))
            created_ensembles.append(sync_ensemble)

        # add metadata to invoke settings later on
        signal_ensemble.measurement_information['alternating'] = False
        signal_ensemble.measurement_information['laser_ignore_list'] = list()
        signal_ensemble.measurement_information['units'] = ('s', '')
        signal_ensemble.measurement_information['number_of_lasers'] = num_of_points
        signal_ensemble.measurement_information['counting_length'] = 0

        # Append PulseSequence to created_sequences list
        created_ensembles.append(signal_ensemble)

        return created_blocks, created_ensembles, created_sequences

    def generate_pulsedodmr_iq(self, name='pulsedODMR', freq_start=2.82e9, freq_step=5e6, num_of_points=21):

        """

            """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Create frequency array
        freq_array = freq_start - self.microwave_frequency + np.arange(num_of_points) * freq_step

        # create the elements
        readout_element = self._get_laser_gate_element(length=self.laser_length,
                                                       increment=0)
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        delay_element = self._get_delay_gate_element()

        # Create block and append to created_blocks list
        pulsedodmr_block = PulseBlock(name=name)
        for mw_freq in freq_array:
            mw_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                                  increment=0,
                                                  amp=self.microwave_amplitude,
                                                  freq=mw_freq,
                                                  phase=0)
            pulsedodmr_block.append(mw_element)
            pulsedodmr_block.append(readout_element)
            pulsedodmr_block.append(delay_element)
            pulsedodmr_block.append(waiting_element)

        created_blocks.append(pulsedodmr_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((pulsedodmr_block.name, 0))

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = freq_array + self.microwave_frequency
        block_ensemble.measurement_information['units'] = ('Hz', '')
        block_ensemble.measurement_information['labels'] = ('Frequency', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        block_ensemble.measurement_information['microwave_frequency'] = self.microwave_frequency
        block_ensemble.measurement_information['iq_mixing'] = True

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_pulsed_demo(self, name='pulsed_demo', freq_start=50e6, freq_step=1e6,
                             num_of_points=10):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Create frequency array
        freq_array = freq_start + np.arange(num_of_points) * freq_step

        # create the elements
        waiting_element = self._get_idle_element(length=200e-9,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()

        start_element = self._get_trigger_element(10e-9, 0, 'd_ch0')
        click_element = self._get_trigger_element(100e-9, 0, 'd_ch1')

        # Create block and append to created_blocks list
        pulsedodmr_block = PulseBlock(name=name)
        for mw_freq in freq_array:
            mw_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                                  increment=0,
                                                  amp=self.microwave_amplitude,
                                                  freq=mw_freq,
                                                  phase=0)
            pulsedodmr_block.append(mw_element)
            # pulsedodmr_block.append(laser_element)
            # pulsedodmr_block.append(delay_element)
            pulsedodmr_block.append(start_element)
            pulsedodmr_block.append(waiting_element)
            pulsedodmr_block.append(click_element)
            pulsedodmr_block.append(waiting_element)
            pulsedodmr_block.append(click_element)
            pulsedodmr_block.append(waiting_element)
            pulsedodmr_block.append(click_element)
            pulsedodmr_block.append(start_element)
            pulsedodmr_block.append(waiting_element)
        created_blocks.append(pulsedodmr_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((pulsedodmr_block.name, 0))

        # Create and append sync trigger block if needed
        if self.sync_channel:
            sync_block = PulseBlock(name='sync_trigger')
            sync_block.append(self._get_sync_element())
            created_blocks.append(sync_block)
            block_ensemble.append((sync_block.name, 0))

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = freq_array
        block_ensemble.measurement_information['units'] = ('Hz', '')
        block_ensemble.measurement_information['labels'] = ('Frequency', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_trig_click(self, name='trig_click(', num_clicks=3, num_reps=10, wait_time=100e-9):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # create the elements
        waiting_element = self._get_idle_element(length=wait_time,
                                                 increment=0)
        start_element = self._get_trigger_element(10e-9, 0, 'd_ch0')
        click_element = self._get_trigger_element(10e-9, 0, 'd_ch1')

        # Create block and append to created_blocks list
        pulsedodmr_block = PulseBlock(name=name)
        trig = 0
        while trig < num_reps:
            pulsedodmr_block.append(start_element)
            pulsedodmr_block.append(waiting_element)
            count = 0
            while count < num_clicks:
                pulsedodmr_block.append(click_element)
                pulsedodmr_block.append(waiting_element)
                count += 1
            trig += 1

        created_blocks.append(pulsedodmr_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((pulsedodmr_block.name, 0))

        # Create and append sync trigger block if needed
        if self.sync_channel:
            sync_block = PulseBlock(name='sync_trigger')
            sync_block.append(self._get_sync_element())
            created_blocks.append(sync_block)
            block_ensemble.append((sync_block.name, 0))

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = np.arange(num_reps)
        block_ensemble.measurement_information['units'] = ('Hz', '')
        block_ensemble.measurement_information['labels'] = ('Frequency', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = num_reps
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_rabi_iq(self, name='rabi', tau_start=10.0e-9, tau_step=10.0e-9, num_of_points=50):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # create the laser_mw element

        # initialization_element = self._get_laser_element(length=1e-6,
        #                                              increment=0)

        mw_element = self._get_iq_mix_element(length=tau_start,
                                              increment=tau_step,
                                              amp=self.microwave_amplitude,
                                              freq=self.iq_freq_shift,
                                              phase=0)
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        cooling_element = self._get_idle_element(length=self.cool_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()

        # Create block and append to created_blocks list
        rabi_iq_block = PulseBlock(name=name)
        # rabi_iq_block.append(waiting_element)
        rabi_iq_block.append(mw_element)
        rabi_iq_block.append(cooling_element)
        rabi_iq_block.append(laser_element)
        rabi_iq_block.append(delay_element)
        rabi_iq_block.append(waiting_element)
        created_blocks.append(rabi_iq_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((rabi_iq_block.name, num_of_points - 1))

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        block_ensemble.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        block_ensemble.measurement_information['iq_mixing'] = True

        # Append ensemble to created_ensembles list
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_ramsey_iq(self, name='ramsey', tau_start=100.0e-9, tau_step=30.0e-9, num_of_points=50,
                           alternating=True):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self._get_iq_mix_element(length=self.rabi_period / 4, increment=0,
                                                  amp=self.microwave_amplitude,
                                                  freq=self.iq_freq_shift,
                                                  phase=0)
        # Use a 180 deg phase shiftet pulse as 3pihalf pulse if microwave channel is analog
        if self.microwave_channel.startswith('a'):
            pi3half_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                       increment=0,
                                                       amp=self.microwave_amplitude,
                                                       freq=self.iq_freq_shift,
                                                       phase=180)
        else:
            pi3half_element = self._get_iq_mix_element(length=3 * self.rabi_period / 4,
                                                       increment=0,
                                                       amp=self.microwave_amplitude,
                                                       freq=self.iq_freq_shift,
                                                       phase=0)
        tau_element = self._get_idle_element(length=tau_start, increment=tau_step)

        # Create block and append to created_blocks list
        ramsey_block = PulseBlock(name=name)
        ramsey_block.append(pihalf_element)
        ramsey_block.append(tau_element)
        ramsey_block.append(pi3half_element)
        ramsey_block.append(laser_element)
        ramsey_block.append(delay_element)
        ramsey_block.append(waiting_element)
        if alternating:
            ramsey_block.append(pihalf_element)
            ramsey_block.append(tau_element)
            ramsey_block.append(pihalf_element)
            ramsey_block.append(laser_element)
            ramsey_block.append(delay_element)
            ramsey_block.append(waiting_element)
        created_blocks.append(ramsey_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((ramsey_block.name, num_of_points - 1))

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        block_ensemble.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        block_ensemble.measurement_information['iq_mixing'] = True

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_hahnecho_iq(self, name='hahnecho', tau_start=0.0e-6, tau_step=1.0e-6,
                             num_of_points=50, pi_axis='x', alternating=True):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # set the phase of the pi pulse
        if pi_axis == 'x':
            pi_phase = 0
        elif pi_axis == '-x':
            pi_phase = 180
        elif pi_axis == 'y':
            pi_phase = 90
        elif pi_axis == '-y':
            pi_phase = -90
        else:
            self.log.error('Illegal input for pi_axis, should be one of the following: x, y, -x, -y')
            return created_blocks, created_ensembles, created_sequences
        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                  increment=0,
                                                  amp=self.microwave_amplitude,
                                                  freq=self.iq_freq_shift,
                                                  phase=0)
        pi_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.iq_freq_shift,
                                              phase=pi_phase)
        # Use a 180 deg phase shiftet pulse as 3pihalf pulse if microwave channel is analog
        if self.microwave_channel.startswith('a'):
            pi3half_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                       increment=0,
                                                       amp=self.microwave_amplitude,
                                                       freq=self.iq_freq_shift,
                                                       phase=180)
        else:
            pi3half_element = self._get_iq_mix_element(length=3 * self.rabi_period / 4,
                                                       increment=0,
                                                       amp=self.microwave_amplitude,
                                                       freq=self.iq_freq_shift,
                                                       phase=0)
        tau_element = self._get_idle_element(length=tau_start, increment=tau_step)

        # Create block and append to created_blocks list
        hahn_block = PulseBlock(name=name)
        hahn_block.append(pihalf_element)
        hahn_block.append(tau_element)
        hahn_block.append(pi_element)
        hahn_block.append(tau_element)
        hahn_block.append(pihalf_element)
        hahn_block.append(laser_element)
        hahn_block.append(delay_element)
        hahn_block.append(waiting_element)
        if alternating:
            hahn_block.append(pihalf_element)
            hahn_block.append(tau_element)
            hahn_block.append(pi_element)
            hahn_block.append(tau_element)
            hahn_block.append(pi3half_element)
            hahn_block.append(laser_element)
            hahn_block.append(delay_element)
            hahn_block.append(waiting_element)
        created_blocks.append(hahn_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((hahn_block.name, num_of_points - 1))

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        block_ensemble.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        block_ensemble.measurement_information['iq_mixing'] = True

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_xy8_tau_iq(self, name='xy8_tau_iq', tau_start=0.0e-6, tau_step=0.01e-6, num_of_points=50,
                            xy8_order=4, randomize_phases=False, alternating=True):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step
        # calculate "real" start length of tau due to finite pi-pulse length
        real_start_tau = max(0, tau_start - self.rabi_period / 2)

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                  increment=0,
                                                  amp=self.microwave_amplitude,
                                                  freq=self.iq_freq_shift,
                                                  phase=0)
        # Use a 180 deg phase shiftet pulse as 3pihalf pulse if microwave channel is analog
        pi3half_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.iq_freq_shift,
                                                   phase=180)

        tauhalf_element = self._get_idle_element(length=real_start_tau / 2, increment=tau_step / 2)
        tau_element = self._get_idle_element(length=real_start_tau, increment=tau_step)

        # Create block and append to created_blocks list
        xy8_block = PulseBlock(name=name)
        xy8_block.append(pihalf_element)
        for n in range(xy8_order):
            if randomize_phases:
                phase_shift = np.random.rand()*360
            else:
                phase_shift = 0
            xy8_block.append(tauhalf_element)
            xy8_block.append(self.pix_element(phase_shift))
            xy8_block.append(tau_element)
            xy8_block.append(self.piy_element(phase_shift))
            xy8_block.append(tau_element)
            xy8_block.append(self.pix_element(phase_shift))
            xy8_block.append(tau_element)
            xy8_block.append(self.piy_element(phase_shift))
            xy8_block.append(tau_element)
            xy8_block.append(self.piy_element(phase_shift))
            xy8_block.append(tau_element)
            xy8_block.append(self.pix_element(phase_shift))
            xy8_block.append(tau_element)
            xy8_block.append(self.piy_element(phase_shift))
            xy8_block.append(tau_element)
            xy8_block.append(self.pix_element(phase_shift))
            xy8_block.append(tauhalf_element)
        xy8_block.append(pihalf_element)
        xy8_block.append(laser_element)
        xy8_block.append(delay_element)
        xy8_block.append(waiting_element)
        if alternating:
            xy8_block.append(pihalf_element)
            for n in range(xy8_order):
                if randomize_phases:
                    phase_shift = np.random.rand() * 360
                else:
                    phase_shift = 0
                xy8_block.append(tauhalf_element)
                xy8_block.append(self.pix_element(phase_shift))
                xy8_block.append(tau_element)
                xy8_block.append(self.piy_element(phase_shift))
                xy8_block.append(tau_element)
                xy8_block.append(self.pix_element(phase_shift))
                xy8_block.append(tau_element)
                xy8_block.append(self.piy_element(phase_shift))
                xy8_block.append(tau_element)
                xy8_block.append(self.piy_element(phase_shift))
                xy8_block.append(tau_element)
                xy8_block.append(self.pix_element(phase_shift))
                xy8_block.append(tau_element)
                xy8_block.append(self.piy_element(phase_shift))
                xy8_block.append(tau_element)
                xy8_block.append(self.pix_element(phase_shift))
                xy8_block.append(tauhalf_element)
            xy8_block.append(pi3half_element)
            xy8_block.append(laser_element)
            xy8_block.append(delay_element)
            xy8_block.append(waiting_element)
        created_blocks.append(xy8_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((xy8_block.name, num_of_points - 1))

        # Create and append sync trigger block if needed - removed

        # add metadata to invoke settings later on
        number_of_lasers = num_of_points * 2 if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        block_ensemble.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        block_ensemble.measurement_information['iq_mixing'] = True
        block_ensemble.measurement_information['randomized_phases'] = randomize_phases

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_xy8_n_iq(self, name='xy8_n_iq', tau=0.1e-6, n_start=1, n_step=1,
                          num_of_points=20, alternating=True):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        n_array = n_start + np.arange(num_of_points) * n_step
        # calculate "real" start length of tau due to finite pi-pulse length
        real_tau = max(0, tau - self.rabi_period / 2)

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                  increment=0,
                                                  amp=self.microwave_amplitude,
                                                  freq=self.iq_freq_shift,
                                                  phase=0)
        # Use a 180 deg phase shiftet pulse as 3pihalf pulse if microwave channel is analog
        pi3half_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.iq_freq_shift,
                                                   phase=180)

        pix_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                               increment=0,
                                               amp=self.microwave_amplitude,
                                               freq=self.iq_freq_shift,
                                               phase=0)
        piy_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                               increment=0,
                                               amp=self.microwave_amplitude,
                                               freq=self.iq_freq_shift,
                                               phase=90)
        tauhalf_element = self._get_idle_element(length=real_tau / 2, increment=0)
        tau_element = self._get_idle_element(length=real_tau, increment=0)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)

        # Create block and append to created_blocks list
        for xy8_order in n_array:
            xy8_block = PulseBlock(name='{0}-{1}'.format(name, xy8_order))
            xy8_block.append(pihalf_element)
            xy8_block.append(tauhalf_element)
            for n in range(xy8_order):
                xy8_block.append(pix_element)
                xy8_block.append(tau_element)
                xy8_block.append(piy_element)
                xy8_block.append(tau_element)
                xy8_block.append(pix_element)
                xy8_block.append(tau_element)
                xy8_block.append(piy_element)
                xy8_block.append(tau_element)
                xy8_block.append(piy_element)
                xy8_block.append(tau_element)
                xy8_block.append(pix_element)
                xy8_block.append(tau_element)
                xy8_block.append(piy_element)
                xy8_block.append(tau_element)
                xy8_block.append(pix_element)
                if n != xy8_order - 1:
                    xy8_block.append(tau_element)
            xy8_block.append(tauhalf_element)
            xy8_block.append(pihalf_element)
            xy8_block.append(laser_element)
            xy8_block.append(delay_element)
            xy8_block.append(waiting_element)
            if alternating:
                xy8_block.append(pihalf_element)
                xy8_block.append(tauhalf_element)
                for n in range(xy8_order):
                    xy8_block.append(pix_element)
                    xy8_block.append(tau_element)
                    xy8_block.append(piy_element)
                    xy8_block.append(tau_element)
                    xy8_block.append(pix_element)
                    xy8_block.append(tau_element)
                    xy8_block.append(piy_element)
                    xy8_block.append(tau_element)
                    xy8_block.append(piy_element)
                    xy8_block.append(tau_element)
                    xy8_block.append(pix_element)
                    xy8_block.append(tau_element)
                    xy8_block.append(piy_element)
                    xy8_block.append(tau_element)
                    xy8_block.append(pix_element)
                    if n != xy8_order - 1:
                        xy8_block.append(tau_element)
                xy8_block.append(tauhalf_element)
                xy8_block.append(pi3half_element)
                xy8_block.append(laser_element)
                xy8_block.append(delay_element)
                xy8_block.append(waiting_element)
            created_blocks.append(xy8_block)
            block_ensemble.append((xy8_block.name, 0))

        # add metadata to invoke settings later on
        number_of_lasers = num_of_points * 2 if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = n_array
        block_ensemble.measurement_information['units'] = ('', '')
        block_ensemble.measurement_information['labels'] = ('N', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        block_ensemble.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        block_ensemble.measurement_information['iq_mixing'] = True
        block_ensemble.measurement_information['tau'] = tau

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_t1_log_scale(self, name='t1_log', tau_start=1.0e-6, tau_end=1.0e-3,
                              num_of_points=10, alternating=True):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Get logarithmically spaced steps in multiples of tau_start.
        # Note that the number of points and the position of the last point can change here.
        # set the minimum wait time to be tau_start/10, set repetitions accordingly
        tau_step = tau_start / 5
        if tau_step < 129e-9:  # this is the shortest segment allowed for the awg
            self.log.error('minimum segment size is 129ns, adjust pulse sequence parameters')
        k_exact = (np.logspace(0., np.log10(tau_end / tau_start), num_of_points)) * 5
        k_array = np.unique(np.rint(k_exact).astype(int))
        # get tau array for measurement ticks
        tau_array = k_array * tau_step

        # Create the readout PulseBlockEnsemble
        # Get necessary PulseBlockElements
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        # Create PulseBlock and append PulseBlockElements
        readout_block = PulseBlock(name='{0}_readout'.format(name))
        readout_block.append(laser_element)
        readout_block.append(delay_element)
        created_blocks.append(readout_block)
        # Create PulseBlockEnsemble and append block to it
        readout_ensemble = PulseBlockEnsemble(name='{0}_readout'.format(name), rotating_frame=False)
        readout_ensemble.append((readout_block.name, 0))
        created_ensembles.append(readout_ensemble)

        if alternating:
            # Create the alternating readout PulseBlockEnsemble
            # Get necessary PulseBlockElements
            laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
            delay_element = self._get_delay_gate_element()
            pi_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                                  increment=0,
                                                  amp=self.microwave_amplitude,
                                                  freq=self.iq_freq_shift,
                                                  phase=0)
            # Create PulseBlock and append PulseBlockElements
            readout_pi_block = PulseBlock(name='{0}_readout_pi'.format(name))
            readout_pi_block.append(laser_element)
            readout_pi_block.append(delay_element)
            readout_pi_block.append(pi_element)
            created_blocks.append(readout_pi_block)
            # Create PulseBlockEnsemble and append block to it
            readout_pi_ensemble = PulseBlockEnsemble(name='{0}_readout_pi'.format(name), rotating_frame=False)
            readout_pi_ensemble.append((readout_pi_block.name, 0))
            created_ensembles.append(readout_pi_ensemble)

        # Create the tau/waiting PulseBlockEnsemble
        # Get tau PulseBlockElement
        tau_element = self._get_idle_element(length=tau_step, increment=0)
        # Create PulseBlock and append PulseBlockElements
        tau_block = PulseBlock(name='{0}_tau'.format(name))
        tau_block.append(tau_element)
        created_blocks.append(tau_block)
        # Create PulseBlockEnsemble and append block to it
        tau_ensemble = PulseBlockEnsemble(name='{0}_tau'.format(name), rotating_frame=False)
        tau_ensemble.append((tau_block.name, 0))
        created_ensembles.append(tau_ensemble)

        # Create the PulseSequence and append the PulseBlockEnsemble names as sequence steps
        # together with the necessary parameters.
        t1_sequence = PulseSequence(name=name, rotating_frame=False)
        count_length = 0.0
        next_step = 1

        for k in k_array:
            t1_sequence.append(tau_ensemble.name)
            t1_sequence[-1].repetitions = int(k)
            count_length += k * self._get_ensemble_count_length(ensemble=tau_ensemble,
                                                                created_blocks=created_blocks)
            t1_sequence[-1].go_to = next_step
            next_step += 1

            if alternating:
                t1_sequence.append(readout_pi_ensemble.name)
                t1_sequence[-1].repetitions = int(1)
                t1_sequence[-1].go_to = next_step
                next_step += 1
                count_length += self._get_ensemble_count_length(ensemble=readout_pi_ensemble,
                                                                created_blocks=created_blocks)

                t1_sequence.append(tau_ensemble.name)
                t1_sequence[-1].repetitions = int(k)
                count_length += k * self._get_ensemble_count_length(ensemble=tau_ensemble,
                                                                    created_blocks=created_blocks)
                t1_sequence[-1].go_to = next_step
                next_step += 1

            t1_sequence.append(readout_ensemble.name)
            t1_sequence[-1].repetitions = int(1)
            t1_sequence[-1].go_to = next_step
            next_step += 1
            count_length += self._get_ensemble_count_length(ensemble=readout_ensemble,
                                                            created_blocks=created_blocks)

        # Make the sequence loop infinitely by setting the go_to parameter of the last sequence
        # step to the first step.
        t1_sequence[-1].go_to = 0

        # Trigger the calculation of parameters in the PulseSequence instance
        t1_sequence.refresh_parameters()

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        t1_sequence.measurement_information['alternating'] = alternating
        t1_sequence.measurement_information['laser_ignore_list'] = list()
        t1_sequence.measurement_information['controlled_variable'] = tau_array
        t1_sequence.measurement_information['units'] = ('s', '')
        t1_sequence.measurement_information['number_of_lasers'] = number_of_lasers
        # t1_sequence.measurement_information['counting_length'] = count_length
        t1_sequence.measurement_information['counting_length'] = self.laser_length + self.laser_delay
        t1_sequence.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        t1_sequence.measurement_information['iq_mixing'] = True

        # Append PulseSequence to created_sequences list
        created_sequences.append(t1_sequence)
        return created_blocks, created_ensembles, created_sequences

    def generate_t1_linear(self, name='t1_linear', tau_start=1.0e-6, tau_step=1.0e-6,
                           num_of_points=10, alternating=True):

        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Get logarithmically spaced steps in multiples of tau_start.
        # Note that the number of points and the position of the last point can change here.

        k_array = 1 + np.arange(num_of_points - 1)  # for number of repetitions
        # minus 1 since the first step is tau_start
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # Create the readout PulseBlockEnsemble
        # Get necessary PulseBlockElements
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        # Create PulseBlock and append PulseBlockElements
        readout_block = PulseBlock(name='{0}_readout'.format(name))
        readout_block.append(laser_element)
        readout_block.append(delay_element)
        created_blocks.append(readout_block)
        # Create PulseBlockEnsemble and append block to it
        readout_ensemble = PulseBlockEnsemble(name='{0}_readout'.format(name), rotating_frame=False)
        readout_ensemble.append((readout_block.name, 0))
        created_ensembles.append(readout_ensemble)

        if alternating:
            # Create the alternating readout PulseBlockEnsemble
            # Get necessary PulseBlockElements
            laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
            delay_element = self._get_delay_gate_element()
            pi_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                                  increment=0,
                                                  amp=self.microwave_amplitude,
                                                  freq=self.iq_freq_shift,
                                                  phase=0)
            # Create PulseBlock and append PulseBlockElements
            readout_pi_block = PulseBlock(name='{0}_readout_pi'.format(name))
            readout_pi_block.append(laser_element)
            readout_pi_block.append(delay_element)
            readout_pi_block.append(pi_element)
            created_blocks.append(readout_pi_block)
            # Create PulseBlockEnsemble and append block to it
            readout_pi_ensemble = PulseBlockEnsemble(name='{0}_readout_pi'.format(name), rotating_frame=False)
            readout_pi_ensemble.append((readout_pi_block.name, 0))
            created_ensembles.append(readout_pi_ensemble)

        # Create the tau/waiting PulseBlockEnsemble
        # Get tau PulseBlockElement
        delta_tau_element = self._get_idle_element(length=tau_step, increment=0)
        # Create PulseBlock and append PulseBlockElements
        delta_tau_block = PulseBlock(name='{0}_delta_tau'.format(name))
        delta_tau_block.append(delta_tau_element)
        created_blocks.append(delta_tau_block)
        # Create PulseBlockEnsemble and append block to it
        delta_tau_ensemble = PulseBlockEnsemble(name='{0}_delta_tau'.format(name), rotating_frame=False)
        delta_tau_ensemble.append((delta_tau_block.name, 0))
        created_ensembles.append(delta_tau_ensemble)

        # if linear scale the wait period is a tau start element plus the number of steps for delta tau
        # Create the tau/waiting PulseBlockEnsemble
        # Get tau PulseBlockElement
        tau_start_element = self._get_idle_element(length=tau_start, increment=0)
        # Create PulseBlock and append PulseBlockElements
        tau_start_block = PulseBlock(name='{0}_start_tau'.format(name))
        tau_start_block.append(tau_start_element)
        created_blocks.append(tau_start_block)
        # Create PulseBlockEnsemble and append block to it
        tau_start_ensemble = PulseBlockEnsemble(name='{0}_start_tau'.format(name), rotating_frame=False)
        tau_start_ensemble.append((tau_start_block.name, 0))
        created_ensembles.append(tau_start_ensemble)

        # Create the PulseSequence and append the PulseBlockEnsemble names as sequence steps
        # together with the necessary parameters.
        t1_sequence = PulseSequence(name=name, rotating_frame=False)
        count_length = 0.0
        next_step = 1

        # for linear scale the first step is simply tau_start
        t1_sequence.append(tau_start_ensemble.name)
        t1_sequence[-1].repetitions = int(1)
        t1_sequence[-1].go_to = next_step
        next_step += 1
        count_length += self._get_ensemble_count_length(ensemble=tau_start_ensemble,
                                                        created_blocks=created_blocks)

        if alternating:
            t1_sequence.append(readout_pi_ensemble.name)
            t1_sequence[-1].repetitions = int(1)
            t1_sequence[-1].go_to = next_step
            next_step += 1
            count_length += self._get_ensemble_count_length(ensemble=readout_pi_ensemble,
                                                            created_blocks=created_blocks)

            t1_sequence.append(tau_start_ensemble.name)
            t1_sequence[-1].repetitions = int(1)
            t1_sequence[-1].go_to = next_step
            next_step += 1
            count_length += self._get_ensemble_count_length(ensemble=tau_start_ensemble,
                                                            created_blocks=created_blocks)

        t1_sequence.append(readout_ensemble.name)
        t1_sequence[-1].repetitions = int(1)
        t1_sequence[-1].go_to = next_step
        next_step += 1
        count_length += self._get_ensemble_count_length(ensemble=readout_ensemble,
                                                        created_blocks=created_blocks)

        for k in k_array:
            # if linear scale the first step is set by tau start by user
            t1_sequence.append(tau_start_ensemble.name)
            t1_sequence[-1].repetitions = int(1)
            t1_sequence[-1].go_to = next_step
            next_step += 1
            count_length += self._get_ensemble_count_length(ensemble=tau_start_ensemble,
                                                            created_blocks=created_blocks)
            t1_sequence.append(delta_tau_ensemble.name)
            t1_sequence[-1].repetitions = int(k)
            count_length += k * self._get_ensemble_count_length(ensemble=delta_tau_ensemble,
                                                                created_blocks=created_blocks)
            t1_sequence[-1].go_to = next_step
            next_step += 1

            if alternating:
                t1_sequence.append(readout_pi_ensemble.name)
                t1_sequence[-1].repetitions = int(1)
                t1_sequence[-1].go_to = next_step
                next_step += 1
                count_length += self._get_ensemble_count_length(ensemble=readout_pi_ensemble,
                                                                created_blocks=created_blocks)
                # if linear scale the first step is set by tau start by user
                t1_sequence.append(tau_start_ensemble.name)
                t1_sequence[-1].repetitions = int(1)
                t1_sequence[-1].go_to = next_step
                next_step += 1
                count_length += self._get_ensemble_count_length(ensemble=tau_start_ensemble,
                                                                created_blocks=created_blocks)
                t1_sequence.append(delta_tau_ensemble.name)
                t1_sequence[-1].repetitions = int(k)
                count_length += k * self._get_ensemble_count_length(ensemble=delta_tau_ensemble,
                                                                    created_blocks=created_blocks)
                t1_sequence[-1].go_to = next_step
                next_step += 1

            t1_sequence.append(readout_ensemble.name)
            t1_sequence[-1].repetitions = int(1)
            t1_sequence[-1].go_to = next_step
            next_step += 1
            count_length += self._get_ensemble_count_length(ensemble=readout_ensemble,
                                                            created_blocks=created_blocks)

        # Make the sequence loop infinitely by setting the go_to parameter of the last sequence
        # step to the first step.
        t1_sequence[-1].go_to = 0

        # Trigger the calculation of parameters in the PulseSequence instance
        t1_sequence.refresh_parameters()

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        t1_sequence.measurement_information['alternating'] = alternating
        t1_sequence.measurement_information['laser_ignore_list'] = list()
        t1_sequence.measurement_information['controlled_variable'] = tau_array
        t1_sequence.measurement_information['units'] = ('s', '')
        t1_sequence.measurement_information['number_of_lasers'] = number_of_lasers
        # t1_sequence.measurement_information['counting_length'] = count_length
        t1_sequence.measurement_information['counting_length'] = self.laser_length + self.laser_delay
        t1_sequence.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        t1_sequence.measurement_information['iq_mixing'] = True

        # Append PulseSequence to created_sequences list
        created_sequences.append(t1_sequence)
        return created_blocks, created_ensembles, created_sequences

    def generate_odmr_cw(self, name='odmrcw', freq_start=2.77e9, freq_step=2e6, num_of_points=101):

        """

            """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Array for analysis (invoked setting)
        freq_array = freq_start + np.arange(num_of_points) * freq_step

        # Create frequency array
        shifted_freq_array = freq_array - self.microwave_frequency

        # create the elements
        delay_element = self._get_delay_gate_element()
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)

        # Create block and append to created_blocks list
        odmr_cw_block = PulseBlock(name=name)
        for freq in shifted_freq_array:
            cw_element = self._get_cw_element(length=self.laser_length,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=freq,
                                              phase=0)
            odmr_cw_block.append(cw_element)
            odmr_cw_block.append(delay_element)
            odmr_cw_block.append(waiting_element)

        created_blocks.append(odmr_cw_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((odmr_cw_block.name, 0))

        # Create and append sync trigger block if needed
        if self.sync_channel:
            sync_block = PulseBlock(name='sync_trigger')
            sync_block.append(self._get_sync_element())
            created_blocks.append(sync_block)
            block_ensemble.append((sync_block.name, 0))

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = freq_array
        block_ensemble.measurement_information['units'] = ('Hz', '')
        block_ensemble.measurement_information['labels'] = ('Frequency', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        block_ensemble.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        block_ensemble.measurement_information['iq_mixing'] = True

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_odmr_cw_sequencing(self, name='odmrcwseq', freq_start=2.77e9, freq_step=2e6, num_of_points=101):
        """

        """
        # All the elements will be 10 microseconds long, and repeated as required. If the given laser length or laser
        # delay will be a non-integer multiple of element_length, it will be rounded up to the nearest integer multiple
        element_length = 10e-6

        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Create frequency array
        freq_array = freq_start - self.microwave_frequency + np.arange(num_of_points) * freq_step
        freq_ensemble_names = {}

        # Create the readout PulseBlockEnsemble
        # Get necessary PulseBlockElements
        polarization_element = self._get_laser_gate_element(length=element_length, increment=0)
        delay_element = self._get_idle_element(length=self.wait_time, increment=0)
        # Create PulseBlock and append PulseBlockElements

        polarization_block = PulseBlock(name='{0}_polarization'.format(name))
        polarization_block.append(polarization_element)
        created_blocks.append(polarization_block)

        # Create PulseBlockEnsemble and append block to it
        polarization_ensemble = PulseBlockEnsemble(name='{0}_polarization'.format(name), rotating_frame=False)
        polarization_ensemble.append((polarization_block.name, 0))
        created_ensembles.append(polarization_ensemble)

        delay_block = PulseBlock(name='{0}_delay'.format(name))
        delay_block.append(delay_element)
        created_blocks.append(delay_block)

        # Create PulseBlockEnsemble and append block to it
        delay_ensemble = PulseBlockEnsemble(name='{0}_delay'.format(name), rotating_frame=False)
        delay_ensemble.append((delay_block.name, 0))
        created_ensembles.append(delay_ensemble)

        # Create the various frequency PulseBlockEnsembles
        for i, freq in enumerate(freq_array):
            freq_block = PulseBlock(name='{0}_cw_{1}MHz'.format(name, freq * 1e-6))
            cw_element = self._get_cw_element(length=element_length,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=freq,
                                              phase=0)
            freq_block.append(cw_element)
            created_blocks.append(freq_block)
            freq_ensemble = PulseBlockEnsemble(name='{0}_cw_{1}MHz'.format(name, freq * 1e-6), rotating_frame=False)
            freq_ensemble.append((freq_block.name, 0))
            freq_ensemble_names[freq] = freq_ensemble.name
            created_ensembles.append(freq_ensemble)

        # Create the PulseSequence and append the PulseBlockEnsemble names as sequence steps
        # together with the necessary parameters.
        odmr_cw_sequence = PulseSequence(name=name, rotating_frame=False)
        freq_repetitions = int(np.ceil(self.laser_length / element_length))
        polarization_repetitions = int(np.ceil(self.laser_delay / element_length))
        corrected_laser_length = freq_repetitions * element_length
        corrected_laser_delay = polarization_repetitions * element_length
        count_length = corrected_laser_length + corrected_laser_delay + self.wait_time

        for f in freq_array:
            odmr_cw_sequence.append(freq_ensemble_names[f])
            odmr_cw_sequence[-1].repetitions = freq_repetitions
            odmr_cw_sequence.append(polarization_ensemble.name)
            odmr_cw_sequence[-1].repetitions = polarization_repetitions
            odmr_cw_sequence.append(delay_ensemble.name)
            odmr_cw_sequence[-1].repetitions = 1

        for i in range(len(odmr_cw_sequence)):
            odmr_cw_sequence[i].go_to = i + 1

        odmr_cw_sequence[-1].go_to = 0

        # Trigger the calculation of parameters in the PulseSequence instance
        odmr_cw_sequence.refresh_parameters()

        # add metadata to invoke settings later on
        odmr_cw_sequence.measurement_information['alternating'] = False
        odmr_cw_sequence.measurement_information['laser_ignore_list'] = list()
        odmr_cw_sequence.measurement_information['controlled_variable'] = freq_array + self.microwave_frequency
        odmr_cw_sequence.measurement_information['units'] = ('Hz', '')
        odmr_cw_sequence.measurement_information['labels'] = ('Frequency', 'Signal')
        odmr_cw_sequence.measurement_information['number_of_lasers'] = len(freq_array)
        odmr_cw_sequence.measurement_information['counting_length'] = count_length

        # Append PulseSequence to created_sequences list
        created_sequences.append(odmr_cw_sequence)
        return created_blocks, created_ensembles, created_sequences

    def generate_pulse_laser(self, name='pulse_laser', tau_start=10.0e-9, tau_step=10.0e-9, num_of_points=50,
                             t_on=10e-9, t_off=10e-9, reps=10):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # create the laser_mw element

        # initialization_element = self._get_laser_element(length=1e-6,
        #                                              increment=0)

        mw_element = self._get_iq_mix_element(length=tau_start,
                                              increment=tau_step,
                                              amp=self.microwave_amplitude,
                                              freq=self.iq_freq_shift,
                                              phase=0)
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        delay_element = self._get_laser_element(length=self.laser_delay, increment=0)
        read_out_element = self._get_laser_gate_element(length=self.laser_length,
                                                        increment=0)
        laser_on_element = self._get_laser_gate_element(length=t_on,
                                                        increment=0)
        laser_off_element = self._get_trigger_element(length=t_off, increment=0, channels=self.gate_channel)

        # Create block and append to created_blocks list
        pulsed_laser_block = PulseBlock(name=name)
        pulsed_laser_block.append(mw_element)
        pulsed_laser_block.append(delay_element)
        pulsed_laser_block.append(read_out_element)

        count = 0
        while count < reps:
            pulsed_laser_block.append(laser_on_element)
            pulsed_laser_block.append(laser_off_element)
            count += 1
        pulsed_laser_block.append(waiting_element)
        created_blocks.append(pulsed_laser_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((pulsed_laser_block.name, num_of_points - 1))

        # Create and append sync trigger block if needed
        # if self.sync_channel:
        #     sync_block = PulseBlock(name='sync_trigger')
        #     sync_block.append(self._get_sync_element())
        #     created_blocks.append(sync_block)
        #     block_ensemble.append((sync_block.name, 0))

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks) + reps * (t_on + t_off)
        block_ensemble.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        block_ensemble.measurement_information['iq_mixing'] = True

        # Append ensemble to created_ensembles list
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_tomography_iq(self, name='tomography', tau_start=0.0e-6, tau_step=1.0e-6,
                               num_of_points=50, pi_axis='x', rotation_axis='x', alpha=0.0, alternating=True):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # set the phase of the pi pulse
        if pi_axis == 'x':
            pi_phase = 0
        elif pi_axis == '-x':
            pi_phase = 180
        elif pi_axis == 'y':
            pi_phase = 90
        elif pi_axis == '-y':
            pi_phase = -90
        else:
            self.log.error('Illegal input for pi_axis, should be one of the following: x, y, -x, -y')
            return created_blocks, created_ensembles, created_sequences

        # set the phase for the projections
        if rotation_axis == 'x':
            rotation_phase = 0
        elif rotation_axis == 'y':
            rotation_phase = 90
        elif rotation_axis == 'z':
            rotation_phase = 0
        else:
            self.log.error('Illegal input for rotation_axis, should be one of the following: x, y, z')
            return created_blocks, created_ensembles, created_sequences

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()


        alpha_initialization_element = self._get_iq_mix_element(length=self.rabi_period * alpha / 360,
                                                                increment=0,
                                                                amp=self.microwave_amplitude,
                                                                freq=self.iq_freq_shift,
                                                                phase=0)
        pi_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.iq_freq_shift,
                                              phase=pi_phase)
        pihalf_projection_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                             increment=0,
                                                             amp=self.microwave_amplitude,
                                                             freq=self.iq_freq_shift,
                                                             phase=rotation_phase)

        # Use a 180 deg phase shifted pulse as 3pihalf pulse if microwave channel is analog
        pi3half_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                       increment=0,
                                                       amp=self.microwave_amplitude,
                                                       freq=self.iq_freq_shift,
                                                       phase=rotation_phase-180)

        # Defining tau elements
        # tau_element = self._get_idle_element(length=tau_start, increment=tau_step)
        first_real_tau_element = self._get_idle_element(length=tau_start-self.rabi_period * alpha / 360 - self.rabi_period / 4, increment=tau_step)
        second_real_xy_tau_element = self._get_idle_element(length=tau_start - self.rabi_period / 2, increment=tau_step)
        second_real_z_tau_element = self._get_idle_element(length=tau_start - self.rabi_period / 4, increment=tau_step)
        second_real_z_tau_alternate_element = self._get_idle_element(length=tau_start - 3 * self.rabi_period / 4, increment=tau_step)

        # Create block and append to created_blocks list
        tomography_block = PulseBlock(name=name)
        tomography_block.append(alpha_initialization_element)
        tomography_block.append(first_real_tau_element)
        tomography_block.append(pi_element)
        if rotation_axis == 'x' or rotation_axis == 'y':
            tomography_block.append(second_real_xy_tau_element)
            tomography_block.append(pihalf_projection_element)
        if rotation_axis == 'z':
            tomography_block.append(second_real_z_tau_element)
        tomography_block.append(laser_element)
        tomography_block.append(delay_element)
        tomography_block.append(waiting_element)
        if alternating:
            tomography_block.append(alpha_initialization_element)
            tomography_block.append(first_real_tau_element)
            tomography_block.append(pi_element)
            if rotation_axis == 'x' or rotation_axis == 'y':
                tomography_block.append(second_real_xy_tau_element)
                tomography_block.append(pi3half_element)
            if rotation_axis == 'z':
                tomography_block.append(second_real_z_tau_alternate_element)
                tomography_block.append(pi_element)
            tomography_block.append(laser_element)
            tomography_block.append(delay_element)
            tomography_block.append(waiting_element)
        created_blocks.append(tomography_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((tomography_block.name, num_of_points - 1))

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        block_ensemble.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        block_ensemble.measurement_information['iq_mixing'] = True

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_tomography_angle_iq(self, name='tomography', tau_start=0.0e-6, tau_step=1.0e-6,
                               num_of_points=50, pi_axis='x', rotation_axis='x', alpha=0.0, alternating=True):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # set the phase of the pi pulse
        if pi_axis == 'x':
            pi_phase = 0
        elif pi_axis == '-x':
            pi_phase = 180
        elif pi_axis == 'y':
            pi_phase = 90
        elif pi_axis == '-y':
            pi_phase = -90
        else:
            self.log.error('Illegal input for pi_axis, should be one of the following: x, y, -x, -y')
            return created_blocks, created_ensembles, created_sequences

        # set the phase for the projections
        if rotation_axis == 'x':
            rotation_phase = 0
        elif rotation_axis == 'y':
            rotation_phase = 90
        elif rotation_axis == 'z':
            rotation_phase = 0
        else:
            self.log.error('Illegal input for rotation_axis, should be one of the following: x, y, z')
            return created_blocks, created_ensembles, created_sequences

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()


        alpha_initialization_element = self._get_iq_mix_element(length=self.rabi_period * alpha / 360,
                                                                increment=0,
                                                                amp=self.microwave_amplitude,
                                                                freq=self.iq_freq_shift,
                                                                phase=0)
        pi_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.iq_freq_shift,
                                              phase=pi_phase)
        pihalf_projection_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                             increment=0,
                                                             amp=self.microwave_amplitude,
                                                             freq=self.iq_freq_shift,
                                                             phase=rotation_phase)

        # Use a 180 deg phase shifted pulse as 3pihalf pulse if microwave channel is analog
        pi3half_element = self._get_iq_mix_element(length=self.rabi_period / 4,
                                                       increment=0,
                                                       amp=self.microwave_amplitude,
                                                       freq=self.iq_freq_shift,
                                                       phase=rotation_phase-180)

        # Defining tau elements
        # tau_element = self._get_idle_element(length=tau_start, increment=tau_step)
        first_real_tau_element = self._get_idle_element(length=tau_start-self.rabi_period * alpha / 360 - self.rabi_period / 4, increment=tau_step)
        second_real_xy_tau_element = self._get_idle_element(length=tau_start - self.rabi_period / 2, increment=tau_step)
        second_real_z_tau_element = self._get_idle_element(length=tau_start - self.rabi_period / 4, increment=tau_step)
        second_real_z_tau_alternate_element = self._get_idle_element(length=tau_start - 3 * self.rabi_period / 4, increment=tau_step)

        # Create block and append to created_blocks list
        tomography_block = PulseBlock(name=name)
        tomography_block.append(alpha_initialization_element)
        tomography_block.append(first_real_tau_element)
        tomography_block.append(pi_element)
        if rotation_axis == 'x' or rotation_axis == 'y':
            tomography_block.append(second_real_xy_tau_element)
            tomography_block.append(pihalf_projection_element)
        if rotation_axis == 'z':
            tomography_block.append(second_real_z_tau_element)
        tomography_block.append(laser_element)
        tomography_block.append(delay_element)
        tomography_block.append(waiting_element)
        if alternating:
            tomography_block.append(alpha_initialization_element)
            tomography_block.append(first_real_tau_element)
            tomography_block.append(pi_element)
            if rotation_axis == 'x' or rotation_axis == 'y':
                tomography_block.append(second_real_xy_tau_element)
                tomography_block.append(pi3half_element)
            if rotation_axis == 'z':
                tomography_block.append(second_real_z_tau_alternate_element)
                tomography_block.append(pi_element)
            tomography_block.append(laser_element)
            tomography_block.append(delay_element)
            tomography_block.append(waiting_element)
        created_blocks.append(tomography_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((tomography_block.name, num_of_points - 1))

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        block_ensemble.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        block_ensemble.measurement_information['iq_mixing'] = True

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences


    def generate_t1_log_scale_channel_1(self, name='t1_log_channel_1', tau_start=1.0e-6, tau_end=1.0e-3,
                              num_of_points=10, alternating=True):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Get logarithmically spaced steps in multiples of tau_start.
        # Note that the number of points and the position of the last point can change here.
        # set the minimum wait time to be tau_start/10, set repetitions accordingly
        tau_step = tau_start / 5
        if tau_step < 129e-9:  # this is the shortest segment allowed for the awg
            self.log.error('minimum segment size is 129ns, adjust pulse sequence parameters')
        k_exact = (np.logspace(0., np.log10(tau_end / tau_start), num_of_points)) * 5
        k_array = np.unique(np.rint(k_exact).astype(int))
        # get tau array for measurement ticks
        tau_array = k_array * tau_step

        # Create the readout PulseBlockEnsemble
        # Get necessary PulseBlockElements
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()

        pi_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.iq_freq_shift,
                                              phase=0)

        # Create PulseBlock and append PulseBlockElements
        readout_block = PulseBlock(name='{0}_readout'.format(name))
        readout_block.append(laser_element)
        readout_block.append(delay_element)
        readout_block.append(pi_element)
        created_blocks.append(readout_block)
        # Create PulseBlockEnsemble and append block to it
        readout_ensemble = PulseBlockEnsemble(name='{0}_readout'.format(name), rotating_frame=False)
        readout_ensemble.append((readout_block.name, 0))
        created_ensembles.append(readout_ensemble)

        if alternating:
            # Create the alternating readout PulseBlockEnsemble
            # Get necessary PulseBlockElements
            laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
            delay_element = self._get_delay_gate_element()
            pi_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                                  increment=0,
                                                  amp=self.microwave_amplitude,
                                                  freq=self.iq_freq_shift,
                                                  phase=0)
            # Create PulseBlock and append PulseBlockElements
            readout_pi_block = PulseBlock(name='{0}_readout_pi'.format(name))
            readout_pi_block.append(pi_element)
            readout_pi_block.append(laser_element)
            readout_pi_block.append(delay_element)
            readout_pi_block.append(pi_element)
            created_blocks.append(readout_pi_block)
            # Create PulseBlockEnsemble and append block to it
            readout_pi_ensemble = PulseBlockEnsemble(name='{0}_readout_pi'.format(name), rotating_frame=False)
            readout_pi_ensemble.append((readout_pi_block.name, 0))
            created_ensembles.append(readout_pi_ensemble)

        # Create the tau/waiting PulseBlockEnsemble
        # Get tau PulseBlockElement
        tau_element = self._get_idle_element(length=tau_step, increment=0)
        # Create PulseBlock and append PulseBlockElements
        tau_block = PulseBlock(name='{0}_tau'.format(name))
        tau_block.append(tau_element)
        created_blocks.append(tau_block)
        # Create PulseBlockEnsemble and append block to it
        tau_ensemble = PulseBlockEnsemble(name='{0}_tau'.format(name), rotating_frame=False)
        tau_ensemble.append((tau_block.name, 0))
        created_ensembles.append(tau_ensemble)

        # Create the PulseSequence and append the PulseBlockEnsemble names as sequence steps
        # together with the necessary parameters.
        t1_sequence = PulseSequence(name=name, rotating_frame=False)
        count_length = 0.0
        next_step = 1

        for k in k_array:
            t1_sequence.append(tau_ensemble.name)
            t1_sequence[-1].repetitions = int(k)
            count_length += k * self._get_ensemble_count_length(ensemble=tau_ensemble,
                                                                created_blocks=created_blocks)
            t1_sequence[-1].go_to = next_step
            next_step += 1

            if alternating:
                t1_sequence.append(readout_pi_ensemble.name)
                t1_sequence[-1].repetitions = int(1)
                t1_sequence[-1].go_to = next_step
                next_step += 1
                count_length += self._get_ensemble_count_length(ensemble=readout_pi_ensemble,
                                                                created_blocks=created_blocks)

                t1_sequence.append(tau_ensemble.name)
                t1_sequence[-1].repetitions = int(k)
                count_length += k * self._get_ensemble_count_length(ensemble=tau_ensemble,
                                                                    created_blocks=created_blocks)
                t1_sequence[-1].go_to = next_step
                next_step += 1

            t1_sequence.append(readout_ensemble.name)
            t1_sequence[-1].repetitions = int(1)
            t1_sequence[-1].go_to = next_step
            next_step += 1
            count_length += self._get_ensemble_count_length(ensemble=readout_ensemble,
                                                            created_blocks=created_blocks)

        # Make the sequence loop infinitely by setting the go_to parameter of the last sequence
        # step to the first step.
        t1_sequence[-1].go_to = 0

        # Trigger the calculation of parameters in the PulseSequence instance
        t1_sequence.refresh_parameters()

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        t1_sequence.measurement_information['alternating'] = alternating
        t1_sequence.measurement_information['laser_ignore_list'] = list()
        t1_sequence.measurement_information['controlled_variable'] = tau_array
        t1_sequence.measurement_information['units'] = ('s', '')
        t1_sequence.measurement_information['number_of_lasers'] = number_of_lasers
        # t1_sequence.measurement_information['counting_length'] = count_length
        t1_sequence.measurement_information['counting_length'] = self.laser_length + self.laser_delay
        t1_sequence.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        t1_sequence.measurement_information['iq_mixing'] = True

        # Append PulseSequence to created_sequences list
        created_sequences.append(t1_sequence)
        return created_blocks, created_ensembles, created_sequences


    def generate_t1_log_scale_chanel_0(self, name='t1_log_channel_0', tau_start=1.0e-6, tau_end=1.0e-3,
                              num_of_points=10, alternating=True):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Get logarithmically spaced steps in multiples of tau_start.
        # Note that the number of points and the position of the last point can change here.
        # set the minimum wait time to be tau_start/10, set repetitions accordingly
        tau_step = tau_start / 5
        if tau_step < 129e-9:  # this is the shortest segment allowed for the awg
            self.log.error('minimum segment size is 129ns, adjust pulse sequence parameters')
        k_exact = (np.logspace(0., np.log10(tau_end / tau_start), num_of_points)) * 5
        k_array = np.unique(np.rint(k_exact).astype(int))
        # get tau array for measurement ticks
        tau_array = k_array * tau_step

        # Create the readout PulseBlockEnsemble
        # Get necessary PulseBlockElements
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        # Create PulseBlock and append PulseBlockElements
        readout_block = PulseBlock(name='{0}_readout'.format(name))
        readout_block.append(laser_element)
        readout_block.append(delay_element)
        created_blocks.append(readout_block)
        # Create PulseBlockEnsemble and append block to it
        readout_ensemble = PulseBlockEnsemble(name='{0}_readout'.format(name), rotating_frame=False)
        readout_ensemble.append((readout_block.name, 0))
        created_ensembles.append(readout_ensemble)

        if alternating:
            # Create the alternating readout PulseBlockEnsemble
            # Get necessary PulseBlockElements
            laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
            delay_element = self._get_delay_gate_element()
            pi_element = self._get_iq_mix_element(length=self.rabi_period / 2,
                                                  increment=0,
                                                  amp=self.microwave_amplitude,
                                                  freq=self.iq_freq_shift,
                                                  phase=0)
            # Create PulseBlock and append PulseBlockElements
            readout_pi_block = PulseBlock(name='{0}_readout_pi'.format(name))
            readout_pi_block.append(pi_element)
            readout_pi_block.append(laser_element)
            readout_pi_block.append(delay_element)
            created_blocks.append(readout_pi_block)
            # Create PulseBlockEnsemble and append block to it
            readout_pi_ensemble = PulseBlockEnsemble(name='{0}_readout_pi'.format(name), rotating_frame=False)
            readout_pi_ensemble.append((readout_pi_block.name, 0))
            created_ensembles.append(readout_pi_ensemble)

        # Create the tau/waiting PulseBlockEnsemble
        # Get tau PulseBlockElement
        tau_element = self._get_idle_element(length=tau_step, increment=0)
        # Create PulseBlock and append PulseBlockElements
        tau_block = PulseBlock(name='{0}_tau'.format(name))
        tau_block.append(tau_element)
        created_blocks.append(tau_block)
        # Create PulseBlockEnsemble and append block to it
        tau_ensemble = PulseBlockEnsemble(name='{0}_tau'.format(name), rotating_frame=False)
        tau_ensemble.append((tau_block.name, 0))
        created_ensembles.append(tau_ensemble)

        # Create the PulseSequence and append the PulseBlockEnsemble names as sequence steps
        # together with the necessary parameters.
        t1_sequence = PulseSequence(name=name, rotating_frame=False)
        count_length = 0.0
        next_step = 1

        for k in k_array:
            t1_sequence.append(tau_ensemble.name)
            t1_sequence[-1].repetitions = int(k)
            count_length += k * self._get_ensemble_count_length(ensemble=tau_ensemble,
                                                                created_blocks=created_blocks)
            t1_sequence[-1].go_to = next_step
            next_step += 1

            if alternating:
                t1_sequence.append(readout_pi_ensemble.name)
                t1_sequence[-1].repetitions = int(1)
                t1_sequence[-1].go_to = next_step
                next_step += 1
                count_length += self._get_ensemble_count_length(ensemble=readout_pi_ensemble,
                                                                created_blocks=created_blocks)

                t1_sequence.append(tau_ensemble.name)
                t1_sequence[-1].repetitions = int(k)
                count_length += k * self._get_ensemble_count_length(ensemble=tau_ensemble,
                                                                    created_blocks=created_blocks)
                t1_sequence[-1].go_to = next_step
                next_step += 1

            t1_sequence.append(readout_ensemble.name)
            t1_sequence[-1].repetitions = int(1)
            t1_sequence[-1].go_to = next_step
            next_step += 1
            count_length += self._get_ensemble_count_length(ensemble=readout_ensemble,
                                                            created_blocks=created_blocks)

        # Make the sequence loop infinitely by setting the go_to parameter of the last sequence
        # step to the first step.
        t1_sequence[-1].go_to = 0

        # Trigger the calculation of parameters in the PulseSequence instance
        t1_sequence.refresh_parameters()

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        t1_sequence.measurement_information['alternating'] = alternating
        t1_sequence.measurement_information['laser_ignore_list'] = list()
        t1_sequence.measurement_information['controlled_variable'] = tau_array
        t1_sequence.measurement_information['units'] = ('s', '')
        t1_sequence.measurement_information['number_of_lasers'] = number_of_lasers
        # t1_sequence.measurement_information['counting_length'] = count_length
        t1_sequence.measurement_information['counting_length'] = self.laser_length + self.laser_delay
        t1_sequence.measurement_information['microwave_frequency'] = self.microwave_frequency - self.iq_freq_shift
        t1_sequence.measurement_information['iq_mixing'] = True

        # Append PulseSequence to created_sequences list
        created_sequences.append(t1_sequence)
        return created_blocks, created_ensembles, created_sequences

