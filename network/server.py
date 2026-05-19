# -*- coding: utf-8 -*-
"""
Socket Server - Quản lý kết nối với các client
Improvements:
- Added comprehensive logging
- Better error handling and socket reconnection
- Progress tracking for file transfers
- Thread-safe operations
- Timeout handling
"""

import pickle
import socket
import threading
import struct
import time
import cv2
import os
from utils.logger import LoggerSetup

logger = LoggerSetup.get_logger(__name__)

# Server constants
DEFAULT_BUFFER_SIZE = 4096
FILE_HEADER_SIZE = 256
SOCKET_TIMEOUT = 30
RECONNECT_ATTEMPTS = 3


class SocketServer:
    """
    Multi-threaded socket server for client communication
    Handles main commands, screen streaming, and file transfer
    """

    def __init__(
            self,
            host="0.0.0.0",
            port=5000,
            on_packet_received=None,
            on_client_disconnected=None,
            on_screen_frame=None,
            on_file_progress=None
        ):

        self.host = host
        self.port = port

        self.on_packet_received = on_packet_received
        self.on_client_disconnected = on_client_disconnected
        self.on_screen_frame = on_screen_frame
        self.on_file_progress = on_file_progress

        # Main server socket
        self.server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )
        self.server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        # Screen server socket
        self.screen_server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )
        self.screen_server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        # File server socket
        self.file_server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )
        self.file_server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self.is_running = True
        self.clients = {}  # client_id -> socket mapping
        self.file_clients = {}  # client_id -> file socket mapping
        self.lock = threading.Lock()  # Thread-safe access to dicts

        logger.info(f"SocketServer initialized - {host}:{port}")

    def start(self):
        """Start all server threads"""
        self.is_running = True
        
        try:
            # Bind main server
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(100)
            logger.info(f"Main server listening on {self.host}:{self.port}")

            # Bind screen server
            self.screen_server_socket.bind((self.host, 5001))
            self.screen_server_socket.listen(100)
            logger.info(f"Screen server listening on {self.host}:5001")

            # Bind file server
            self.file_server_socket.bind((self.host, 5002))
            self.file_server_socket.listen(100)
            logger.info(f"File server listening on {self.host}:5002")

            # Start accepting threads
            threading.Thread(
                target=self.accept_clients,
                daemon=True,
                name="AcceptClients"
            ).start()

            threading.Thread(
                target=self.accept_screen_clients,
                daemon=True,
                name="AcceptScreenClients"
            ).start()

            threading.Thread(
                target=self.accept_file_clients,
                daemon=True,
                name="AcceptFileClients"
            ).start()

            logger.info("All server threads started successfully")

        except Exception as e:
            logger.error(f"Failed to start server: {e}", exc_info=True)
            raise

    def register_client(self, client_id, client_socket):
        """
        Register a client with thread-safe operation
        
        Args:
            client_id (str): Unique client identifier
            client_socket: Socket connection to client
        """
        with self.lock:
            self.clients[client_id] = client_socket
        logger.info(f"Client registered: {client_id}")

    def remove_client(self, client_id):
        """
        Remove a client safely
        
        Args:
            client_id (str): Client identifier to remove
        """
        with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]
                logger.info(f"Client removed: {client_id}")
            
            if client_id in self.file_clients:
                del self.file_clients[client_id]
                logger.info(f"File client removed: {client_id}")

    def accept_clients(self):
        """Accept incoming client connections"""
        while self.is_running:
            try:
                client_socket, address = self.server_socket.accept()
                client_socket.settimeout(SOCKET_TIMEOUT)
                
                logger.info(f"New client connection from {address}")

                threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address),
                    daemon=True,
                    name=f"ClientHandler-{address[0]}"
                ).start()

            except Exception as e:
                if self.is_running:
                    logger.error(f"Error accepting client: {e}")
                time.sleep(1)

    def accept_screen_clients(self):
        """Accept incoming screen stream connections"""
        while self.is_running:
            try:
                screen_socket, address = self.screen_server_socket.accept()
                screen_socket.settimeout(SOCKET_TIMEOUT)
                
                logger.info(f"New screen client connection from {address}")

                threading.Thread(
                    target=self.handle_screen_client,
                    args=(screen_socket, address),
                    daemon=True,
                    name=f"ScreenHandler-{address[0]}"
                ).start()

            except Exception as e:
                if self.is_running:
                    logger.error(f"Error accepting screen client: {e}")
                time.sleep(1)

    def accept_file_clients(self):
        """Accept incoming file transfer connections"""
        while self.is_running:
            try:
                file_socket, address = self.file_server_socket.accept()
                file_socket.settimeout(SOCKET_TIMEOUT)
                
                logger.info(f"New file client connection from {address}")

                threading.Thread(
                    target=self.handle_file_client,
                    args=(file_socket, address),
                    daemon=True,
                    name=f"FileHandler-{address[0]}"
                ).start()

            except Exception as e:
                if self.is_running:
                    logger.error(f"Error accepting file client: {e}")
                time.sleep(1)

    def send_command(self, client_id, command):
        """
        Send command to a specific client
        
        Args:
            client_id (str): Target client ID
            command (str): Command to send
            
        Returns:
            bool: True if sent successfully
        """
        with self.lock:
            client_socket = self.clients.get(client_id)

        if not client_socket:
            logger.warning(f"Client socket not found: {client_id}")
            return False

        try:
            client_socket.send(command.encode())
            logger.info(f"Command sent to {client_id}: {command}")
            return True

        except socket.error as e:
            logger.error(f"Failed to send command to {client_id}: {e}")
            self.remove_client(client_id)
            return False

    def handle_client(self, client_socket, address):
        """
        Handle main client connection
        
        Args:
            client_socket: Connected socket
            address: Client address tuple
        """
        client_id = None
        
        try:
            while self.is_running:
                try:
                    data = client_socket.recv(DEFAULT_BUFFER_SIZE).decode()

                    if not data:
                        logger.info(f"Client disconnected (empty data): {address}")
                        break

                    logger.debug(f"Received from {address}: {data}")

                    parts = data.split("|")

                    # Handle INFO packet
                    if parts[0] == "INFO" and len(parts) >= 2:
                        client_id = parts[1]
                        self.register_client(client_id, client_socket)

                    # Call user-defined callback
                    if self.on_packet_received:
                        self.on_packet_received(
                            client_socket,
                            address,
                            data
                        )

                except socket.timeout:
                    logger.warning(f"Socket timeout for client: {address}")
                    break
                except UnicodeDecodeError as e:
                    logger.error(f"Decode error from {address}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Client error ({address}): {e}", exc_info=True)

        finally:
            logger.info(f"Client session ended: {address}")
            
            try:
                client_socket.close()
            except:
                pass
            
            if client_id:
                self.remove_client(client_id)
                if self.on_client_disconnected:
                    self.on_client_disconnected(client_id)

    def handle_screen_client(self, screen_socket, address):
        """
        Handle screen streaming from client
        
        Args:
            screen_socket: Screen stream socket
            address: Client address
        """
        try:
            payload_size = struct.calcsize("Q")
            data = b""

            while self.is_running:
                try:
                    # Receive payload size
                    while len(data) < payload_size:
                        packet = screen_socket.recv(DEFAULT_BUFFER_SIZE)

                        if not packet:
                            logger.info(f"Screen client disconnected: {address}")
                            return

                        data += packet

                    packed_msg_size = data[:payload_size]
                    data = data[payload_size:]

                    msg_size = struct.unpack("Q", packed_msg_size)[0]

                    # Receive frame data
                    while len(data) < msg_size:
                        packet = screen_socket.recv(DEFAULT_BUFFER_SIZE)

                        if not packet:
                            logger.info(f"Screen stream ended: {address}")
                            return

                        data += packet

                    frame_data = data[:msg_size]
                    data = data[msg_size:]

                    # Unpack frame
                    try:
                        client_id, frame_bytes = pickle.loads(frame_data)
                        frame = pickle.loads(frame_bytes)
                        frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)

                        if self.on_screen_frame:
                            self.on_screen_frame(client_id, frame)

                    except Exception as e:
                        logger.error(f"Frame processing error: {e}")
                        continue

                except socket.timeout:
                    logger.warning(f"Screen socket timeout: {address}")
                    break

        except Exception as e:
            logger.error(f"Screen handler error ({address}): {e}", exc_info=True)

        finally:
            try:
                screen_socket.close()
            except:
                pass
            logger.info(f"Screen socket closed: {address}")

    def handle_file_client(self, client_socket, address):
        """
        Handle file transfer from/to client
        
        Args:
            client_socket: File transfer socket
            address: Client address
        """
        client_id = None
        
        try:
            # First packet: FILE_CONNECT|client_id
            data = client_socket.recv(1024).decode()

            if not data:
                logger.warning(f"No data from file client: {address}")
                return

            logger.debug(f"File socket data: {data}")

            parts = data.split("|")

            if parts[0] == "FILE_CONNECT" and len(parts) >= 2:
                client_id = parts[1]
                
                with self.lock:
                    self.file_clients[client_id] = client_socket
                
                logger.info(f"File client registered: {client_id}")

            # Handle file transfers
            while self.is_running and client_id:
                try:
                    header = client_socket.recv(FILE_HEADER_SIZE).decode().strip()

                    if not header:
                        continue

                    parts = header.split("|")

                    # Handle file from client
                    if parts[0] == "FILES_FROM_CLIENT" and len(parts) >= 3:
                        filename = parts[1]
                        filesize = int(parts[2])

                        self._receive_file(
                            client_socket,
                            filename,
                            filesize,
                            client_id
                        )

                except socket.timeout:
                    logger.debug(f"File socket timeout: {address}")
                    continue
                except Exception as e:
                    logger.error(f"File receive error: {e}")
                    break

        except Exception as e:
            logger.error(f"File client error ({address}): {e}", exc_info=True)

        finally:
            try:
                client_socket.close()
            except:
                pass
            
            if client_id:
                self.remove_client(client_id)
            
            logger.info(f"File socket closed: {address}")

    def _receive_file(self, socket_obj, filename, filesize, client_id):
        """
        Receive file from client with progress tracking
        
        Args:
            socket_obj: Socket to receive from
            filename: Name of file to save
            filesize: Size of file in bytes
            client_id: ID of sending client
        """
        try:
            os.makedirs("files_got", exist_ok=True)
            save_path = os.path.join("files_got", filename)

            received = 0
            start_time = time.time()

            with open(save_path, "wb") as f:
                while received < filesize:
                    to_receive = min(
                        DEFAULT_BUFFER_SIZE,
                        filesize - received
                    )
                    
                    data = socket_obj.recv(to_receive)

                    if not data:
                        logger.warning(f"Incomplete file transfer: {filename}")
                        break

                    f.write(data)
                    received += len(data)

                    # Progress callback
                    if self.on_file_progress:
                        progress = (received / filesize) * 100
                        self.on_file_progress(client_id, filename, progress)

            elapsed = time.time() - start_time
            speed = (filesize / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            
            logger.info(
                f"File received: {filename} ({filesize/1024:.2f}KB) "
                f"from {client_id} in {elapsed:.2f}s ({speed:.2f}MB/s)"
            )

        except Exception as e:
            logger.error(f"Failed to receive file {filename}: {e}", exc_info=True)

    def send_file(self, client_id, file_path, callback=None):
        """
        Send file to client with progress tracking
        
        Args:
            client_id (str): Target client ID
            file_path (str): Path to file to send
            callback: Progress callback function
            
        Returns:
            bool: True if sent successfully
        """
        with self.lock:
            file_socket = self.file_clients.get(client_id)

        if not file_socket:
            logger.error(f"File socket not found for client: {client_id}")
            return False

        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return False

            filename = os.path.basename(file_path)
            filesize = os.path.getsize(file_path)

            header = f"FILE|{filename}|{filesize}"
            file_socket.sendall(header.encode().ljust(FILE_HEADER_SIZE))

            sent = 0
            start_time = time.time()

            with open(file_path, "rb") as f:
                while True:
                    data = f.read(DEFAULT_BUFFER_SIZE)

                    if not data:
                        break

                    file_socket.sendall(data)
                    sent += len(data)

                    # Progress callback
                    if callback:
                        progress = (sent / filesize) * 100
                        callback(client_id, filename, progress)

            elapsed = time.time() - start_time
            speed = (filesize / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            
            logger.info(
                f"File sent: {filename} ({filesize/1024:.2f}KB) "
                f"to {client_id} in {elapsed:.2f}s ({speed:.2f}MB/s)"
            )
            return True

        except socket.error as e:
            logger.error(f"Socket error sending file to {client_id}: {e}")
            self.remove_client(client_id)
            return False
        except Exception as e:
            logger.error(f"Failed to send file to {client_id}: {e}", exc_info=True)
            return False

    def shutdown(self):
        """Gracefully shutdown the server"""
        logger.info("Server shutdown initiated")
        self.is_running = False
        
        try:
            self.server_socket.close()
            self.screen_server_socket.close()
            self.file_server_socket.close()
        except:
            pass
        
        logger.info("Server shutdown completed")