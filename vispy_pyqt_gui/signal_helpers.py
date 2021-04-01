"""Functions for communicating between processes and threads with the GUI"""


# Class for a pyqtSignal that can create and emit() it (NOT USED)
class SignalsClass(QObject):

    Signal = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        QtCore.QObject.__init__(self)

    def boil(self):
        self.Signal.emit()


# Class for defining a worker thread that listens for a multiprocess event set then emits a pyqtSignal (NOT USED)
class Worker(QRunnable):
    """Worker thread"""
    def __init__(self, pot, event):  # pot is a pyqtsignal
        super(Worker, self).__init__()
        self.pot = pot
        self.event = event

    @pyqtSlot()
    def run(self):
        """Your code goes in this function"""
        print("in run of heat_map_worker")
        while True:
            if self.event.is_set():
                print("detected event set")
                self.event.clear()
                self.pot.boil()