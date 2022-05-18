import csv
import multiprocessing
from aioprocessing import AioEvent
from aioprocessing import AioProcess


class LogToSpreadsheet:
    def __init__(self):
        self.logging_stop_event = AioEvent()
        self.in_logging_process_event = AioEvent()

    def start_logging_process(self, data_queue_logging, csv_path):
        self.Data_queue_logging = data_queue_logging
        self.logging_stop_event.clear()
        self.process2 = AioProcess(target=self.logging_process, args=(csv_path,))
        self.process2.start()
        self.process2.join(1)  # if timeout is passed then connection established
        if not self.process2.is_alive():
            print("process2 joined")
            self.Data_queue_logging.close()
            self.process2.terminate()
            print("process2 ended \n", "Children processes still active:", multiprocessing.active_children())
            return False
        else:
            print("process2 started")
            return True

    def logging_process(self, csv_path):

        csv_file = open(csv_path, 'w', newline='')
        if not csv_file.writable():
            print("Error : CSV file is not writable")
            return False  # TODO : create error message
        csv_writer = csv.writer(csv_file, dialect='excel')

        labels = ["Sensor "+str(i) for i in range(1, 33)]   # TODO : create automatic sensor number detection
        csv_writer.writerow(labels)

        self.in_logging_process_event.set()

        while not self.logging_stop_event.is_set():
            array_to_log = self.Data_queue_logging.get()
            if array_to_log is not None:
                table = []
                for L in array_to_log:
                    table += list(L)
                T = [int(4095*x) for x in table]  # TODO : analyse this section and adapt to input
                csv_writer.writerow(T)
                csv_file.flush()

        self.in_logging_process_event.clear()

    def end_logging_process(self):
        self.logging_stop_event.set()
        self.process2.join()
        print("process2 joined")
        try:
            self.process2.terminate()
        except:
            print("process2 terminate failed")
            return False
        print("process2 ended")
        print("process2 ended \n", "Children processes still active:", multiprocessing.active_children())
        return True