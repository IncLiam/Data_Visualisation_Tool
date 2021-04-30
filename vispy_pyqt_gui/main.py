import csv
import os

from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QDateTime, Qt, QTimer, pyqtSignal, QRunnable, QThreadPool, QObject, pyqtSlot
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
                             QDial, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QProgressBar, QPushButton, QRadioButton, QScrollBar, QSizePolicy,
                             QSlider, QSpinBox, QStyleFactory, QTableWidget, QTabWidget, QTextEdit,
                             QVBoxLayout, QWidget, QDesktopWidget, QMainWindow, QInputDialog, QFileDialog)
import asyncio
import multiprocessing
import aioprocessing
from bleak import BleakClient
import logging
from matplotlib.pyplot import cm
import numpy as np
from vispy.util.transforms import ortho
import vispy.app
from vispy import color
from vispy import gloo
import serial
import json
import pyqtgraph as pg
import time

class LogToSpreadsheet:
    def __init__(self):
        self.logging_stop_event = aioprocessing.AioEvent()
        self.in_logging_process_event = aioprocessing.AioEvent()

    def start_logging_process(self, data_queue_logging, csv_path):
        self.Data_queue_logging = data_queue_logging
        self.logging_stop_event.clear()
        self.process2 = aioprocessing.AioProcess(target=self.logging_process, args=(csv_path,))
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


    def logging_process(self,csv_path):

        csv_file = open(csv_path, 'w', newline='')
        if not csv_file.writable():
            print("Error : CSV file is not writable")
            return False  # TODO : message d'erreur pour dire a l'utilisateur qu'il y a un soucis d'ecriture
        csv_writer = csv.writer(csv_file, dialect='excel')

        labels = ["Sensor "+str(i) for i in range(1,33)]   # TODO : nom des colonnes automatique ; ici, 32 capteurs
        csv_writer.writerow(labels)

        self.in_logging_process_event.set()

        while not self.logging_stop_event.is_set():
            array_to_log = self.Data_queue_logging.get()
            # print("Logging:", array_to_log) # Ne surtout pas activer
            if array_to_log is not None :
                # array_to_log est une matrice 8x4

                # On met les valeurs sur une seule ligne
                table=[]
                for L in array_to_log:
                    table += list(L)

                T = [ int(4095*x) for x in table ] # TODO : fonction de traitement des données ;
                # ici c'est pour passer de [0;1] à [[0;4095]] , à adapter selon le nombre de bit de l'ADC

                csv_writer.writerow(T) # enregistre dans le CSV la ligne
                csv_file.flush() # écrit dans le fichier immédiatement (évite de garder les données en cache)

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

# Class for simulating sensor matrix values
class ConnectionSimulation:
    def __init__(self):
        self.Sim_disconnect_event = aioprocessing.AioEvent()
        self.in_Sim_process_event = aioprocessing.AioEvent()

    def start_sim_process(self, data_queue_visuals, data_queue_logging):
        self.Data_queue_visuals = data_queue_visuals
        self.Data_queue_logging = data_queue_logging
        self.Sim_disconnect_event.clear()
        self.process1 = aioprocessing.AioProcess(target=self.sim_process, args=())
        self.process1.start()
        self.process1.join(1)  # if timeout is passed then connection established
        if not self.process1.is_alive():
            print("process1 joined")
            self.Data_queue_visuals.close()
            self.Data_queue_logging.close()
            self.process1.terminate()
            print("process1 ended \n", "Children processes still active:", multiprocessing.active_children())
            return False
        else:
            print("process1 started")
            return True

    def sim_process(self):
        self.in_Sim_process_event.set()

        # Fréquences aléatoires
        M = np.random.uniform(0, 1, (8, 4)).astype(np.float32)
        M = M.clip(min=0)
        M = np.rot90(M, 2)
        t = float(0)
        while not self.Sim_disconnect_event.is_set():

            # Gestion du temps
            fps = 60  # Nombre de MAP des 32 capteurs par secondes
            dt = 1 / fps
            time.sleep(dt) # Pour éviter de générer 12'000 mesures par seconde
            t += dt

            #matrix_values = np.random.uniform(0, 1, (8, 4)).astype(np.float32)
            #matrix_values = matrix_values.clip(min=0)
            #matrix_values = np.rot90(matrix_values, 2)

            x=3 # multiplicateur de vitesse de l'animation HEAT MAP
            matrix_values = (1+np.cos(t*M*x))/2 # Variation progressive des valeurs de chacun des capteurs

            if self.Data_queue_visuals.empty():
                self.Data_queue_visuals.put(matrix_values)  # wait for most recent value 4,2 0r 3,2 4,2 was used
            if self.Data_queue_logging.empty():
                self.Data_queue_logging.put(matrix_values)  # wait for most recent value 4,2 0r 3,2 4,2 was used



        # emptying data queues
        while not self.Data_queue_visuals.empty():
            self.Data_queue_visuals.get_nowait()
        while not self.Data_queue_logging.empty():
            self.Data_queue_logging.get_nowait()

        self.in_Sim_process_event.clear()

    def end_sim_process(self):  # also destroys process
        self.Sim_disconnect_event.set()
        self.process1.join()
        print("process1 joined")
        try:
            self.process1.terminate()
        except:
            print("process1 terminate failed")
            return False
        print("process1 ended")
        print("process1 ended \n", "Children processes still active:", multiprocessing.active_children())
        return True


# Class for Pyqtgraph plot for single sensor output
class PyqtgraphPlotSensor:

    def __init__(self, *args):

        self.args = args
        self.Data_queue = args[0]
        self.selected_sensor = args[1]
        self.new_data = 0.
        self.in_graph_event = aioprocessing.AioEvent()

        self.graphWidget = pg.GraphicsLayoutWidget()
        self.graphWidget.setBackground('w')
        self.p1 = self.graphWidget.addPlot()

        pen = pg.mkPen(color=(255, 165, 0), width=4)

        # single pressure
        self.data1 = np.random.uniform(0, 0, size=100)
        self.curve1 = self.p1.plot(self.data1, pen=pen)
        self.p1.setYRange(0, 0.8, padding=0)
        self.p1.setTitle("Single Pressure Sensor Airflow Detection")
        self.p1.hideAxis('bottom')
        self.p1.hideAxis('left')

        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(50)

    def update1(self):
        self.data1[:-1] = self.data1[1:]  # shift data in the array one sample left
        self.data1[-1] = self.new_data
        self.curve1.setData(self.data1)

    # update all plots
    def update(self):
        if not self.Data_queue.empty():
            self.q_data = self.Data_queue.get_nowait()
            # TODO create function to get sensor from int argument
            self.new_data = self.q_data[3, 1]
            # print(self.q_data)
            # print(self.new_data)
        self.update1()


# Class for Vispy Heat Map for sensors output
class CanvasSensors(vispy.app.Canvas):

    def __init__(self, *args):
        self.in_heatmap_event = aioprocessing.AioEvent()

        # Image to be displayed
        self.W, self.H = 8, 4
        self.I = np.random.uniform(0, 1, (self.W, self.H)).astype(np.float32)
        colors = color.get_colormap("jet").map(self.I).reshape(self.I.shape + (-1,))

        # A simple texture quad
        self.data = np.zeros(4, dtype=[('a_position', np.float32, 2),
                                       ('a_texcoord', np.float32, 2)])

        self.data['a_position'] = np.array([[0, 0], [self.W, 0], [0, self.H], [self.W, self.H]])
        self.data['a_texcoord'] = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])

        VERT_SHADER = """
        // Uniforms
        uniform mat4 u_model;
        uniform mat4 u_view;
        uniform mat4 u_projection;
        uniform float u_antialias;

        // Attributes
        attribute vec2 a_position;
        attribute vec2 a_texcoord;

        // Varyings
        varying vec2 v_texcoord;

        // Main
        void main (void)
        {
            v_texcoord = a_texcoord;
            gl_Position = u_projection * u_view * u_model * vec4(a_position,0.0,1.0);
        }
        """

        FRAG_SHADER = """
        uniform sampler2D u_texture;
        varying vec2 v_texcoord;
        void main()
        {
            gl_FragColor = texture2D(u_texture, v_texcoord);
            gl_FragColor.a = 1.0;
        }

        """

        vispy.app.Canvas.__init__(self, keys='interactive', size=((self.W * 20), (self.H * 20)))

        self.args = args
        print(args)
        if args:
            self.Data_queue = args[0]

        self.program = gloo.Program(VERT_SHADER, FRAG_SHADER)
        self.texture = gloo.Texture2D(colors, interpolation='linear', format='rgba')

        self.program['u_texture'] = self.texture
        self.program.bind(gloo.VertexBuffer(self.data))

        self.view = np.eye(4, dtype=np.float32)
        self.model = np.eye(4, dtype=np.float32)
        self.projection = np.eye(4, dtype=np.float32)

        self.program['u_model'] = self.model
        self.program['u_view'] = self.view
        self.projection = ortho(0, self.W, 0, self.H, -1, 1)
        self.program['u_projection'] = self.projection

        gloo.set_clear_color('white')

        self._timer = vispy.app.Timer('auto', connect=self.update, start=True)

    def on_resize(self, event):
        width, height = event.physical_size
        gloo.set_viewport(0, 0, width, height)
        self.projection = ortho(0, width, 0, height, -100, 100)
        self.program['u_projection'] = self.projection

        # Compute the new size of the quad
        r = width / float(height)
        R = self.W / float(self.H)
        if r < R:
            w, h = width, width / R
            x, y = 0, int((height - h) / 2)
        else:
            w, h = height * R, height
            x, y = int((width - w) / 2), 0
        self.data['a_position'] = np.array(
            [[x, y], [x + w, y], [x, y + h], [x + w, y + h]])
        self.program.bind(gloo.VertexBuffer(self.data))

    def on_draw(self, event):
        gloo.clear(color=True, depth=True)
        if self.args:
            if not self.Data_queue.empty():
                self.I[...] = self.Data_queue.get_nowait()
        else:
            self.I[...] = np.random.uniform(0, 1, (self.W, self.H)).astype(np.float32)

        colors = color.get_colormap("Oranges").map(self.I).reshape(self.I.shape + (-1,))  # YlOrBr
        self.texture.set_data(colors)
        self.program.draw('triangle_strip')

    def show_fps(self, fps):
        print("FPS - %.2f" % fps)


# Class containing all objects and methods for Bluetooth Serial stack connection and disconnection
class BTConnection:
    def __init__(self):
        self.bt_disconnect_event = aioprocessing.AioEvent()
        self.in_BT_process_event = aioprocessing.AioEvent()

    def start_bt_process(self, data_queue1):
        self.Data_queue1 = data_queue1

        self.bt_disconnect_event.clear()
        self.process1 = aioprocessing.AioProcess(target=self.bt_process, args=())
        self.process1.start()
        self.process1.join(1)  # if timeout is passed then connection established
        if not self.process1.is_alive():
            print("process1 joined")
            self.Data_queue1.close()
            self.process1.terminate()
            print("process1 ended \n", "Children processes still active:", multiprocessing.active_children())
            return False
        else:
            print("process1 started")
            return True

    def bt_process(self):
        self.in_BT_process_event.set()
        ser = serial.Serial('COM9', baudrate=9600, timeout=0.1)
        matrix_values = np.random.uniform(0, 1, (3, 1))

        while not self.bt_disconnect_event.is_set():
            ser.write(b'~')
            adc_json = ser.readline().decode('ascii')
            adc_dictionary = json.loads(adc_json)

            contact_temperature_value = adc_dictionary["Contact_t"]
            ir_object_temperature_value = adc_dictionary["Object_IR"]
            ir_ambient_temperature_value = adc_dictionary["Ambient_IR"]

            matrix_values[2, 0] = contact_temperature_value
            matrix_values[1, 0] = ir_ambient_temperature_value
            matrix_values[0, 0] = ir_object_temperature_value

            if self.Data_queue1.empty():
                self.Data_queue1.put(matrix_values)  # wait for most recent value

        self.in_BT_process_event.clear()

    def end_bt_process(self):  # also destroys process
        self.bt_disconnect_event.set()
        self.process1.join()
        print("process1 joined")
        try:
            self.process1.terminate()
        except:
            print("process1 terminate failed")
            return False
        print("process1 ended")
        print("process1 ended \n", "Children processes still active:", multiprocessing.active_children())
        return True


# Class containing all objects and methods for BLE stack connection and disconnection
class BLEConnection:
    def __init__(self):
        self.BLE_disconnect_event = aioprocessing.AioEvent()
        self.BLE_connection_event = aioprocessing.AioEvent()
        self.in_BLE_process_event = aioprocessing.AioEvent()

        self.address = "E2:B1:5D:0F:DC:5B"                                              # Arduino Device UUID
        self.char_uuid = "140984b8-72ba-494d-8707-80e9af77523a"                         # Arduino Characteristic UUID

    def start_ble_process(self, data_queue):
        self.Data_queue = data_queue
        self.BLE_connection_event.clear()
        self.BLE_disconnect_event.clear()
        self.process1 = aioprocessing.AioProcess(target=self.ble_process, args=())
        self.process1.start()
        self.process1.join(5)  # if timeout is passed then connection established
        if not self.process1.is_alive():
            print("process1 joined")
            self.Data_queue.close()
            self.process1.terminate()
            print("process1 ended \n", "Children processes still active:", multiprocessing.active_children())
            return False
        else:
            print("process1 started")
            return True

    def ble_process(self):
        print("In BLE process")
        self.in_BLE_process_event.set()

        async def run():
            def notification_handler(sender, data):
                """Simple notification handler which prints the data received."""
                if self.Data_queue.empty():
                    self.Data_queue.put(data)  # wait for most recent value
                    #print("Pressure Sensor Values: ", list(data))
                    # self.Data_queue1.get() # now that heat map will take

            async def ble_disconnect_waiter():
                """creates interrupt every second that checks for user disconnect input"""
                print('waiting for disconnect event from user...')
                while not self.BLE_disconnect_event.is_set():
                    await asyncio.sleep(1, result=True, loop=loop)
                print('... got the disconnect event !')
                while not self.Data_queue.empty():
                    try: self.Data_queue.get_nowait()
                    except: pass

            try:
                print("Attempting to enter Bleak Client")
                async with BleakClient(self.address, loop=loop) as client:
                    print("In Bleak Client")
                    x = await client.is_connected()
                    print("Connected: {0}".format(x), "\t[Characteristic] {0}: ".format(self.char_uuid))
                    self.BLE_connection_event.set()
                    await client.start_notify(self.char_uuid, notification_handler)
                    await asyncio.create_task(ble_disconnect_waiter())
                    await client.stop_notify(self.char_uuid)
                    print("Done in Bleak Client")
            except Exception as e:
                logging.exception(e)
                print("problem in Bleak Client")

        loop = asyncio.get_event_loop()
        loop.run_until_complete(run())
        print("BLE process done")
        self.in_BLE_process_event.clear()

    def end_ble_process(self):  # also destroys process
        self.BLE_disconnect_event.set()
        self.process1.join()
        print("process1 joined")
        try:
            self.process1.terminate()
        except:
            print("process1 terminate failed")
            return False
        print("process1 ended")
        print("process1 ended \n", "Children processes still active:", multiprocessing.active_children())
        return True


# Class containing all objects and methods for USB Serial stack connection and disconnection
class USBConnection:
    def __init__(self):
        self.USB_disconnect_event = aioprocessing.AioEvent()
        self.in_USB_process_event = aioprocessing.AioEvent()

    def start_usb_process(self, data_queue_visuals, data_queue_logging):
        self.Data_queue_visuals = data_queue_visuals
        self.Data_queue_logging = data_queue_logging
        self.USB_disconnect_event.clear()
        self.process1 = aioprocessing.AioProcess(target=self.usb_process, args=())
        self.process1.start()
        self.process1.join(5)  # if timeout is passed then connection established
        if not self.process1.is_alive():
            print("process1 joined")
            self.Data_queue_visuals.close()
            self.Data_queue_logging.close()
            self.process1.terminate()
            print("process1 ended \n", "Children processes still active:", multiprocessing.active_children())
            return False
        else:
            print("process1 started")
            return True

    def usb_process(self):
        self.in_USB_process_event.set()
        try:
            ser = serial.Serial('COM5', baudrate=115200, timeout=0.1)  # USB
        except:
            print("did not connect to COM5 serial")
            self.in_USB_process_event.clear()
            return
        init_matrix_values = np.random.uniform(0, 1, (8, 4)).astype(np.float32)
        matrix_values = np.random.uniform(0, 1, (8, 4)).astype(np.float32)

        for i in range(2): # read twice because first reading too much noise
            ser.write(b'~')
            adc_json = ser.readline().decode('ascii')

        adc_dictionary = json.loads(adc_json)

        init_matrix_values[1, 0] = adc_dictionary["ADC0_0"] / 256
        init_matrix_values[1, 1] = adc_dictionary["ADC0_1"] / 256
        init_matrix_values[1, 2] = adc_dictionary["ADC0_2"] / 256
        init_matrix_values[1, 3] = adc_dictionary["ADC0_3"] / 256
        init_matrix_values[0, 0] = adc_dictionary["ADC0_4"] / 256
        init_matrix_values[0, 1] = adc_dictionary["ADC0_5"] / 256
        init_matrix_values[0, 2] = adc_dictionary["ADC0_6"] / 256
        init_matrix_values[0, 3] = adc_dictionary["ADC0_7"] / 256
        init_matrix_values[3, 0] = adc_dictionary["ADC1_0"] / 256
        init_matrix_values[3, 1] = adc_dictionary["ADC1_1"] / 256
        init_matrix_values[3, 2] = adc_dictionary["ADC1_2"] / 256
        init_matrix_values[3, 3] = adc_dictionary["ADC1_3"] / 256
        init_matrix_values[2, 0] = adc_dictionary["ADC1_4"] / 256
        init_matrix_values[2, 1] = adc_dictionary["ADC1_5"] / 256
        init_matrix_values[2, 2] = adc_dictionary["ADC1_6"] / 256
        init_matrix_values[2, 3] = adc_dictionary["ADC1_7"] / 256
        init_matrix_values[5, 3] = adc_dictionary["ADC2_0"] / 256
        init_matrix_values[5, 2] = adc_dictionary["ADC2_1"] / 256
        init_matrix_values[5, 1] = adc_dictionary["ADC2_2"] / 256
        init_matrix_values[5, 0] = adc_dictionary["ADC2_3"] / 256
        init_matrix_values[4, 3] = adc_dictionary["ADC2_4"] / 256
        init_matrix_values[4, 2] = adc_dictionary["ADC2_5"] / 256
        init_matrix_values[4, 1] = adc_dictionary["ADC2_6"] / 256
        init_matrix_values[4, 0] = adc_dictionary["ADC2_7"] / 256
        init_matrix_values[7, 3] = adc_dictionary["ADC3_0"] / 256
        init_matrix_values[7, 2] = adc_dictionary["ADC3_1"] / 256
        init_matrix_values[7, 1] = adc_dictionary["ADC3_2"] / 256
        init_matrix_values[7, 0] = adc_dictionary["ADC3_3"] / 256
        init_matrix_values[6, 3] = adc_dictionary["ADC3_4"] / 256
        init_matrix_values[6, 2] = adc_dictionary["ADC3_5"] / 256
        init_matrix_values[6, 1] = adc_dictionary["ADC3_6"] / 256
        init_matrix_values[6, 0] = adc_dictionary["ADC3_7"] / 256

        while not self.USB_disconnect_event.is_set():
            ser.write(b'~')
            adc_json = ser.readline().decode('ascii')
            adc_dictionary = json.loads(adc_json)

            matrix_values[1, 0] = adc_dictionary["ADC0_0"]/256
            matrix_values[1, 1] = adc_dictionary["ADC0_1"]/256
            matrix_values[1, 2] = adc_dictionary["ADC0_2"]/256
            matrix_values[1, 3] = adc_dictionary["ADC0_3"]/256
            matrix_values[0, 0] = adc_dictionary["ADC0_4"]/256
            matrix_values[0, 1] = adc_dictionary["ADC0_5"]/256
            matrix_values[0, 2] = adc_dictionary["ADC0_6"]/256
            matrix_values[0, 3] = adc_dictionary["ADC0_7"]/256
            matrix_values[3, 0] = adc_dictionary["ADC1_0"]/256
            matrix_values[3, 1] = adc_dictionary["ADC1_1"]/256
            matrix_values[3, 2] = adc_dictionary["ADC1_2"]/256
            matrix_values[3, 3] = adc_dictionary["ADC1_3"]/256
            matrix_values[2, 0] = adc_dictionary["ADC1_4"]/256
            matrix_values[2, 1] = adc_dictionary["ADC1_5"]/256
            matrix_values[2, 2] = adc_dictionary["ADC1_6"]/256
            matrix_values[2, 3] = adc_dictionary["ADC1_7"]/256
            matrix_values[5, 3] = adc_dictionary["ADC2_0"]/256
            matrix_values[5, 2] = adc_dictionary["ADC2_1"]/256
            matrix_values[5, 1] = adc_dictionary["ADC2_2"]/256
            matrix_values[5, 0] = adc_dictionary["ADC2_3"]/256
            matrix_values[4, 3] = adc_dictionary["ADC2_4"]/256
            matrix_values[4, 2] = adc_dictionary["ADC2_5"]/256
            matrix_values[4, 1] = adc_dictionary["ADC2_6"]/256
            matrix_values[4, 0] = adc_dictionary["ADC2_7"]/256
            matrix_values[7, 3] = adc_dictionary["ADC3_0"]/256
            matrix_values[7, 2] = adc_dictionary["ADC3_1"]/256
            matrix_values[7, 1] = adc_dictionary["ADC3_2"]/256
            matrix_values[7, 0] = adc_dictionary["ADC3_3"]/256
            matrix_values[6, 3] = adc_dictionary["ADC3_4"]/256
            matrix_values[6, 2] = adc_dictionary["ADC3_5"]/256
            matrix_values[6, 1] = adc_dictionary["ADC3_6"]/256
            matrix_values[6, 0] = adc_dictionary["ADC3_7"]/256

            matrix_values = - matrix_values + init_matrix_values
            matrix_values = matrix_values.clip(min=0)
            matrix_values = np.rot90(matrix_values, 2)

            #print(matrix_values)

            if self.Data_queue_visuals.empty():
                self.Data_queue_visuals.put(matrix_values)  # wait for most recent value 4,2 0r 3,2 4,2 was used
            if self.Data_queue_logging.empty():
                self.Data_queue_logging.put(matrix_values)  # wait for most recent value 4,2 0r 3,2 4,2 was used

        # emptying data queues
        while not self.Data_queue_visuals.empty():
            self.Data_queue_visuals.get_nowait()
        while not self.Data_queue_logging.empty():
            self.Data_queue_logging.get_nowait()

        self.in_USB_process_event.clear()

    def end_usb_process(self):  # also destroys process
        self.USB_disconnect_event.set()
        self.process1.join()
        print("process1 joined")
        try:
            self.process1.terminate()
        except:
            print("process1 terminate failed")
            return False
        print("process1 ended")
        print("process1 ended \n", "Children processes still active:", multiprocessing.active_children())
        return True


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
        self.createTopLeftGroupBox()
        self.createTopRightGroupBox()
        self.createTopMiddleGroupBox()
        self.createBottomRightGroupBox()

        self.mainLayout.addWidget(self.topLeftGroupBox, 0, 0, 1, 1)
        self.mainLayout.addWidget(self.topMiddleGroupBox, 0, 1, 1, 1)
        self.mainLayout.addWidget(self.topRightGroupBox, 0, 2, 1, 1)
        self.mainLayout.addWidget(self.bottomRightGroupBox, 1, 2, 1, 1)  # row, col, vertical stretch, horizontal stretch

        # Ne pas activer les tailles minimales sinon inutilisable sur les écrans 720p
        #self.mainLayout.setColumnMinimumWidth(2, 400)  # col, stretch
        #self.mainLayout.setColumnMinimumWidth(1, 600)  # col, stretch
        #self.mainLayout.setColumnMinimumWidth(0, 400)
        #self.mainLayout.setRowMinimumHeight(1, 1000)

        self.mainLayout.setColumnStretch(0, 3)  # col, stretch
        self.mainLayout.setColumnStretch(2, 3)
        self.mainLayout.setColumnStretch(1, 4)

        self.mainLayout.setRowStretch(1, 8)  # row, stretch
        self.mainLayout.setRowStretch(0, 2)

        self.setLayout(self.mainLayout)

        self.setWindowTitle("Hyve Dynamics Data Visualisation Tool")
        QApplication.setStyle(QStyleFactory.create("Fusion"))

        # Removing help "?" button
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.CustomizeWindowHint |
            QtCore.Qt.WindowTitleHint |
            QtCore.Qt.WindowCloseButtonHint
            #  QtCore.Qt.WindowStaysOnTopHint # Ne surtout pas activer, pas du tout ergonomique
        )

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

    def createTopLeftGroupBox(self):
        self.topLeftGroupBox = QGroupBox("Connection")

        Button0 = QPushButton("Connect to Temp Sensor via BT")
        Button0.setStyleSheet("background-color: none; "
                                #"height: 100px; "
                                #"width: 200px; "
                                )
        Button1 = QPushButton("Connect to Skin via BLE")
        Button1.setStyleSheet("background-color: none; "
                                #"height: 100px; "
                                #"width: 200px; "
                                )
        Button2 = QPushButton("Connect to Sensors")
        Button2.setStyleSheet("background-color: none; "
                              # "height: 100px; "
                              # "width: 200px; "
                              )

        Button3 = QPushButton("Connect to Sensors")
        Button3.setStyleSheet("background-color: none; "
                              # "height: 100px; "
                              # "width: 200px; "
                              )
        Button4 = QPushButton("Simulate Connection to sensors")
        Button4.setStyleSheet("background-color: none; "
                                   #"height: 100px; "
                                   #"width: 200px; "
                                   )

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
            self.Data_queue1 = aioprocessing.AioQueue()  # added every time as joining closes the queue

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
            self.Data_queue = aioprocessing.AioQueue()  # added every time as joining closes thr queue
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

    def createTopMiddleGroupBox(self):
        self.topMiddleGroupBox = QGroupBox("About")

        text = QLabel(
            "<center>" \
            "<img src=../images/hyve_1080w.png/>" \
            "<p>Data Visualisation Tool<br/>" \
            "Version 1.0<br/>" \
            "Copyright &copy; Hyve Dynamics Ltd.</p>" \
            "</center>")

        layout = QVBoxLayout()
        layout.addWidget(text)
        #layout.addStretch(1)
        self.topMiddleGroupBox.setLayout(layout)

    def createTopRightGroupBox(self):
        self.topRightGroupBox = QGroupBox("Visuals")

        Button4 = QPushButton("Show Heat Map")
        Button4.setStyleSheet("background-color: none; "
                                   # "height: 100px; "
                                   # "width: 200px; "
                                   )
        Button5 = QPushButton("Hide Visuals")
        Button5.setStyleSheet("background-color: none; "
                                   # "height: 100px; "
                                   # "width: 200px; "
                                   )
        Button6 = QPushButton("Show Graph Plot")
        Button6.setStyleSheet("background-color: none; "
                                   # "height: 100px; "
                                   # "width: 200px; "
                                   )

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
                print("connect to sensors ?")
            buttons_enabler()
        Button4.clicked.connect(show_heat_map)

        # Graph plots push button setup
        def show_graph_plot():
            buttons_disabler()
            hide_visuals()
            selected_sensor = self.get_sensor()
            if not selected_sensor:
                return
            try:
                self.add_graph_sensor(self.Data_queue_visuals, selected_sensor)
            except:
                print("connect to sensors ?")
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




    def createBottomRightGroupBox(self):
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
            "<img src=../images/hyve_icon_180.png>" \
            "<br/>" \
            "<img src=../images/hyve_icon_180.png>" \
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
                print("not addded logging : ", ex) # Affiche l'erreur

        def delete_logging():
            try:
                self.remove_logging()
            except:
                print("did not remove logging")

        Button2.clicked.connect(delete_logging)
        Button1.clicked.connect(create_logging)



    # USB connection adder
    def add_usb_connection(self):  # create and start usb serial connection
        self.Data_queue_visuals = aioprocessing.AioQueue()  # added every time as joining closes the queue
        self.Data_queue_logging = aioprocessing.AioQueue()  # added every time as joining closes the queue
        if self.usb_connection.start_usb_process(self.Data_queue_visuals, self.Data_queue_logging):
            print("added USB Connection")
            # self.add_heat_map_sensors(self.Data_queue_visuals)
            return True
        else:
            return False

    # Simulation connection adder
    def add_sim_connection(self):  # create and start usb serial connection
        self.Data_queue_visuals = aioprocessing.AioQueue()  # added every time as joining closes the queue
        self.Data_queue_logging = aioprocessing.AioQueue()  # added every time as joining closes the queue
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
        if not csv_path.lower().endswith(".csv"): # force CSV extension
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
        i, okPressed = QInputDialog.getInt(self, "Sensor Selection", "Input Sensor Position: 0 <= X <= 30             "
                                                                     "                 ", 0, 0, 30, 1)
        if okPressed:
            print(i)
            return i




# Main method runs the GUI

if __name__ == '__main__':
    import sys

    multiprocessing.set_start_method('spawn', force=False)

    app = QApplication(sys.argv)
    main_window = GuiMainWindow()

    def end_connections():
        main_window.connection_killer()

    app.aboutToQuit.connect(end_connections)
    sys.exit(app.exec_())