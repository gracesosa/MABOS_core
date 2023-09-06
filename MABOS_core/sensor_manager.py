from MABOS_core.data.data_manager import *
from MABOS_core.memory.mem_manager import *
from MABOS_core.serial.ser_manager import *
import multiprocessing
from warnings import warn
import threading
import os
import sys
import pickle
def setup_process_start_method():
    if sys.platform.startswith('win'):
        multiprocessing.set_start_method("spawn", force=True)
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin') or sys.platform.startswith('darwin'):
        multiprocessing.set_start_method("fork", force=True)
    else:
        raise EnvironmentError('Unsupported platform')


def setup_queue(dict: dict):
    """ Setup queue to hold dynamic parameter dictionaries
    :param dict: dictionary of parameters to put into queue
    :return: queue object
    """
    q = multiprocessing.Queue()
    q.put(dict)
    return q


class SensorManager:
    def __init__(self, channel_key: Union[np.ndarray, str], commport: str, num_points: int = 1000,
                 window_size: int = 1, baudrate: int = 115200):
        """ Initialize SensorManager Class
        Initializes serial port, shared memory object, and kwarg dictionary (args_dict)
        :param channel_key: list of channel names
        :param commport: target serial port
        :param num_points: number of 'time' points [num_points = time(s) * Hz]
        :param window_size: for 1D data, number of timepoints to acquire before passing
        :param baudrate: target baudrate
        """

        # Ensures all resources available to parent process are identical to child process. Needed for windows & macOS
        setup_process_start_method()

        mutex = create_mutex()

        self.ser = setup_serial(commport, baudrate)
        self.window_size = window_size
        self.shm, data_shared, self.plot = create_shared_block(grid_plot_flag=True,
                                                               channel_key=channel_key,
                                                               num_points=num_points)

        self.args_dict = {
            "channel_key": channel_key,
            "commport": commport,
            "baudrate": baudrate,
            "mutex": mutex,
            "ser": self.ser,
            "shm_name": self.shm.name,
            "plot": self.plot,
            "shape": data_shared.shape,
            "dtype": data_shared.dtype
        }

        self.dynamic_args_dict = {
            "num_points": num_points,
            "window_size": self.window_size
        }
        self.stat_q = setup_queue(dict=self.args_dict)
        self.dyn_q = setup_queue(dict=self.dynamic_args_dict)

    def update_process(self, save_data: bool = True):
        """ Initialize dedicated process to update data

        :param save_data: boolean flag. If true, save acquired data to file and RAM, if not just update it in RAM
        :return: pointer to process
        """

        if save_data:
            p = multiprocessing.Process(name='update',
                                        target=update_save_data,
                                        args=(self.stat_q, self.dyn_q,))
        else:
            p = multiprocessing.Process(name='update',
                                        target=update_data,
                                        args=(self.stat_q, self.dyn_q,))
        return p

    def update_params(self, params: dict):
        """ Check validity and update parameters

        :param params: dictionary of parameters to update
        :return: updates queue with new dictionary
        """
        master_keys = self.dynamic_args_dict.keys()
        for param_key in params.keys():
            if param_key in master_keys:
                self.dynamic_args_dict[f"{param_key}"] = params[f"{param_key}"]
                self.update_queue(self.dyn_q)
            else:
                warn(f"Parameter key {param_key} does not exist in dynamic parameter dictionary\n"
                     f"{self.dynamic_args_dict}")

    def update_queue(self, q):
        """ Adding item to existing queue object

        :param q: Queue object
        """
        q.put(self.dynamic_args_dict)
