import sys
import os
from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QGridLayout, QGroupBox, QLabel, QPushButton, QSizePolicy, QStyleFactory,
                             QVBoxLayout, QWidget, QDesktopWidget, QInputDialog, QFileDialog)
from aioprocessing import AioQueue
from Visuals import *
from Connections import *
from SpreadsheetLogging import *

from multiprocessing import freeze_support
freeze_support()


# Class containing GUI setup and basic functions
class GuiMainWindow(QWidget):
    def __init__(self, parent=None):
        super(GuiMainWindow, self).__init__(parent)

        # Initialising (creating instances of) all connection classes, BLE, USB, BT classic
        self.ble_connection = BLEConnection()
        self.usb_connection = USBConnection()
        self.bt_connection = BTConnection()
        self.spreadsheet_logging = LogToSpreadsheet()
        self.sim_connection = ConnectionSimulation()

        self.mainLayout = QGridLayout()

        # Initialising the widgets
        self.create_top_left_group_box()
        self.create_top_right_group_box()
        self.create_top_middle_group_box()
        self.create_bottom_right_group_box()

        self.mainLayout.addWidget(self.topLeftGroupBox, 0, 0, 1, 1)
        self.mainLayout.addWidget(self.topMiddleGroupBox, 0, 1, 1, 1)
        self.mainLayout.addWidget(self.topRightGroupBox, 0, 2, 1, 1)
        self.mainLayout.addWidget(self.bottomRightGroupBox, 1, 2, 1, 1)
        # row, col, vertical stretch, horizontal stretch

        # attention les tailles minimales sinon inutilisable sur les écrans 720p
        self.mainLayout.setColumnMinimumWidth(2, 300)  # col, stretch
        # self.mainLayout.setColumnMinimumWidth(1, 600)  # col, stretch
        self.mainLayout.setColumnMinimumWidth(0, 300)
        self.mainLayout.setRowMinimumHeight(1, 750)

        self.mainLayout.setColumnStretch(0, 1)  # col, stretch
        self.mainLayout.setColumnStretch(2, 1)
        self.mainLayout.setColumnStretch(1, 2)

        self.mainLayout.setRowStretch(1, 8)  # row, stretch
        self.mainLayout.setRowStretch(0, 2)

        self.setLayout(self.mainLayout)

        self.setWindowTitle("Data Visualisation Tool")
        QApplication.setStyle(QStyleFactory.create("Fusion"))

        # Removing help "?" button
        self.setWindowFlags(
            Qt.Window |
            Qt.CustomizeWindowHint |
            Qt.WindowTitleHint |
            Qt.WindowCloseButtonHint
            # QtCore.Qt.WindowStaysOnTopHint # Ne surtout pas activer, pas du tout ergonomique
        )

        self.setWindowIcon(QtGui.QIcon('images/icon.ico'))

        # Adding Maximise and Minimise buttons to window
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.show()
        self.center()

    def remove_heat_map(self):
        self.canvas._timer.stop()
        self.bottomLeftGroupBox.setParent(None)
        QApplication.processEvents()

    def remove_graph(self):
        self.graph1.timer.stop()
        self.bottomLeftGroupBox.setParent(None)
        QApplication.processEvents()

    def add_heat_map_sensors(self, *args):
        print(args)

        self.bottomLeftGroupBox = None
        self.bottomLeftGroupBox = QGroupBox("Heat Map")

        self.canvas = None
        self.canvas = CanvasSensors(args[0])  # if queue given as arg
        self.canvas.measure_fps(1, self.canvas.show_fps)

        layout = None
        layout = QVBoxLayout()
        layout.addWidget(self.canvas.native)
        self.bottomLeftGroupBox.setLayout(layout)

        self.mainLayout.addWidget(self.bottomLeftGroupBox, 1, 0, 1, 2)
        self.setLayout(self.mainLayout)
        self.show()

    def add_graph_sensor(self, *args):
        self.bottomLeftGroupBox = None
        self.bottomLeftGroupBox = QGroupBox("Graph Plot")
        print(args[0])
        print(args[1])

        self.graph1 = None
        self.plotWidget1 = None

        self.graph1 = PyqtgraphPlotSensor(args[0], args[1])

        self.plotWidget1 = self.graph1.graphWidget

        layout = None
        layout = QVBoxLayout()
        layout.addWidget(self.plotWidget1)

        self.bottomLeftGroupBox.setLayout(layout)

        self.mainLayout.addWidget(self.bottomLeftGroupBox, 1, 0, 1, 2)
        self.setLayout(self.mainLayout)
        self.show()

    def create_top_left_group_box(self):
        self.topLeftGroupBox = QGroupBox("Connection")

        Button0 = QPushButton("Connect via BT")
        Button0.setStyleSheet("background-color: none; ")
        Button1 = QPushButton("Connect via BLE")
        Button1.setStyleSheet("background-color: none; ")
        Button2 = QPushButton("Connect via USB")
        Button2.setStyleSheet("background-color: none; ")
        Button3 = QPushButton("Disconnect")
        Button3.setStyleSheet("background-color: none; ")
        Button4 = QPushButton("Simulate")
        Button4.setStyleSheet("background-color: none; ")

        Button0.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        Button1.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        Button2.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        Button3.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        Button4.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

        layout = QVBoxLayout()
        # layout.addWidget(Button0)
        # layout.addWidget(Button1)
        layout.addWidget(Button2)
        layout.addWidget(Button3)
        layout.addWidget(Button4)

        self.topLeftGroupBox.setLayout(layout)

        def buttons_enabler():
            Button0.setEnabled(True)
            Button1.setEnabled(True)
            Button2.setEnabled(True)
            Button3.setEnabled(True)
            Button4.setEnabled(True)
            QApplication.processEvents()

        def buttons_disabler():
            Button0.setDisabled(True)
            Button1.setDisabled(True)
            Button2.setDisabled(True)
            Button3.setDisabled(True)
            Button4.setDisabled(True)
            QApplication.processEvents()

        buttons_enabler()

        # BT push buttons setup
        def create_bt_connection():  # create and start the BLE connection
            buttons_disabler()
            self.Data_queue1 = AioQueue()  # added every time as joining closes the queue

            if self.bt_connection.start_bt_process(self.Data_queue1):
                # show graph1 plot, non sim,  with queue
                self.add_graph_sensor(self.Data_queue1)
                buttons_disabler()
                Button3.setEnabled(True)
            else:
                buttons_enabler()

            def delete_bt_connection():
                buttons_disabler()
                if self.bt_connection.end_bt_process():
                    # remove plot
                    self.remove_graph()
                    buttons_enabler()
                else:
                    buttons_disabler()
                    Button3.setEnabled(True)

            Button3.clicked.connect(delete_bt_connection)
        Button0.clicked.connect(create_bt_connection)

        # BLE push buttons setup
        def create_ble_connection():  # create and start the BLE connection
            buttons_disabler()
            self.Data_queue = AioQueue()  # added every time as joining closes thr queue
            if self.ble_connection.start_ble_process(self.Data_queue):
                buttons_disabler()
            else:
                buttons_enabler()

            def delete_ble_connection():
                buttons_disabler()
                if self.ble_connection.end_ble_process():
                    buttons_enabler()
                else:
                    buttons_disabler()
                    Button3.setEnabled(True)

            Button3.clicked.connect(delete_ble_connection)
        Button1.clicked.connect(create_ble_connection)

        # USB push button setup (to be modified)
        def create_usb_connection():  # create and start usb serial connection
            buttons_disabler()
            if self.add_usb_connection():
                print("adding usb")
                buttons_disabler(), Button3.setEnabled(True)
            else:
                delete_connections()
                buttons_enabler()
        Button2.clicked.connect(create_usb_connection)

        def create_simulation():  # create and start usb serial connection
            buttons_disabler()
            if self.add_sim_connection():
                print("adding simulation")
                buttons_disabler(), Button3.setEnabled(True)
            else:
                delete_connections()
                buttons_enabler()
        Button4.clicked.connect(create_simulation)

        def delete_connections():
            buttons_disabler()
            self.connection_killer()
            buttons_enabler()
        Button3.clicked.connect(delete_connections)

    def create_top_middle_group_box(self):
        self.topMiddleGroupBox = QGroupBox("About")

        text = QLabel(
            "<center>" \
            "<img src=images/1080w.png/>" \
            "<p>Data Visualisation Tool<br/>" \
            "Version 1.0</p>" \
            "</center>")

        layout = QVBoxLayout()
        layout.addWidget(text)
        # layout.addStretch(1)
        self.topMiddleGroupBox.setLayout(layout)

    def create_top_right_group_box(self):
        self.topRightGroupBox = QGroupBox("Visuals")

        Button4 = QPushButton("Heat Map")
        Button4.setStyleSheet("background-color: none; ")
        Button5 = QPushButton("Hide Visuals")
        Button5.setStyleSheet("background-color: none; ")
        Button6 = QPushButton("Graph Plot")
        Button6.setStyleSheet("background-color: none; ")

        Button4.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        Button5.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        Button6.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

        layout = QVBoxLayout()
        layout.addWidget(Button4)
        layout.addWidget(Button5)
        layout.addWidget(Button6)
        # layout.addStretch(1)
        self.topRightGroupBox.setLayout(layout)

        def buttons_enabler():
            Button4.setEnabled(True)
            Button5.setEnabled(True)
            Button6.setEnabled(True)
            QApplication.processEvents()

        def buttons_disabler():
            Button4.setDisabled(True)
            Button5.setDisabled(True)
            Button6.setDisabled(True)
            QApplication.processEvents()

        buttons_enabler()

        # Heat map push button setup
        def show_heat_map():
            buttons_disabler()
            hide_visuals()
            try:
                self.add_heat_map_sensors(self.Data_queue_visuals)
            except:
                print("connected ?")
            buttons_enabler()
        Button4.clicked.connect(show_heat_map)

        # Graph plots push button setup
        def show_graph_plot():
            buttons_disabler()
            hide_visuals()
            selected_sensor = self.get_sensor()
            try:
                print(selected_sensor)
                self.add_graph_sensor(self.Data_queue_visuals, selected_sensor)
            except:
                print("connected?")
            buttons_enabler()
        Button6.clicked.connect(show_graph_plot)

        def hide_visuals():
            try:
                self.remove_heat_map()
            except:
                pass
            try:
                self.remove_graph()
            except:
                pass
        Button5.clicked.connect(hide_visuals)

    def create_bottom_right_group_box(self):
        self.bottomRightGroupBox = QGroupBox("Data")

        Button1 = QPushButton("Start Logging")
        Button1.setStyleSheet("background-color: none; "
                                   # "height: 100px; "
                                   # "width: 200px; "
                                   )
        Button2 = QPushButton("Stop Logging")
        Button2.setStyleSheet("background-color: none; "
                              # "height: 100px; "
                              # "width: 200px; "
                              )

        Button1.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        Button2.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

        text = QLabel(
            "<center>" \
            "<img src=images/icon_180.png>" \
            "<br/>" \
            "<img src=images/icon_180.png>" \
            "</center>")

        layout = QVBoxLayout()
        layout.addWidget(Button1)
        layout.addWidget(Button2)
        layout.addWidget(text)
        #layout.addStretch(1)
        self.bottomRightGroupBox.setLayout(layout)

        Button1.setEnabled(True)
        Button2.setEnabled(True)

        # Logging push button setup
        def create_logging():  # create and start usb serial connection
            try:
                self.add_logging()
                print("adding logging")
            except Exception as ex:
                print("not addded logging : ", ex)

        def delete_logging():
            try:
                self.remove_logging()
            except:
                print("did not remove logging")

        Button2.clicked.connect(delete_logging)
        Button1.clicked.connect(create_logging)

    # USB connection adder
    def add_usb_connection(self):  # create and start usb serial connection
        self.Data_queue_visuals = AioQueue()  # added every time as joining closes the queue
        self.Data_queue_logging = AioQueue()  # added every time as joining closes the queue
        if self.usb_connection.start_usb_process(self.Data_queue_visuals, self.Data_queue_logging):
            print("added USB Connection")
            # self.add_heat_map_sensors(self.Data_queue_visuals)
            return True
        else:
            return False

    # Simulation connection adder
    def add_sim_connection(self):  # create and start usb serial connection
        self.Data_queue_visuals = AioQueue()  # added every time as joining closes the queue
        self.Data_queue_logging = AioQueue()  # added every time as joining closes the queue
        if self.sim_connection.start_sim_process(self.Data_queue_visuals, self.Data_queue_logging):
            print("added Simulation Connection")
            # self.add_heat_map_sensors(self.Data_queue_visuals)
            return True
        else:
            return False

    # logging is only possible if sensors are connected
    def add_logging(self):
        # Ask for CSV file to log
        csv_path = QFileDialog.getSaveFileName(self, 'Save CSV', os.getenv('HOME'), 'CSV (*.csv)', 'CSV (*.csv)', QFileDialog.DontUseNativeDialog)
        if csv_path[0] == '':
            return False # Cancel
        csv_path = csv_path[0]
        if not csv_path.lower().endswith(".csv"):  # force CSV extension
            csv_path += ".csv"

        if self.spreadsheet_logging.start_logging_process(self.Data_queue_logging,csv_path):
            print("added logging")
            return True
        else:
            return False

    def remove_logging(self):
        self.spreadsheet_logging.end_logging_process()
        print("ended logging")

    # ends all possible connections
    def connection_killer(self):
        # visuals removed before closing connections
        try: self.remove_heat_map()
        except: pass
        try: self.remove_graph()
        except: pass
        if self.spreadsheet_logging.in_logging_process_event.is_set():
            self.spreadsheet_logging.end_logging_process()
            print("killed logging")
        if self.ble_connection.in_BLE_process_event.is_set():
            self.ble_connection.end_ble_process()
            print("killed ble")
        if self.usb_connection.in_USB_process_event.is_set():
            self.usb_connection.end_usb_process()
            print("killed usb")
        if self.bt_connection.in_BT_process_event.is_set():
            self.bt_connection.end_bt_process()
            print("killed bt")
        if self.sim_connection.in_Sim_process_event.is_set():
            self.sim_connection.end_sim_process()
            print("killed sim")

    # for centering a window on screen
    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    # get sensor selection from user
    def get_sensor(self):
        i, ok_pressed = QInputDialog.getInt(self, "Point Selection",
                                            "Input Sensor Position: 0 <= X <= 30            "
                                            "                 ", 15, 0, 30, 1)
        print(i)
        return i


# Main method runs the GUI
if __name__ == '__main__':

    multiprocessing.set_start_method('spawn', force=False)

    app = QApplication(sys.argv)
    main_window = GuiMainWindow()

    def end_connections():
        main_window.connection_killer()

    app.aboutToQuit.connect(end_connections)
    sys.exit(app.exec_())
