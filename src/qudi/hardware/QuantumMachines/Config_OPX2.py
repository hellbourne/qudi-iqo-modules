# from qm.QuantumMachinesManager import QuantumMachinesManager
import numpy as np
# from qm import SimulationConfig, ConfigHelper
# from qm import LoopbackInterface
# import matplotlib.pyplot as plt
# import time
from scipy import special
x = np.linspace(-3, 3,200)
Rise_up = special.erf(x)*0.24+0.24
Rise_down = special.erf(x)*(-0.24)+0.24
noise_init = np.zeros(200)

NV_IF = 150e6
NV_LO = 1.8e9-NV_IF

e_IF = 200e6
e_LO = 1.4e9-e_IF

# IF_freq = 150e6
# rad_freq = 200e6
# LO_freq = 1.5e9-IF_freq

config = {

    'version': 1,

    'controllers': {

        'finkler1': {
            'type': 'opx2',
            'analog_outputs': {
                1: {'offset': 0.01407},  # I
                2: {'offset': 0.01286},  # Q
                3: {'offset': 0.01407},  # I
                4: {'offset': 0.01286},  # Q
                5: {'offset': 0}, # N
                6: {'offset': 0}, # Noise
            },
            'digital_outputs': {
                1: {'offset': 0.0},
                2: {'offset': 0.0},
                7: {'offset': 0.0},
                8: {'offset': 0.0},
                9: {'offset': 0.0},
            },  # laser
            'analog_inputs': {
                1: {'offset': -0.032},  # readout1
                2: {'offset': -0.037},  # readout2

            }
        }
    },

    'elements': {

        'qubit': {
            'mixInputs': {
                'I': ('finkler1', 1),
                'Q': ('finkler1', 2),
                'lo_frequency': NV_LO,
                'mixer': 'mixer_NV'
            },
            'intermediate_frequency': NV_IF,
            # 'digitalInputs': {
            #     "ttl_in": {
            #         "port": ("finkler1", 7),
            #         "delay": 136,
            #         "buffer": 15,
            #     },
            #     "ttl_check": {
            #         "port": ("finkler1", 8),
            #         "delay": 136,
            #         "buffer": 15,
            #     },
            # },
            'operations': {
                'MW_pi': 'MW_pi_pulse',
            }
        },
        'qubit2': {
            'mixInputs': {
                'I': ('finkler1', 3),
                'Q': ('finkler1', 4),
                'lo_frequency': e_LO,
                'mixer': 'mixer_e'
            },
            'intermediate_frequency': e_IF,
            'digitalInputs': {
                "ttl_in": {
                    "port": ("finkler1", 7),
                    "delay": 136,
                    "buffer": 15,
                },
                "ttl_check": {
                    "port": ("finkler1", 8),
                    "delay": 136,
                    "buffer": 15,
                },
            },
            'operations': {
                'MW_e': 'MW_e_pulse',
            }
        },

        'radical': {
            'mixInputs': {
                'I': ('finkler1', 3),
                'Q': ('finkler1', 4),
                'lo_frequency': e_LO,
                'mixer': 'mixer_e'
            },
            'intermediate_frequency': e_IF,
            'digitalInputs': {
                "ttl_in": {
                    "port": ("finkler1", 7),
                    "delay": 136,
                    "buffer": 15,
                },
                "ttl_check": {
                    "port": ("finkler1", 8),
                    "delay": 136,
                    "buffer": 15,
                },
            },
            'operations': {
                'MW_e': 'MW_e_pulse',
            }
        },

        'nuclear': {
            'singleInput': {
                'port': ('finkler1', 5),
                },
            'intermediate_frequency': 300e6,

            'operations': {
                'nuclear_pi': 'nuclear_pi_pulse',
                'nuclear_rise': 'nuclear_rise_pulse',
                'nuclear_down': 'nuclear_down_pulse'
            },
            },

        'noise': {
            'singleInput': {
                'port': ('finkler1', 6),
                },
            'intermediate_frequency': 0,
            'operations': {
                'inject_noise1': 'noise_pulse1',
                'inject_noise2': 'noise_pulse2',
                'inject_noise3': 'noise_pulse3'
            },
            },

        'radical_2': {
            'mixInputs': {
                'I': ('finkler1', 1),
                'Q': ('finkler1', 2),
                'lo_frequency': NV_LO,
                'mixer': 'mixer_NV'
            },
            'intermediate_frequency': NV_IF,
            # 'digitalInputs': {
            #     "ttl_in": {
            #         "port": ("finkler1", 7),
            #         "delay": 136,
            #         "buffer": 15,
            #     },
            #     "ttl_check": {
            #         "port": ("finkler1", 8),
            #         "delay": 136,
            #         "buffer": 15,
            #     },
            # },
            'operations': {
                'MW_pi': 'MW_pi_pulse',
            }
        },




        "laser": {
            'digitalInputs': {
                "laser_in": {
                    "port": ("finkler1", 1),
                    "delay": 0,
                    "buffer": 0,
                },
            },
            'operations': {
                'laser_pulse': 'laser_trig_pulse',
            }
        },

        'readout1': {

            # open: fake
            "singleInput": {
                "port": ("finkler1", 1)
            },
            # close: fake

            # 'digitalInputs': {
            #     "tt_in": {
            #         "port": ("finkler1", 4),
            #         "delay": 0,
            #         "buffer": 0,
            #     },
            # },

            'operations': {
                'readout': 'readout_pulse',
            },
            "outputs": {
                'out1': ("finkler1", 1)
            },
            'time_of_flight': 28,
            'smearing': 0,
            # 'outputPulse': [int(-arg) for arg in apd_pulse]
            'outputPulseParameters': {
                'signalThreshold': -300,
                'signalPolarity': 'Descending',
                'derivativeThreshold': -50,
                'derivativePolarity': 'Descending'
            }
        },

         'readout2': {

             # open: fake
             "singleInput": {
                 "port": ("finkler1", 1)
             },
             # close: fake

             # 'digitalInputs': {
             #     "tt_in": {
             #         "port": ("finkler1", 3),
             #         "delay": 0,
             #         "buffer": 0,
             #     },
             # },

             'operations': {
                 'readout': 'readout_pulse',
             },
             "outputs": {
                 'out1': ("finkler1", 2)
             },
             'time_of_flight': 28,
             'smearing': 0,
             # 'outputPulse': [int(-arg) for arg in apd_pulse2]
             'outputPulseParameters': {
                'signalThreshold': -300,
                'signalPolarity': 'Descending',
                'derivativeThreshold': -50,
                'derivativePolarity': 'Descending'}
         },

        "NI": {
            'digitalInputs': {
                "NI_in": {
                    "port": ("finkler1", 2),
                    "delay": 0,
                    "buffer": 0,
                },
            },
            'operations': {
                'follow': 'follow_pulse',
            }
        },
    },

    "pulses": {
        'MW_pi_pulse': {
            'operation': "control",
            'length': 24*4,
            'waveforms': {
                "I": "const_wf",
                "Q": "zero_wf",
            },
            'digital_marker': 'ON'
        },

        'noise_pulse1': {
            'operation': "control",
            'length': 200,
            'waveforms': {
                'single': 'noise_wf1'
            },
        },

        'noise_pulse2': {
            'operation': "control",
            'length': 200,
            'waveforms': {
                'single': 'noise_wf2'
            },
        },

        'noise_pulse3': {
            'operation': "control",
            'length': 200,
            'waveforms': {
                'single': 'noise_wf3'
            },
        },

        'MW_e_pulse': {
            'operation': "control",
            'length': 24*4,
            'waveforms': {
                "I": "const_wf",
                "Q": "zero_wf"
            },
            'digital_marker': 'ON'
        },

        'MW_pi_pulse2': {
            'operation': "control",
            'length': 24*4,
            'waveforms': {
                "I": "const_wf",
                "Q": "zero_wf"
            },
        },

        'nuclear_pi_pulse': {
            'operation': 'control',
            'length': 24*4,
            'waveforms': {
                'single': 'const_nuclear_wf',
            },
            # 'digital_marker': 'ON'
        },

        'nuclear_rise_pulse': {
            'operation': 'control',
            'length': 200,
            'waveforms': {
                'single': 'rise_nuclear_wf',
            },
            # 'digital_marker': 'ON'
        },

        'nuclear_down_pulse': {
            'operation': 'control',
            'length': 200,
            'waveforms': {
                'single': 'down_nuclear_wf',
            },
            # 'digital_marker': 'ON'
        },


        'laser_trig_pulse': {
            'operation': "control",
            'length': 100,
            'digital_marker': 'ON'
        },

        'follow_pulse': {
            'operation': "control",
            'length': 80,
            'digital_marker': 'ON'
        },

        'readout_pulse': {
            'operation': "measurement",
            "length": 2000,
            "waveforms": {
                "single": "zero_wf"  # fake!
            },
            'digital_marker': 'ON',
        },
    },

    'waveforms': {
        "const_wf": {
            "type": "constant",  # arbitrary give list og amps
            "sample": 0.4  # need to give samples
        },

        "zero_wf": {
            "type": "constant",
            "sample": 0.0
        },

        'rise_nuclear_wf': {
            "type": "arbitrary",  # arbitrary give list og amps
            "samples": Rise_up
        },

        'down_nuclear_wf': {
            "type": "arbitrary",  # arbitrary give list og amps
            "samples": Rise_down
        },

        'const_nuclear_wf': {
            "type": "constant",  # arbitrary give list og amps
            "sample": 0.48 # need to give samples
        },
        'noise_wf1': {
            "type": "arbitrary",  # arbitrary give list og amps
            'is_overridable': True,
            "samples": noise_init
        },
        'noise_wf2': {
            "type": "arbitrary",  # arbitrary give list og amps
            "samples": noise_init
        },
        'noise_wf3': {
            "type": "arbitrary",  # arbitrary give list og amps
            "samples": noise_init
        },
    },

    "digital_waveforms": {
        "ON": {
            "samples": [(1, 0)]  # (on/off, ns)
        }
    },

    "mixers": {
        'mixer_NV': [
            {'intermediate_frequency': NV_IF, 'lo_frequency': NV_LO, 'correction': [1.18,  0.19,  0.24,  0.96]}  # SSB (Both (-) left (+) right)
            # {'intermediate_frequency': NV_IF, 'lo_frequency': NV_LO, 'correction': [1.0,  0.0,  0.0,  1.0]}  # SSB (Both (-) left (+) right)

        ],
        'mixer_e': [
            {'intermediate_frequency': e_IF, 'lo_frequency': e_LO, 'correction': [1.18,  0.19,  0.24,  0.96]},  # SSB (Both (-) left (+) right)
            # {'intermediate_frequency': e_IF, 'lo_frequency': e_LO, 'correction': [1.0,  0.0,  0.0,  1.0]}  # SSB (Both (-) left (+) right)

        ]
    },
}

# qmm = QuantumMachinesManager()
# qm = qmm.open_qm(config)