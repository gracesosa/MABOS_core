import MABOS_core.memory.mem_manager as mm
from .plot_utils import *
from typing import *
from multiprocessing.shared_memory import SharedMemory
from MABOS_core.utils.utils import DictManager


class PlotManager(DictManager):
    def __init__(self, static_args_dict, online: bool = True, multiproc: bool = True):
        DictManager.__init__(self, online=online,
                             multiproc=multiproc)

        self.update_dictionary(args_dict=static_args_dict,
                               dict_type="static")
        # Unpack static_args_dict
        self.select_dict_to_unpack()
        # Set grid_plot_flag
        if self.num_channel > 1:
            self.grid_plot_flag = True
        elif self.num_channel == 1:
            self.grid_plot_flag = False
        else:
            raise ValueError(f"Number of Channels {self.num_channel} \n"
                             f"defined as the number of columns in channel_key {self.channel_key} \n"
                             f"is an invalid number")
        self.plot = None

    def initialize_plot(self):
        """ Handler for initializing Plot/GridPlot
        :return: Calls function to initialize Plot or GridPlot
        """

        if self.grid_plot_flag:
            self.plot, data = self._initialize_grid_plot()
        else:
            self.plot, data = self._initialize_plot()

    def _initialize_plot(self):
        """ Initialize Plot object and data
        :return: Plot object and data
        """
        plot = create_plot(channel_key=self.channel_key)
        xs, ys = initialize_plot_data(num_points=self.num_points)
        plot_data = np.dstack([xs, ys])[0]
        plot.add_line(data=plot_data, name=self.channel_key[0], cmap='jet')
        plot.auto_scale(maintain_aspect=False)
        data = np.vstack((xs, ys))
        return plot, data

    def _initialize_grid_plot(self):
        """ Initialize GridPlot object and data
        :return: GridPlot object and data
        """
        grid_plot = create_grid_plot(channel_key=self.channel_key)
        xs, ys = initialize_grid_plot_data(num_channel=self.num_channel, num_points=self.num_points)
        for i, subplot in enumerate(grid_plot):
            plot_data = np.dstack([xs, ys[i]])[0]
            subplot.add_line(data=plot_data, name=self.channel_key[i], cmap='jet')
        data = np.vstack((xs, ys))
        return grid_plot, data

    def online_plot_data(self):
        """ Update Plot data with shared memory object data
        :return: no explicit return. Updates Plot data, next render cycle will show updated data
        """
        # Acquire Shared Memory Object data
        mm.acquire_mutex(self.mutex)
        shm = SharedMemory(self.shm_name)
        data_shared = np.ndarray(shape=self.shape, dtype=self.dtype,
                                 buffer=shm.buf)
        data = np.dstack([data_shared[0], data_shared[1]])[0]
        self.plot[self.channel_key[0]].data = data
        self.plot.auto_scale(maintain_aspect=False)
        mm.release_mutex(self.mutex)

    def online_grid_plot_data(self):
        """ Update GridPlot data with shared memory object data
        :return: no explicit return. Updates GridPlot data, next render cycle will show updated data
        """
        # Acquire Shared Memory Object data
        mm.acquire_mutex(self.mutex)
        shm = SharedMemory(self.shm_name)
        data_shared = np.ndarray(shape=self.shape, dtype=self.dtype,
                                 buffer=shm.buf)
        for i, subplot in enumerate(self.plot):
            data = np.dstack([data_shared[0], data_shared[i + 1]])[0]
            subplot[self.channel_key[i]].data = data
            subplot.auto_scale(maintain_aspect=False)
        mm.release_mutex(self.mutex)
