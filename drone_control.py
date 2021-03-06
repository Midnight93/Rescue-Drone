# -*- coding: cp1255 -*-
# -*- coding: utf-8 -*-

import os
import signal
import pickle
import socket
import struct
import subprocess
import threading
from multiprocessing import Process
import vehicle
import report
import setting
import time
from Tkinter import *
from mttkinter import mtTkinter
import cv2
from PIL import Image, ImageTk
from winsound import *

############################################# person detection ##############################################################
class PersonDetection:
    #the class run the person_detection.py, and read msg if the person_detection send a msg that detection person.
    def __init__(self, drone_vehicle_obj,type_cam,gui_obj):
        self.gui = gui_obj
        self.drone_vehicle = drone_vehicle_obj
        self.listener = True
        self.gui.show_msg_monitor(">> Start detection process", 'msg')
        if type_cam == 1:
            person_detection = "py person_detection.py 1" # launch the person_detection script using bash
        else:
            person_detection = "py person_detection.py 0"  # launch the person_detection script using bash
        self.person_detection_process = subprocess.Popen(person_detection, shell=True, stdout=subprocess.PIPE)

        # msg thread,if the camera detection person msg send to drone_vehicle.person_detected()
        self.person_detection_msg = threading.Thread(name='person_detection_msg', target=self.detection_msg)
        self.person_detection_msg.start()

    # close the process that start the person_detection.py file.call from GUI.disconnect function.
    def close_detection(self):
        self.listener = False
        self.person_detection_msg.join()
        self.person_detection_process.kill()


    def detection_msg(self):
        while self.listener:
            msg_detection = self.person_detection_process.stdout.readline().rstrip('\n')
            if not msg_detection:
                break
            if msg_detection is not None:
                try:
                    self.drone_vehicle.person_detected()
                except:
                    continue


###############################################################################################################################
##################################################### Gui #####################################################################
###############################################################################################################################

class Gui:
    """the class gui responsible for running all classes,the class creates the gui and the control panel."""
    def __init__(self, master):
        master.geometry("950x690")
        master.title("Rescue Drone")
        master.iconbitmap(r"media\rd.ico")
        self.detection_obj=None #this Obj its person detection class
        self.socket_video=None  #the socket_video assigned to receive video from person_detection file.
        self.message_box_pop = False
        self.message_box = None   #this LabelFrame create when have message from system\person detection etc..
        self.repo = report.Report()
        self.setting = setting.Setting(master,self)
        self.setting.get_db().delete('','locations') # reset firebase database
        self.__count_person = 0 #how many person to send gps to dataBase
        self.drone_vehicle = vehicle.DroneControl(self,self.repo,self.setting)
        self.low_battery = False
        self.drone_control = None
        self.video_window = None
        self.monitor_msg = None
        self.info = None
        self.get_image = False
        self.drone_is_connect = False  # this bool to know if the system connected to the drone and video system
        self.sitl_is_connect = False  # this bool to know if the system connected to the simulator

        # create the main frame to rows and columns.
        for x in xrange(5):
            master.grid_rowconfigure(x, weight=1)
        for y in xrange(6):
            master.grid_columnconfigure(y, weight=1)



        # create panel for control drone
        self.create_drone_control_panel(master)
        # create panel for video from drone
        self.create_video_panel(master)
        # msg_drone frames
        self.create_monitor_msg(master)

        self.show_msg_monitor(">> Welcome to Rescue Drone software", 'msg')

        master.protocol("WM_DELETE_WINDOW", lambda:self.on_closing(master))


    def create_video_panel(self,master):
        """the function create the area of video window."""
        self.video_window = Label(master, width=65, height=26, borderwidth=2, relief="groove", bg="gray")
        self.video_window.grid(row=0, column=0, sticky=W + N + E + S, padx=5, pady=5)

    def create_drone_control_panel(self,master):
        """ the function create the drone_control frames."""
        self.drone_control = Frame(master, bg='gray')

        for x in xrange(4):
            self.drone_control.grid_rowconfigure(x, weight=1)
        for y in xrange(3):
            self.drone_control.grid_columnconfigure(y, weight=1)


        self.drone_control.grid(row=0, column=1, columnspan=5, sticky=W + N + E + S)

        """button connect to drone"""
        self.button_connect = Button(self.drone_control, text="Drone \nConnect", width=9, height=2,bg='#C70002',fg='WHITE',
                                     command=lambda: self.switch_on_off(master, 'drone'))
        self.button_connect.grid(row=0, column=1, sticky=W + N, pady=4)

        """button connect to SITL"""
        self.button_connect_sitl = Button(self.drone_control, text="Sitl \nConnect", width=9, height=2,bg='#C70002',fg='WHITE',#5CB300
                                          command=lambda: self.switch_on_off(master, 'sitl'))
        self.button_connect_sitl.grid(row=0, column=0, sticky=W + N, padx=4, pady=4)

        """button image capture"""
        self.image_capture = Button(self.drone_control,state=DISABLED, text="Image\ncapture", width=9, height=2,
                                          command=self.get_image_function)
        self.image_capture.grid(row=0, column=2, sticky=W + N, padx=4, pady=4)

        """button AUTO mode"""
        self.button_auto = Button(self.drone_control, state=DISABLED, text="Auto Search", width=9, height=3,
                                  command=self.send_auto_mode)
        self.button_auto.grid(row=1, column=0, columnspan=1, sticky=W + N, padx=4, pady=4)

        """button LOITER mode"""
        self.button_loiter = Button(self.drone_control, state=DISABLED, text="Loiter", width=9, height=3,
                                  command=self.send_loiter_mode)
        self.button_loiter.grid(row=1, column=1, columnspan=1, sticky=W + N, padx=4, pady=4)

        """button GUIDED mode"""
        self.button_manual = Button(self.drone_control, state=DISABLED, text="Guided", width=9, height=3, command=self.send_manual_mode)
        self.button_manual.grid(row=1, column=2, columnspan=1, sticky=W + N, pady=4)

        """button RTL mode"""
        self.button_rtl = Button(self.drone_control, state=DISABLED, text="RTL", width=9, height=3, command=self.send_rtl_mode)
        self.button_rtl.grid(row=1, column=3, columnspan=1, sticky=W + N, padx=4, pady=4)

    def create_monitor_msg(self,master):
        """the function create the monitor msg"""
        indication_frame = Frame(master, height=200, bg='gray')
        for x in xrange(2):
            indication_frame.grid_rowconfigure(x, weight=1)
        for y in xrange(5):
            indication_frame.grid_columnconfigure(y, weight=1)

        indication_frame.grid(row=1, column=0, columnspan=6, rowspan=5, sticky=W + N + E + S)

        # frame for msg from the drone and software
        self.monitor_msg = Text(indication_frame, width=30, background='black')
        self.monitor_msg.grid(row=0, column=0,columnspan=4, sticky=W + N + S + E)
        scrollbar = Scrollbar(indication_frame)
        scrollbar.grid(row=0, column=3, sticky=E + N + S )
        self.monitor_msg.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.monitor_msg.yview)
        self.monitor_msg.tag_configure("success", foreground='#00B400')
        self.monitor_msg.tag_configure("error", foreground='#e60000')
        self.monitor_msg.tag_configure("person", foreground='#00C5CD')
        self.monitor_msg.tag_configure("msg", foreground='#ffffff')
        self.create_info_panel(indication_frame)

    def create_info_panel(self,indication_frame):
        """the function create the area of info from drone and the button to control drone from the keyboard"""
        self.info = Frame(indication_frame, bg='#282828')
        for x in xrange(10):
            indication_frame.grid_rowconfigure(x, weight=1)
        for y in xrange(8):
            indication_frame.grid_columnconfigure(y, weight=1)

        self.info.grid(row=0, column=4, columnspan=7, sticky=W +  N + S + E)

        self.altitude_label = Label(self.info, text="Altitude (m)",font=('Arial', 10), fg="white",bg='#282828')
        self.altitude_label.grid(row=0, column=0,padx=10)
        self.altitude_info = Label(self.info, text="0.00",font=('Arial', 20), fg="#BA55D3", bg='#282828')
        self.altitude_info.grid(row=1,column=0,padx=10)

        self.ground_speed_label = Label(self.info, text="Ground Speed (m/s)", font=('Arial', 10), fg="white", bg='#282828')
        self.ground_speed_label.grid(row=2, column=0, padx=10)
        self.ground_speed_info = Label(self.info, text="0.00", font=('Arial', 20), fg="#00FF00", bg='#282828')
        self.ground_speed_info.grid(row=3, column=0, padx=10)

        self.dist_to_home_label = Label(self.info, text="Dist to Home (m)", font=('Arial', 10), fg="white",bg='#282828')
        self.dist_to_home_label.grid(row=4, column=0, padx=10)
        self.dist_to_home_info = Label(self.info, text="0.00", font=('Arial', 20), fg="#00FFFF", bg='#282828')
        self.dist_to_home_info.grid(row=5, column=0, padx=10)

        self.bat_volt_label = Label(self.info, text="Bat Voltage (V)", font=('Arial', 10), fg="white",bg='#282828')
        self.bat_volt_label.grid(row=6, column=0, padx=10)
        self.bat_volt_info = Label(self.info, text="0.00", font=('Arial', 20), fg="#FFD700", bg='#282828')
        self.bat_volt_info.grid(row=7, column=0, padx=10)

        self.time_air = Label(self.info, text="Air time ", font=('Arial', 10), fg="white", bg='#282828')
        self.time_air.grid(row=0, column=1, padx=10)
        self.time_air_info = Label(self.info, text="00:00:00", font=('Arial', 20), fg="#FFD700", bg='#282828')
        self.time_air_info.grid(row=1, column=1, padx=10)

        self.lon =  Label(self.info, text="Longitude ", font=('Arial', 10), fg="white", bg='#282828')
        self.lon.grid(row=4, column=1, padx=10)
        self.lon_info = Label(self.info, text="00.0000000", font=('Arial', 20), fg="red", bg='#282828')
        self.lon_info.grid(row=5, column=1, padx=10)

        self.lat = Label(self.info, text="Latitude ", font=('Arial', 10), fg="white", bg='#282828')
        self.lat.grid(row=6, column=1, padx=10)
        self.lat_info = Label(self.info, text="00.0000000", font=('Arial', 20), fg="blue", bg='#282828')
        self.lat_info.grid(row=7, column=1, padx=10)

        self.keyboard_control_bool = BooleanVar()
        button_keyboard_control = Checkbutton(self.drone_control, text="Keyboard \n control", bg='gray',
                                              activebackground='gray', variable=self.keyboard_control_bool,
                                              command=self.show_keyboard_control)
        button_keyboard_control.grid(row=0, column=0, sticky=W + S, pady=4)

        self.move_up = Button(self.info, state=DISABLED, text="Up\n W", width=4, height=2)
        self.move_up.grid(row=1, column=3, columnspan=1, sticky=E + N, padx=2, pady=2)
        self.move_dwon = Button(self.info, state=DISABLED, text="Dwon\n S", width=4, height=2)
        self.move_dwon.grid(row=2, column=3, columnspan=1, sticky=E + N, padx=2, pady=2)
        self.spin_right = Button(self.info, state=DISABLED, text="Spin" + u'\u23f5'+"\n D", width=4, height=2)
        self.spin_right.grid(row=2, column=4, columnspan=1, sticky=E + N, padx=2, pady=2)
        self.spin_left = Button(self.info, state=DISABLED, text=u'\u23f4' + "Spin\n A", width=4, height=2)
        self.spin_left.grid(row=2, column=2, columnspan=1, sticky=E + N, padx=2, pady=2)

        self.move_forward = Button(self.info, state=DISABLED, text=u'\u23f6', width=4, height=2)
        self.move_forward.grid(row=1, column=6, columnspan=1, sticky=E + N, padx=2, pady=2)
        self.move_back = Button(self.info, state=DISABLED, text=u'\u23f7', width=4, height=2)
        self.move_back.grid(row=2, column=6, columnspan=1, sticky=E + N, padx=2, pady=2)
        self.move_right = Button(self.info, state=DISABLED, text=u'\u23f5', width=4, height=2)
        self.move_right.grid(row=2, column=7, columnspan=1, sticky=N + S, padx=2, pady=2)
        self.move_left = Button(self.info, state=DISABLED, text=u'\u23f4', width=4, height=2)
        self.move_left.grid(row=2, column=5, columnspan=1, sticky=E + N, padx=2, pady=2)

    def show_keyboard_control(self):
        """the function shows / hides the button that control drone from keyboard"""

        if self.keyboard_control_bool.get() is True: #shows

            self.move_up.config(state=NORMAL)
            self.move_dwon.config(state=NORMAL)
            self.spin_right.config(state=NORMAL)
            self.spin_left.config(state=NORMAL)
            self.move_forward.config(state=NORMAL)
            self.move_back.config(state=NORMAL)
            self.move_right.config(state=NORMAL)
            self.move_left.config(state=NORMAL)

        elif self.keyboard_control_bool.get() is False: #hides

            self.move_up.config(state=DISABLED)
            self.move_dwon.config(state=DISABLED)
            self.spin_right.config(state=DISABLED)
            self.spin_left.config(state=DISABLED)
            self.move_forward.config(state=DISABLED)
            self.move_back.config(state=DISABLED)
            self.move_right.config(state=DISABLED)
            self.move_left.config(state=DISABLED)

    def send_auto_mode(self):
        """this function send to drone move to AUTO mode"""
        auto = threading.Thread(name='drone connect', target=self.drone_vehicle.auto_mode)
        auto.start()
    def send_loiter_mode(self):
        """this function send to drone move to LOITER mode ,need a remote controle"""
        self.drone_vehicle.loiter_mode()

    def send_manual_mode(self):
        """this function send to drone move to GUIDED mode"""
        self.drone_vehicle.manual_mode()

    def send_rtl_mode(self):
        """this function send to drone move to RTL mode"""
        rtl = threading.Thread(name='drone connect', target=self.drone_vehicle.rtl_mode)
        rtl.start()

    def allow_deny_button(self,key):
        """the function show/hides the button if the drone is connect/disconnect"""
        if key == 'allow':
            self.image_capture.config(state=NORMAL,bg='#E38608',fg='white')
            self.button_auto.config(state=NORMAL,bg='#0B407C',fg='white')
            self.button_loiter.config(state = NORMAL,bg='#0B407C',fg='white')
            self.button_manual.config(state=NORMAL,bg='#0B407C',fg='white')
            self.button_rtl.config(state=NORMAL,bg='#0B407C',fg='white')
        elif key == 'deny':
            self.image_capture.config(state=DISABLED,bg='white')
            self.button_auto.config(state=DISABLED,bg='white')
            self.button_loiter.config(state=DISABLED, bg='white')
            self.button_manual.config(state=DISABLED,bg='white')
            self.button_rtl.config(state=DISABLED,bg='white')

    def switch_on_off(self, master, key):
        """the functionn manages the connect / disconnect drone and accordingly show / hides buttons and text"""
        if key == 'drone':
            if self.sitl_is_connect is False:
                if self.drone_is_connect is False:
                    self.button_connect.config(text="Drone \nDisconnect", bg='#5CB300')
                    self.button_connect_sitl.config(state=DISABLED, bg='white')
                    self.drone_is_connect = True
                    self.drone_connect(key, master)
                else:
                    if self.drone_vehicle.drone_connected is True:
                        if self.drone_vehicle.vehicle.armed is False:
                            self.button_connect.config(text="Drone \nConnect", bg='#C70002')
                            self.button_connect_sitl.config(state=NORMAL, bg='#C70002')
                            self.drone_is_connect = False
                            self.allow_deny_button('deny')
                            disconnect_thread = threading.Thread(name='disconnect from drone',
                                                                 target=lambda: self.disconnect(key, master))
                            disconnect_thread.start()
                        else:
                            self.show_msg_monitor(">> Attention! You have to land the drone before Disconnect", "error")
                    else:
                        self.show_msg_monitor(
                            ">> The system is in process of connecting, please wait for connection and then Disconnect",
                            "error")
            else:
                self.show_msg_monitor(">> please disconnect from the SITL , and try again", "msg")
        else:
            if self.drone_is_connect is False:
                if self.sitl_is_connect is False:
                    self.button_connect_sitl.config(text="Sitl \nDisconnect", bg='#5CB300')
                    self.button_connect.config(state=DISABLED, bg='white')
                    self.sitl_is_connect = True
                    self.drone_connect(key, master)
                else:
                    if self.drone_vehicle.drone_connected is True:
                        if self.drone_vehicle.vehicle.armed is False:
                            self.button_connect_sitl.config(text="Sitl \nConnect", bg='#C70002')
                            self.button_connect.config(state=NORMAL, bg='#C70002')
                            self.sitl_is_connect = False
                            self.allow_deny_button('deny')
                            disconnect_thread = threading.Thread(name='disconnect from sitl',
                                                                 target=lambda: self.disconnect(key, master))
                            disconnect_thread.start()
                        else:
                            self.show_msg_monitor(">> Attention! You have to land the drone before Disconnect", "error")
                    else:
                        self.show_msg_monitor(
                            ">> The system is in process of connecting, please wait for connection and then Disconnect",
                            "error")
            else:
                self.show_msg_monitor(">> please disconnect from the drone , and try again", "msg")

    def drone_connect(self, key, master):  # connect to the system
        """the function send to drone_vehicle if connect to the drone or to sitl"""
        if key == 'drone':
            # this apply the mavProxy and after mavProxy succeeded,the mavProxy connecting the drone to the system in drone_control
            connecting_drone_thread = threading.Thread(name='connect_to_drone_thread',target=self.drone_vehicle.mav_proxy_connect)
            connecting_drone_thread.start()
        else:
            #connect to sitl system
            connecting_sitl_thread = threading.Thread(name='connect_to_sitl_thread',target=self.drone_vehicle.connecting_sitl)
            connecting_sitl_thread.start()

        get_info_drone = threading.Thread(name='send info',target=self.get_parm_drone)
        get_info_drone.start()

        #start to camera
        person_detection_video = threading.Thread(name='cam_drone',target=lambda: self.cam_drone(master,key))
        person_detection_video.start()

    def disconnect(self, key, master):
        """disconnect from drone/sitl by button disconnect"""
        if key == 'drone':
            self.drone_vehicle.drone_disconnect()
            self.drone_is_connect = False  # change the bool drone to false,is mean that drone now is not connected

        elif key == 'sitl':
            #self.show_msg_monitor(">> Sitl is disconnected", "msg")
            self.drone_vehicle.sitl_disconnect()
            self.sitl_is_connect = False  # change the bool sitl to false,is mean that sitl now is not connected

        if  self.message_box_pop:
            self.message_box_pop = False  # reset the bool message box.
            self.message_box.destroy()    #if the message box open destroy it.

        self.socket_video.close()
        self.detection_obj.close_detection()
        self.clear_label(master)    #clear all value from labels and frame

    def clear_label(self,master):
        """clear_label call from disconnect function,the function clear all value from frames and labels"""
        self.video_window.destroy()
        self.video_window = Label(master, width=65, height=26, borderwidth=2, relief="groove", bg="gray")
        self.video_window.grid(row=0, column=0, sticky=W + N + E + S, padx=5, pady=5)
        self.altitude_info.config(text="0.00")
        self.bat_volt_info.config(text="0.00")
        self.dist_to_home_info.config(text="0.00")
        self.ground_speed_info.config(text="0.00")
        self.lat_info.config(text = "00.0000000")
        self.lon_info.config(text = "00.0000000")

    def on_closing(self,master):
        """if the user close the swoftwer from X button,this function close all threads and process and close thr gui"""
        if self.drone_vehicle.drone_connected is True:
            if self.drone_vehicle.vehicle.armed is False:
                os.kill(os.getpid(), signal.SIGTERM)
                """
                if self.drone_is_connect is True :
                    self.switch_on_off(master,'drone') #disconnect drone.
                    time.sleep(3)
                    root.destroy()
                elif self.sitl_is_connect is True:
                    close_sitl = Process(target=self.switch_on_off(master,'sitl'))
                    close_sitl.daemon = True
                    close_sitl.start()
                    close_sitl.join()
                    #self.switch_on_off(master,'sitl') #disconnect sitl
                    #time.sleep(3)
                    root.destroy()
                """
            else:
                self.show_msg_monitor(">> You can not exit from rescue drone before the drone land! ", 'error')
        else:
            root.destroy()
            return

    def get_image_function(self):
        """every time that user press on button image capture, this function call to access to cam_drone function get a picture"""
        self.get_image = True

    def cam_drone(self, master,key):
        """the function connect to usp port and gets video frame from person_detection the send to udp port video frame"""
        self.show_msg_monitor(">> Connecting to the camera...", 'msg')
        if key == 'drone':
            self.detection_obj = PersonDetection(self.drone_vehicle,1, self)
        else:
            self.detection_obj = PersonDetection(self.drone_vehicle, 0, self)
        self.socket_video = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_video.settimeout(30)
        host = ''
        port = 8080
        try:
            self.socket_video.bind((host, port)) # connect to port
            self.show_msg_monitor(">> Socket bind complete", "msg")
            self.socket_video.listen(20)
            self.show_msg_monitor(">> Socket now listening", "msg")
            conn, addr = self.socket_video.accept()
            conn.setblocking(1)
        except socket.error, exc:
            self.show_msg_monitor(">> error,problem video connect: %s" % exc,'error')
            if self.drone_is_connect:
                self.switch_on_off(master, 'drone')
            elif self.sitl_is_connect:
                self.switch_on_off(master, 'sitl')
            sys.exit(1)

        data = ""
        payload_size = struct.calcsize("L")
        open_label = False
        self.show_msg_monitor(">> The Camera is connected ", "success")
        while not self.drone_vehicle.drone_connected:
            if self.drone_vehicle.cam_connect is False:
                self.switch_on_off(master, key)
                break
            time.sleep(1)

        while self.drone_vehicle.drone_connected: #start show video frame on the screen

            while len(data) < payload_size:
                data += conn.recv(4096)
            if not data:
                self.socket_video.close()
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("L", packed_msg_size)[0]
            while len(data) < msg_size:
                data += conn.recv(4096)
            frame_data = data[:msg_size]
            data = data[msg_size:]

            if not open_label:
                self.video_window.config(width=460, height=400)
                open_label = True
            last_frame = pickle.loads(frame_data)
            last_frame = cv2.cvtColor(last_frame, cv2.COLOR_BGR2RGB)
            if self.get_image:
                self.repo.set_image(last_frame)
                self.get_image =False

            try:
                img = Image.fromarray(last_frame)
                imgtk = ImageTk.PhotoImage(image=img)

            except:
                continue
            self.video_window.configure(image=imgtk)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                cv2.destroyAllWindows()
                break

    def show_msg_monitor(self, msg, tag):
        """this function get a text msg and tag->like msg/error/success and show on monitor msg frame"""
        self.monitor_msg.config(state='normal')
        self.monitor_msg.insert(END, msg + "\n", tag)
        self.monitor_msg.see(END)
        self.monitor_msg.config(state='disabled')

    def show_msg_user(self,key):
        """the function get a key and create template of important message to user with sound and button to how to continue"""
        if not self.message_box_pop:
            self.message_box_pop = True

            if key == "person detection":   #msg if person detection
                text_message = "A person has been detected !\n do you want send GPS location and RTL?\n or continue search ? "
                yes_button = "send GPS and RTL"
                no_button = "continue to search"
                middle_button ="send GPS and stay"
                msg_detail = {'message': text_message, 'key': key, 'yes_b':yes_button, 'mid_b':middle_button, 'no_b':no_button}
                self.create_message_box(msg_detail)
                """
                self.sound_bool = BooleanVar()
                button_sound_on_oof = Checkbutton(self.message_box, text="sound on/off", variable=self.sound_bool,bg='#E5C100')
                button_sound_on_oof.grid(row=1, column=0)
                start_alarm = threading.Thread(name="start_the_alarm_person_detect", target=lambda :self.start_alarm(self.sound_bool))
                start_alarm.start()
                """
            if key == "low voltage":    #msg if the battery voltage is low.
                if  self.low_battery is True:
                    text_message = "LOW BATTERY !\n low battery voltage, return home.\n  "
                    yes_button = "return home"
                    no_button = "continue to search"
                    msg_detail = {'message': text_message, 'key': key, 'yes_b': yes_button,'no_b': no_button}
                    self.create_message_box(msg_detail)
                    """
                    sound_bool = BooleanVar()
                    button_sound_on_oof = Checkbutton(self.message_box, text="sound on/off", variable=sound_bool,bg='#E5C100')
                    button_sound_on_oof.grid(row=1, column=0)
                    start_alarm = threading.Thread(name="start_the_alarm_low_batt",target=lambda: self.start_alarm(sound_bool))
                    start_alarm.start()
                    """
            sound_bool = BooleanVar()
            button_sound_on_oof = Checkbutton(self.message_box, text="sound on/off", variable=sound_bool,bg='#E5C100')
            button_sound_on_oof.grid(row=1, column=0)
            start_alarm = threading.Thread(name="start_the_alarm_person_detect",target=lambda: self.start_alarm(sound_bool))
            start_alarm.start()



    def create_message_box(self,msg_detail):
        """the functionf get a msg template from show_msg_user and show the msg"""
        self.message_box = LabelFrame(self.drone_control, fg='red', text="!! Message !!", font=("Courier", 15),
                                      labelanchor=N,bg='#E5C100')
        for x in xrange(5):
            self.message_box.grid_columnconfigure(x, weight=1)
        for y in xrange(2):
            self.message_box.grid_rowconfigure(y, weight=1)
        self.message_box.grid(row=2, column=0, columnspan=4, rowspan=5, sticky=W + N + E + S)

        message = Label(self.message_box, text=msg_detail['message'],font=10,bg='#E5C100')
        message.grid(row=0, columnspan=5)

        button_yes = Button(self.message_box, text=msg_detail['yes_b'], width=15, height=2,bg='#5CB300',
                           command=lambda: self.user_reply_message('yes',msg_detail['key']))
        button_yes.grid(row=1, column=1)

        button_no = Button(self.message_box, text=msg_detail['no_b'], width=15, height=2,bg='#5CB300',
                           command=lambda: self.user_reply_message('no',msg_detail['key']))
        button_no.grid(row=1, column=3)

        if msg_detail['key'] == 'person detection':
            send_gps = Button(self.message_box, text=msg_detail['mid_b'], width=15, height=2,bg='#5CB300',
                               command=lambda: self.user_reply_message('mid', msg_detail['key']))
            send_gps.grid(row=1, column=2)

    def user_reply_message(self, answer,key):
        """the function get answer from the user what he wants to do after receiving the message in create_message_box"""
        if key == 'person detection':
            if answer == 'yes': #send gps and rtl
                self.repo.set_person_loc(self.drone_vehicle.get_person_location(),"send gps and rtl,time:"+time.strftime("%H:%M:%S"))
                self.person_location_todb(self.drone_vehicle.get_person_location())
                rtl = threading.Thread(name='drone connect', target=self.drone_vehicle.rtl_mode)
                rtl.start()

            elif answer == 'no': #return to search
                self.repo.set_person_loc(self.drone_vehicle.get_person_location(), "return to search,time:"+time.strftime("%H:%M:%S"))
                self.show_msg_monitor(">> Return to search", "msg")
                self.send_auto_mode()

            else:   #send gps and stay in position
                self.repo.set_person_loc(self.drone_vehicle.get_person_location(),"send gps and stay,time:" + time.strftime("%H:%M:%S"))
                self.person_location_todb(self.drone_vehicle.get_person_location())
                send_gps_stay_thread = threading.Thread(name="send_gps_stay_thread",target=self.drone_vehicle.send_gps_and_stay)  # check when possible again alarm operation
                send_gps_stay_thread.start()

            check_alarm_operation_again = threading.Thread(name="check_alarm_operation",target=self.drone_vehicle.check_alarm_operation)  # check when possible again alarm operation
            check_alarm_operation_again.start()

        if key == 'low voltage':
            if answer == 'yes':
                rtl = threading.Thread(name='drone connect', target=self.drone_vehicle.rtl_mode)
                rtl.start()
            else:
                low_batt_timer = threading.Thread(name="check_low_battery",target=self.timer_low_battery)
                low_batt_timer.start()

        self.message_box.destroy()
        self.message_box_pop = False

    def timer_low_battery(self):
        """if the user press the continue when msg battery show the timer start to 15 sec and alarm again msg."""
        t = 0
        while t < 15:
            t += 1
            time.sleep(1)
        self.low_battery = False

    def person_location_todb(self,location):
        self.setting.get_db().patch('location' + str(self.__count_person), {'longitude': location.lon, 'latitude': location.lat})
        self.__count_person +=1

    def get_parm_drone(self):
        """the function listen to drone all time when the drone connect,and show parameters"""
        while not self.drone_vehicle.drone_connected:
            time.sleep(1)
            if self.drone_vehicle.cam_connect is False:
                break

        if self.drone_vehicle.drone_connected:
            self.allow_deny_button('allow')
        start = None
        second = 0
        minu = 0
        hour = 0
        max_alt = 0
        max_speed = 0

        self.repo.set_drone_connect_time(time.strftime("%H:%M:%S"))

        while self.drone_vehicle.drone_connected:
            min_bat = self.min_battery_voltage()
            if self.drone_vehicle.vehicle.armed:
                if start is None:
                    start = time.time()
                    self.repo.set_start_mission(time.strftime("%H:%M:%S"))

            if self.drone_vehicle.vehicle.armed and start is not None:
                second = int((time.time() - start))
                if second == 60:
                    minu += 1
                    start = time.time()
                if minu == 60:
                    hour += 1
                    minu = 0
            ck = format(hour, '02') + ":" + format(minu, '02') + ":" + format(second, '02')
            if self.drone_vehicle.vehicle.armed is False and start is not None:      #the drone finish mission,write to report start and end time mission and air time
                start = None
                end_mission =  time.strftime("%H:%M:%S")
                self.repo.set_end_mission(end_mission)
                self.repo.set_max_alt(max_alt)
                self.repo.set_top_speed(max_speed)
                self.repo.set_air_time(ck)
                self.repo.create_report_mission() ## when the drone landed create report file.


            parm = self.drone_vehicle.get_info_drone()

            if self.drone_vehicle.vehicle.armed:
                if min_bat >= float(parm['bat']) and self.low_battery is False:
                    self.low_battery = True
                    self.show_msg_user("low voltage")

            if parm['alt'] > max_alt:
                max_alt = parm['alt']

            if parm['ground_speed'] > max_speed:
                max_speed = parm['ground_speed']
            try:
                self.altitude_info.config(text="%.2f" % parm['alt'])
                self.bat_volt_info.config(text="%.2f" % parm['bat'])
                self.dist_to_home_info.config(text="%.2f" % parm['dist_home'])
                self.ground_speed_info.config(text="%.2f" % parm['ground_speed'])
                self.time_air_info.config(text=ck)
                self.lon_info.config(text ="%.7f" % parm['lon'])
                self.lat_info.config(text="%.7f" % parm['lat'])
            except:
                continue

    def min_battery_voltage(self):
        """clculate the minimum voltage on the battery"""
        min_volt = float(self.setting.get_num_of_cell() * self.setting.get_min_v_per_cell())
        return min_volt

    def start_alarm (self,sound_bool):
        """the function call from show_msg_user and only on/off alarm when person detect"""
        while self.message_box_pop:
            try:
                if sound_bool.get() is False:
                    PlaySound('media\Alarm.wav', SND_FILENAME)
                    time.sleep(2)
                else:
                    continue
            except:
                continue

    def key(self,event):
        """the function get event key from keyboard and send command to drone accordingly the key"""
        gnd_speed = self.setting.get_manu_speed()  # [m/s] ->meter/second
        if self.keyboard_control_bool.get() is True and self.drone_vehicle.drone_connected is True:
            if self.drone_vehicle.vehicle.armed is True and self.drone_vehicle.vehicle.mode.name is 'GUIDED':
                if event.char == event.keysym:  # -- standard keys
                    if event.keysym == 's':     #dwon
                        self.move_dwon.config(relief=SUNKEN)
                        self.drone_vehicle.set_velocity_body(0, 0, gnd_speed,0)
                        self.move_dwon.after(100, lambda: self.move_dwon.config(relief=RAISED))
                    elif event.keysym == 'w' :   #up
                        self.move_up.config(relief=SUNKEN)
                        self.drone_vehicle.set_velocity_body(0, 0, -gnd_speed,0)
                        self.move_up.after(100, lambda: self.move_up.config(relief=RAISED))
                    elif event.keysym == 'd':   #yaw right
                        self.spin_right.config(relief=SUNKEN)
                        self.drone_vehicle.set_velocity_body(0, 0, 0,1,'yaw')
                        self.spin_right.after(100, lambda: self.spin_right.config(relief=RAISED))
                    elif event.keysym == 'a':   #yaw left
                        self.spin_left.config(relief=SUNKEN)
                        self.drone_vehicle.set_velocity_body(0, 0, 0, -1,'yaw')
                        self.spin_left.after(100, lambda: self.spin_left.config(relief=RAISED))
                    elif event.keysym == 'u':
                        self.button_auto.config(relief = SUNKEN)
                        self.send_auto_mode()
                        self.button_auto.after(100, lambda: self.button_auto.config(relief=RAISED))



                else:  # -- non standard keys
                    if event.keysym == 'Up':    #forward
                        self.move_forward.config(relief=SUNKEN)
                        self.drone_vehicle.set_velocity_body( gnd_speed, 0, 0,0)
                        self.move_forward.after(100, lambda: self.move_forward.config(relief=RAISED))
                    elif event.keysym == 'Down':    #backwards
                        self.move_back.config(relief=SUNKEN)
                        self.drone_vehicle.set_velocity_body(-gnd_speed, 0, 0,0)
                        self.move_back.after(100, lambda: self.move_back.config(relief=RAISED))
                    elif event.keysym == 'Left':    #left
                        self.move_left.config(relief=SUNKEN)
                        self.drone_vehicle.set_velocity_body(0, -gnd_speed, 0,0)
                        self.move_left.after(100, lambda: self.move_left.config(relief=RAISED))
                    elif event.keysym == 'Right':   #right
                        self.move_right.config(relief=SUNKEN)
                        self.drone_vehicle.set_velocity_body(0, gnd_speed, 0,0)
                        self.move_right.after(100, lambda: self.move_right.config(relief=RAISED))

    def aplly_key(self,event):
        """apply keyboard control"""
        if self.drone_vehicle.drone_connected is True:
            key_button = threading.Thread(name="key_button", target=lambda :self.key(event))  # check when possible again alarm operation
            key_button.start()
        else:
            self.show_msg_monitor(">> Only in manual mode", "msg")
    def clean_missions(self):
        """clean mission from the drone"""
        self.drone_vehicle.clean_missions()
###############################################################################################################################
##################################################### main ####################################################################

if __name__ == "__main__":

    root = Tk()
    gui = Gui(root)
    root.bind_all('<Key>',gui.aplly_key)
    root.mainloop()
    sys.exit()