# -*- coding: utf-8 -*-
"""
Socket Client - Kết nối đến server và gửi dữ liệu
Improvements:
- Added comprehensive logging
- Reconnection logic with retry attempts
- Better error handling
- Thread-safe operations
- Graceful shutdown
"""
import gc
import atexit
import pickle
import platform
import getpass
import socket
import struct
import threading
import time
import uuid
import mss
import cv2
import numpy as np
import os
# from PIL import Image
# import io
from utils.logger import LoggerSetup

logger = LoggerSetup.get_logger(__name__)

# Client constants
DEFAULT_BUFFER_SIZE = 4096
FILE_HEADER_SIZE = 256
SOCKET_TIMEOUT = 30
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 5
HEARTBEAT_INTERVAL = 5
SCREEN_CAPTURE_INTERVAL = 0.2


class SocketClient:
    """
    Client for connecting to Computer Room Management Server
    Handles screen capture, file transfer, and command execution
    """

    def __init__(self, host, port=5000):
        """
        Initialize socket client
        
        Args:
            host (str): Server IP address
            port (int): Server port
        """
        self.host = host
        self.port = port
        self.is_running = True
        self.reconnect_attempts = 0


        
        # self.client_socket = socket.socket(
        #     socket.AF_INET,
        #     socket.SOCK_STREAM
        # )

        # self.screen_socket = socket.socket(
        #     socket.AF_INET,
        #     socket.SOCK_STREAM
        # )

        # self.file_socket = socket.socket(
        #     socket.AF_INET,
        #     socket.SOCK_STREAM
        # )

        self.client_id = str(uuid.uuid4())
        self.session_active = False

        logger.info(f"SocketClient initialized - Client ID: {self.client_id}")
        logger.info(f"Target server: {host}:{port}")
        
        atexit.register(self.cleanup)
    
    def start_forever(self):
        """Vòng lặp chính luôn cố gắng kết nối lại với server"""
        while True:
            try:
                if self.connect():
                    self.session_active = True
                    self.send_computer_info()
                    self.start_heartbeat()
                    self.start_screen_stream()
                    self.start_receive_loop()

                    logger.info("Đã kết nối hoàn tất, đang giữ luồng hoạt động...")
                    # Giữ luồng chính sống chừng nào phiên còn đang active
                    while self.session_active:
                        time.sleep(1)
                
                # Nếu kết nối thất bại hoặc bị ngắt, đợi 5s rồi thử lại
                logger.info("Đợi 5 giây trước khi thử kết nối lại...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Lỗi ở vòng lặp chính: {e}")
                time.sleep(5)


    def connect(self):
        """Khởi tạo lại socket và kết nối"""
        try:
            # BẮT BUỘC KHỞI TẠO LẠI SOCKET Ở ĐÂY
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.screen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.file_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            logger.info(f"Đang kết nối tới {self.host}:{self.port}...")
            
            self.client_socket.connect((self.host, self.port))
            self.client_socket.settimeout(SOCKET_TIMEOUT)

            self.screen_socket.connect((self.host, 5001))
            self.screen_socket.settimeout(SOCKET_TIMEOUT)

            self.file_socket.connect((self.host, 5002))
            self.file_socket.settimeout(SOCKET_TIMEOUT)

            # Đăng ký với file server
            message = f"FILE_CONNECT|{self.client_id}"
            self.file_socket.send(message.encode())

            # Start file receiver thread
            threading.Thread(
                target=self.receive_files,
                daemon=True,
                name="FileReceiver"
            ).start()

            self.create_virtual_drive()
            return True

        except Exception as e:
            logger.error(f"Kết nối thất bại: {e}")
            self._close_sockets()
            return False
        

    def send_computer_info(self):
        """Send computer information to server"""
        try:
            computer_name = socket.gethostname()
            username = getpass.getuser()
            os_name = platform.system()
            
            message = (
                f"INFO|{self.client_id}|"
                f"{computer_name}|{username}|{os_name}"
            )
            
            self.client_socket.send(message.encode())
            logger.info(
                f"Computer info sent - Name: {computer_name}, "
                f"User: {username}, OS: {os_name}"
            )

        except Exception as e:
            logger.error(f"Failed to send computer info: {e}", exc_info=True)

    def start_heartbeat(self):
        """Start heartbeat thread"""
        threading.Thread(
            target=self.heartbeat_loop,
            daemon=True,
            name="Heartbeat"
        ).start()
        logger.info("Heartbeat thread started")

    def start_receive_loop(self):
        """Start command receive thread"""
        threading.Thread(
            target=self.receive_loop,
            daemon=True,
            name="CommandReceiver"
        ).start()
        logger.info("Command receive loop started")

    def receive_loop(self):
        """
        Receive and handle commands from server
        """
        while self.session_active:
            try:
                data = self.client_socket.recv(DEFAULT_BUFFER_SIZE).decode()

                if not data:
                    logger.warning("Server closed connection")
                    self.session_active = False
                    break

                logger.debug(f"Server command received: {data}")
                self.handle_command(data)

            except socket.timeout:
                logger.debug("Receive loop timeout")
                continue
            except Exception as e:
                logger.error(f"Receive loop error: {e}", exc_info=True)
                self.session_active = False
                break

    def handle_command(self, data):
        """
        Handle command from server
        
        Args:
            data (str): Command string
        """
        try:
            command = data.split("|")[0]

            if command == "DISCONNECT":
                logger.info("Disconnect command received from server")
                self.disconnect()

            elif command == "GET_FILES":
                logger.info("File request command received")
                self.send_virtual_drive_files()

            else:
                logger.warning(f"Unknown command: {command}")

        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)

    def heartbeat_loop(self):
        """
        Send heartbeat/ping to server periodically
        """
        while self.session_active:
            try:
                message = f"PING|{self.client_id}"
                self.client_socket.send(message.encode())
                logger.debug("Heartbeat sent to server")

                time.sleep(HEARTBEAT_INTERVAL)

            except socket.error as e:
                logger.error(f"Heartbeat socket error: {e}")
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                break

    def capture_screen(self):
        """
        Capture current screen
        Returns:
            bytes: Pickled frame data
        """
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # --- THÊM 3 DÒNG NÀY ĐỂ THU NHỎ ẢNH (TỐI ƯU CHO 20 MÁY) ---
                width = 1024
                height = int(img.shape[0] * (width / img.shape[1]))
                img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
                # ---------------------------------------------------------
                
                _, buffer = cv2.imencode(
                    ".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 50]
                )
                return pickle.dumps(buffer)
        except Exception as e:
            logger.error(f"Screen capture error: {e}")
            return None

    def start_screen_stream(self):
        """Start screen streaming thread"""
        threading.Thread(
            target=self.screen_stream_loop,
            daemon=True,
            name="ScreenStreamer"
        ).start()
        logger.info("Screen streaming thread started")

    def screen_stream_loop(self):
        """Stream screen frames to server với cơ chế tối ưu RAM tối đa"""
        logger.info("Screen stream loop started")
        
        # KHỞI TẠO MSS DUY NHẤT 1 LẦN TẠI ĐÂY (Tránh rò rỉ RAM và giảm 80% CPU)
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            frame_count = 0  # Biến đếm số khung hình
            
            while self.is_running:
                try:
                    if not self.session_active:
                        time.sleep(1)
                        continue

                    # Truyền thẳng sct và monitor vào hàm để dùng lại bộ nhớ cũ
                    frame_data = self.capture_screen_optimized(sct, monitor)
                    
                    if frame_data:
                        # Gửi dữ liệu qua socket
                        self.screen_socket.sendall(
                            struct.pack("Q", len(frame_data)) + frame_data
                        )
                        # XÓA NGAY LẬP TỨC biến frame_data sau khi gửi xong
                        del frame_data 

                    frame_count += 1
                    
                    # CỨ MỖI 50 FRAMES (~10 giây), ÉP PYTHON KHỞI ĐỘNG TRÌNH DỌN RAM
                    if frame_count % 50 == 0:
                        gc.collect()  # Thu hồi toàn bộ ô nhớ treo của OpenCV/Numpy
                        frame_count = 0

                    time.sleep(SCREEN_CAPTURE_INTERVAL)

                except Exception as e:
                    logger.error(f"Screen stream loop error: {e}")
                    self.session_active = False
                    break

    def capture_screen_optimized(self, sct, monitor):
        """
        Chụp và xử lý màn hình tối ưu hóa bộ nhớ đệm
        """
        try:
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            width = 1024
            height = int(img.shape[0] * (width / img.shape[1]))
            small_img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
            
            _, buffer = cv2.imencode(
                ".jpg", small_img, [int(cv2.IMWRITE_JPEG_QUALITY), 50]
            )
            
            # SỬA Ở ĐÂY: Gói (dump) 2 lần để khớp với đầu đọc của Server
            frame_bytes = pickle.dumps(buffer)
            data = pickle.dumps((self.client_id, frame_bytes))
            
            del screenshot
            del img
            del small_img
            del buffer
            
            return data
            
        except Exception as e:
            logger.error(f"Screen capture error: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Screen capture error: {e}")
            return None

    def receive_files(self):
        """
        Receive files from server
        """
        while self.session_active:
            try:
                header = (
                    self.file_socket.recv(FILE_HEADER_SIZE)
                    .decode()
                    .strip()
                )

                if not header:
                    continue

                parts = header.split("|")

                if parts[0] != "FILE" or len(parts) < 3:
                    continue

                filename = parts[1]
                filesize = int(parts[2])

                self._save_received_file(filename, filesize)

            except socket.timeout:
                logger.debug("File receive timeout")
                continue
            except ValueError as e:
                logger.error(f"Invalid file header format: {e}")
                continue
            except Exception as e:
                logger.error(f"Receive file error: {e}", exc_info=True)
                break

    def _save_received_file(self, filename, filesize):
        """
        Save received file to Downloads folder
        
        Args:
            filename (str): Name of file
            filesize (int): Size of file in bytes
        """
        try:
            downloads = os.path.join(
                os.path.expanduser("~"),
                "Downloads"
            )

            os.makedirs(downloads, exist_ok=True)
            save_path = os.path.join(downloads, filename)

            received = 0
            start_time = time.time()

            with open(save_path, "wb") as f:
                while received < filesize:
                    to_receive = min(
                        DEFAULT_BUFFER_SIZE,
                        filesize - received
                    )

                    data = self.file_socket.recv(to_receive)

                    if not data:
                        logger.warning(f"Incomplete file transfer: {filename}")
                        break

                    f.write(data)
                    received += len(data)

            elapsed = time.time() - start_time
            speed = (filesize / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            
            logger.info(
                f"File received: {filename} ({filesize/1024:.2f}KB) "
                f"in {elapsed:.2f}s ({speed:.2f}MB/s) to {downloads}"
            )

        except Exception as e:
            logger.error(f"Failed to save received file {filename}: {e}", exc_info=True)

    def send_virtual_drive_files(self):
        """
        Send files from virtual drive to server
        Windows only - requires T: drive
        """
        folder = r"T:\\"

        if not os.path.exists(folder):
            logger.warning("Virtual drive T: not found")
            return

        files = os.listdir(folder)

        if not files:
            logger.info("No files in virtual drive T:")
            return

        logger.info(f"Sending {len(files)} file(s) from virtual drive")

        for filename in files:
            file_path = os.path.join(folder, filename)

            if not os.path.isfile(file_path):
                continue

            try:
                filesize = os.path.getsize(file_path)

                header = (
                    f"FILES_FROM_CLIENT|{filename}|{filesize}"
                )

                self.file_socket.sendall(
                    header.encode().ljust(FILE_HEADER_SIZE)
                )

                with open(file_path, "rb") as f:
                    while True:
                        data = f.read(DEFAULT_BUFFER_SIZE)

                        if not data:
                            break

                        self.file_socket.sendall(data)

                logger.info(f"File sent to server: {filename} ({filesize/1024:.2f}KB)")

            except Exception as e:
                logger.error(f"Error sending file {filename}: {e}", exc_info=True)

    def create_virtual_drive(self):
        """
        Create virtual T: drive for file sharing
        Windows only
        """
        try:
            folder = r"C:\TempShare"

            os.makedirs(folder, exist_ok=True)

            result = os.system(f'subst T: "{folder}"')

            if result == 0:
                logger.info(f"Virtual drive created: T: -> {folder}")
            else:
                logger.warning("Failed to create virtual drive (may require admin)")

        except Exception as e:
            logger.error(f"Error creating virtual drive: {e}", exc_info=True)

    def remove_virtual_drive(self):
        """Remove virtual T: drive"""
        try:
            result = os.system("subst T: /d")
            
            if result == 0:
                logger.info("Virtual drive T: removed")
            else:
                logger.warning("Failed to remove virtual drive")

        except Exception as e:
            logger.error(f"Error removing virtual drive: {e}")

    def disconnect(self):
        """Ngắt kết nối hiện tại (sẽ tự động kích hoạt vòng lặp reconnect ở start_forever)"""
        logger.info("Client disconnect initiated")
        self.session_active = False # Đổi cờ để ngưng các luồng
        self._close_sockets()
        
        try:
            self.remove_virtual_drive()
        except:
            pass

    def _close_sockets(self):
        """Hàm phụ trợ để đóng rạch sẽ sockets"""
        try: self.client_socket.close() 
        except: pass
        try: self.screen_socket.close() 
        except: pass
        try: self.file_socket.close() 
        except: pass

    def cleanup(self):
        """Cleanup on exit"""
        logger.info("Cleanup on exit")
        try:
            self.remove_virtual_drive()
        except:
            pass