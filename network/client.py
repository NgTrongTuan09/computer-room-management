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
        
        logger.info(f"SocketClient initialized - Client ID: {self.client_id}")
        logger.info(f"Target server: {host}:{port}")
        
        atexit.register(self.cleanup)

    def connect(self):
        """
        Connect to server with retry logic
        
        Returns:
            bool: True if connected successfully
        """
        for attempt in range(RECONNECT_ATTEMPTS):
            try:
                logger.info(
                    f"Connection attempt {attempt + 1}/{RECONNECT_ATTEMPTS} "
                    f"to {self.host}:{self.port}"
                )
                
                # Connect main socket
                self.client_socket.connect((self.host, self.port))
                self.client_socket.settimeout(SOCKET_TIMEOUT)
                logger.info("Main socket connected")

                # Connect screen socket
                self.screen_socket.connect((self.host, 5001))
                self.screen_socket.settimeout(SOCKET_TIMEOUT)
                logger.info("Screen socket connected")

                # Connect file socket
                self.file_socket.connect((self.host, 5002))
                self.file_socket.settimeout(SOCKET_TIMEOUT)
                logger.info("File socket connected")

                # Register with file server
                message = f"FILE_CONNECT|{self.client_id}"
                self.file_socket.send(message.encode())
                logger.info("File connection registered")

                # Start receive threads
                threading.Thread(
                    target=self.receive_files,
                    daemon=True,
                    name="FileReceiver"
                ).start()

                # Create virtual drive (Windows only)
                self.create_virtual_drive()

                logger.info("Client connected successfully to server")
                self.reconnect_attempts = 0
                return True

            except socket.error as e:
                logger.error(f"Connection failed (attempt {attempt + 1}): {e}")
                
                if attempt < RECONNECT_ATTEMPTS - 1:
                    logger.info(f"Retrying in {RECONNECT_DELAY} seconds...")
                    time.sleep(RECONNECT_DELAY)
                else:
                    logger.error("Failed to connect after all attempts")
                    return False

            except Exception as e:
                logger.error(f"Unexpected error during connection: {e}", exc_info=True)
                return False

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
        while self.is_running:
            try:
                data = self.client_socket.recv(DEFAULT_BUFFER_SIZE).decode()

                if not data:
                    logger.warning("Server closed connection")
                    break

                logger.debug(f"Server command received: {data}")
                self.handle_command(data)

            except socket.timeout:
                logger.debug("Receive loop timeout")
                continue
            except Exception as e:
                logger.error(f"Receive loop error: {e}", exc_info=True)
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
        while self.is_running:
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

                _, buffer = cv2.imencode(
                    ".jpg",
                    img,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 50]
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
        """
        Continuously capture and send screen to server
        """
        consecutive_errors = 0
        max_errors = 5

        while self.is_running:
            try:
                frame = self.capture_screen()

                if not frame:
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        logger.error("Too many screen capture errors, stopping stream")
                        break
                    time.sleep(SCREEN_CAPTURE_INTERVAL)
                    continue

                data = pickle.dumps((self.client_id, frame))
                message = struct.pack("Q", len(data)) + data

                self.screen_socket.sendall(message)
                consecutive_errors = 0

                time.sleep(SCREEN_CAPTURE_INTERVAL)

            except socket.error as e:
                logger.error(f"Screen stream socket error: {e}")
                consecutive_errors += 1
                break
            except Exception as e:
                logger.error(f"Screen stream error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    break
                time.sleep(SCREEN_CAPTURE_INTERVAL)

    def receive_files(self):
        """
        Receive files from server
        """
        while self.is_running:
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
        """
        Disconnect from server and cleanup
        """
        logger.info("Client disconnect initiated")
        self.is_running = False

        try:
            self.remove_virtual_drive()
        except:
            pass

        try:
            self.client_socket.close()
            self.screen_socket.close()
            self.file_socket.close()
            logger.info("All sockets closed")
        except:
            pass

    def cleanup(self):
        """Cleanup on exit"""
        logger.info("Cleanup on exit")
        try:
            self.remove_virtual_drive()
        except:
            pass
