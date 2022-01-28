import multiprocessing
from aioprocessing import AioEvent
from aioprocessing import AioProcess
from bleak import BleakClient
import logging
import numpy as np
import time
import serial
import json
import asyncio


# Class containing all objects and methods for Bluetooth Serial stack connection and disconnection
class BTConnection:
    def __init__(self):
        self.bt_disconnect_event = AioEvent()
        self.in_BT_process_event = AioEvent()

    def start_bt_process(self, data_queue1):
        self.Data_queue1 = data_queue1

        self.bt_disconnect_event.clear()
        self.process1 = AioProcess(target=self.bt_process, args=())
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
        self.BLE_disconnect_event = AioEvent()
        self.BLE_connection_event = AioEvent()
        self.in_BLE_process_event = AioEvent()

        self.address = "E2:B1:5D:0F:DC:5B"                                              # Arduino Device UUID
        self.char_uuid = "140984b8-72ba-494d-8707-80e9af77523a"                         # Arduino Characteristic UUID

    def start_ble_process(self, data_queue):
        self.Data_queue = data_queue
        self.BLE_connection_event.clear()
        self.BLE_disconnect_event.clear()
        self.process1 = AioProcess(target=self.ble_process, args=())
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
        self.USB_disconnect_event = AioEvent()
        self.in_USB_process_event = AioEvent()

    def start_usb_process(self, data_queue_visuals, data_queue_logging):
        self.Data_queue_visuals = data_queue_visuals
        self.Data_queue_logging = data_queue_logging
        self.USB_disconnect_event.clear()
        self.process1 = AioProcess(target=self.usb_process, args=())
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


# Class for simulating sensor matrix values
class ConnectionSimulation:
    def __init__(self):
        self.Sim_disconnect_event = AioEvent()
        self.in_Sim_process_event = AioEvent()

    def start_sim_process(self, data_queue_visuals, data_queue_logging):
        self.Data_queue_visuals = data_queue_visuals
        self.Data_queue_logging = data_queue_logging
        self.Sim_disconnect_event.clear()
        self.process1 = AioProcess(target=self.sim_process, args=())
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