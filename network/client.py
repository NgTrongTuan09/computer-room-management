import atexit
from email import message
import pickle
import platform
import getpass
import socket
import struct
import threading
import time
import uuid
import mss
import io
import cv2
import numpy as np
from PIL import Image
import os


class SocketClient:

    def __init__(self, host, port=5000):
        self.host = host
        self.port = port
        self.is_running = True

        self.server_ip = host

        self.client_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.screen_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.file_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.client_id = str(uuid.uuid4())
        atexit.register(self.cleanup)

    def connect(self):
        # packet socket
        self.client_socket.connect(
            (self.host, self.port)
        )

        # screen socket
        self.screen_socket.connect(
            (self.host, 5001)
        )

        # file socket
        self.file_socket.connect(
            (self.host, 5002)
        )

        message = (
            f"FILE_CONNECT|{self.client_id}"
        )

        self.file_socket.send(
            message.encode()
        )

        threading.Thread(
            target=self.receive_files,
            daemon=True
        ).start()


        

        print("Connected to server")
        self.create_virtual_drive()

    def send_computer_info(self):
        computer_name = socket.gethostname()
        username = getpass.getuser()
        os_name = platform.system()
        message = (
                f"INFO|"
                f"{self.client_id}|"
                f"{computer_name}|"
                f"{username}|"
                f"{os_name}"
            )
        self.client_socket.send(message.encode())

    def start_heartbeat(self):
        threading.Thread(
            target=self.heartbeat_loop,
            daemon=True
        ).start()


    def start_receive_loop(self):
        threading.Thread(
            target=self.receive_loop,
            daemon=True
        ).start()


    def receive_loop(self):
        while self.is_running:

            try:

                data = self.client_socket.recv(1024).decode()

                if not data:
                    break

                print("Server command:", data)

                self.handle_command(data)

            except Exception as e:

                print("Receive error:", e)

                break

    
    def handle_command(self, data):
        command = data.split("|")[0]

        # ================= DISCONNECT =================
        if command == "DISCONNECT":
            print("Disconnected by server")
            self.disconnect()

        # ================= GET FILES =================
        elif command == "GET_FILES":
            print("Server requested files")
            self.send_virtual_drive_files()      


    def heartbeat_loop(self):
        while self.is_running:

            try:

                self.client_socket.send(
                    f"PING|{self.client_id}".encode()
                )

                time.sleep(5)

            except Exception as e:

                print("Heartbeat error:", e)

                break

    # ================== SCREENSHOT ==================ư
    def capture_screen(self):
        with mss.mss() as sct:

            monitor = sct.monitors[1]

            screenshot = sct.grab(monitor)

            img = np.array(screenshot)

            img = cv2.cvtColor(
                img,
                cv2.COLOR_BGRA2BGR
            )

            _, buffer = cv2.imencode(
                ".jpg",
                img,
                [int(cv2.IMWRITE_JPEG_QUALITY), 50]
            )

            return pickle.dumps(buffer)
        
    def start_screen_stream(self):
        threading.Thread(
            target=self.screen_stream_loop,
            daemon=True
        ).start()

    def screen_stream_loop(self):
        while self.is_running:

            try:

                frame = self.capture_screen()

                data = pickle.dumps(
                    (self.client_id, frame)
                )

                message = struct.pack(
                    "Q",
                    len(data)
                ) + data

                self.screen_socket.sendall(message)

            except Exception as e:

                print("Screen stream error:", e)

                break

            time.sleep(0.2)

    def receive_files(self):
        while self.is_running:

            try:

                header = (
                    self.file_socket.recv(256)
                    .decode()
                    .strip()
                )

                if not header:
                    continue

                parts = header.split("|")

                if parts[0] != "FILE":
                    continue

                filename = parts[1]

                filesize = int(parts[2])

                downloads = os.path.join(
                    os.path.expanduser("~"),
                    "Downloads"
                )

                save_path = os.path.join(
                    downloads,
                    filename
                )

                received = 0

                with open(save_path, "wb") as f:

                    while received < filesize:

                        data = self.file_socket.recv(
                            min(
                                4096,
                                filesize - received
                            )
                        )

                        if not data:
                            break

                        f.write(data)

                        received += len(data)

                print(
                    f"Received file: {filename}"
                )

            except Exception as e:

                print("Receive file error:", e)

                break

    
    def send_virtual_drive_files(self):
        folder = r"T:\\"

        if not os.path.exists(folder):

            print("T drive not found")

            return

        files = os.listdir(folder)

        if not files:

            print("No files in T drive")

            return

        for filename in files:

            file_path = os.path.join(
                folder,
                filename
            )

            if not os.path.isfile(file_path):
                continue

            try:

                filesize = os.path.getsize(
                    file_path
                )

                header = (
                    f"FILES_FROM_CLIENT|"
                    f"{filename}|"
                    f"{filesize}"
                )

                self.file_socket.sendall(
                    header.encode().ljust(256)
                )

                with open(file_path, "rb") as f:

                    while True:

                        data = f.read(4096)

                        if not data:
                            break

                        self.file_socket.sendall(data)

                print(
                    f"Sent file to server: {filename}"
                )

            except Exception as e:

                print(
                    "Send virtual file error:",
                    e
                )

    def create_virtual_drive(self):
        folder = r"C:\TempShare"

        os.makedirs(folder, exist_ok=True)

        os.system(
            f'subst T: "{folder}"'
        )

        print("Virtual drive T: created")

    def remove_virtual_drive(self):
        os.system("subst T: /d")

        print("Virtual drive T: removed")



    # disconnect and cleanup

    def disconnect(self):
        self.is_running = False

        self.remove_virtual_drive()

        self.client_socket.close()
        self.screen_socket.close()
        self.file_socket.close()




    def cleanup(self):
        try:

            self.remove_virtual_drive()

        except:
            pass