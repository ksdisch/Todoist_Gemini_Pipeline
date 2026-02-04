import traceback
from PySide6.QtCore import QRunnable, Slot, QObject, Signal

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    Supported signals are:
    started
        No data
    finished
        object data (result of the function)
    failed
        object data (the exception instance)
    """
    started = Signal()
    finished = Signal(object)
    failed = Signal(object)  # passing the exception object

class Worker(QRunnable):
    """
    Worker thread for generic background tasks.
    Inherits from QRunnable to handle worker thread setup, signals and wrap-up.
    
    :param fn: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function
    """
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        try:
            self.signals.started.emit()
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            traceback.print_exc()
            self.signals.failed.emit(e)
        else:
            self.signals.finished.emit(result)
