# -*- coding: utf-8 -*-
"""
Socket server with activity handling
"""
import pickle
import socket
import threading
import struct
import time
import cv2
import os
import json
from utils.activity_db import bulk_insert
from utils.logger import LoggerSetup

logger = LoggerSetup.get_logger(__name__)


class SocketServer:

    def __init__(
            self,
            host="0.0.0.0",
            port=5000,
            on_packet_received=None,
            on_client_disconnected=None,
            on_screen_frame=None
        ):

        self.host = host
        self.port = port

        self.on_packet_received = on_packet_received
        self.on_client_disconnected = on_client_disconnected
        self.on_screen_frame = on_screen_frame

        self.server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self.screen_server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.screen_server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self.file_server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.file_server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self.file_clients = {}

        self.screen_port = 5001

        self.is_running = True
        self.clients = {}
        self.file_clients = {}

    def start(self):
        self.is_running = True
       
        # ================= MAIN SERVER =================
        self.server_socket.bind(
            (self.host, self.port)
        )
        self.server_socket.listen(100)

        # ================= SCREEN SERVER =================
        self.screen_server_socket.bind(
            (self.host, 5001)
        )

        self.screen_server_socket.listen(100)

        # ================= FILE SERVER =================
        self.file_server_socket.bind(
            (self.host, 5002)
        )

        self.file_server_socket.listen(100)

        # ================= LOG =================
        logger.info(f"Main server: {self.host}:{self.port}")
        logger.info(f"Screen server: {self.host}:5001")
        logger.info(f"File server: {self.host}:5002")

        # ================= THREADS =================
        threading.Thread(
            target=self.accept_clients,
            daemon=True
        ).start()

        threading.Thread(
            target=self.accept_screen_clients,
            daemon=True
        ).start()

        threading.Thread(
            target=self.accept_file_clients,
            daemon=True
        ).start()


    def register_client(self, client_id, client_socket):
        self.clients[client_id] = client_socket

        logger.info(f"Registered client: {client_id}")

    def remove_client(self, client_id):
        if client_id in self.clients:
            del self.clients[client_id]
            logger.info(f"Removed client: {client_id}")

    def accept_clients(self):

        while self.is_running:

            client_socket, address = self.server_socket.accept()

            logger.info(f"Client connected: {address}")

            threading.Thread(
                target=self.handle_client,
                args=(client_socket, address),
                daemon=True
            ).start()


    def accept_screen_clients(self):
        while self.is_running:

            screen_socket, address = (
                self.screen_server_socket.accept()
            )

            logger.info(
                "Screen client connected:",
                address
            )

            threading.Thread(
                target=self.handle_screen_client,
                args=(screen_socket, address),
                daemon=True
            ).start()

    def send_command(self, client_id, command):
        client_socket = self.clients.get(client_id)

        if not client_socket:
            logger.warning(f"Client socket not found: {client_id}")
            return

        try:

            client_socket.send(command.encode())

            logger.info(f"Sent command to {client_id}: {command}")

        except Exception as e:

            logger.error("Send command error:", exc_info=True)
    
    
    def handle_client(self, client_socket, address):

        client_id = None

        try:

            while self.is_running:

                data = client_socket.recv(4096).decode()

                if not data:
                    break

                logger.debug(f"Received from {address}: {data}")

                parts = data.split("|")

                # Handle INFO packet
                if parts[0] == "INFO" and len(parts) >= 2:
                    client_id = parts[1]
                    self.register_client(client_id, client_socket)

                # Handle ACTIVITY packet
                if parts[0] == "ACTIVITY" and len(parts) >= 3:
                    client_id = parts[1]
                    json_payload = "|".join(parts[2:])
                    try:
                        obj = json.loads(json_payload)
                    except Exception as e:
                        logger.error(f"Invalid ACTIVITY JSON from {address}: {e}")
                        obj = {}

                    entries = []
                    now_ts = int(time.time())
                    for p in obj.get("processes", []):
                        entries.append({"type": "process", "name": p.get("name", ""), "url": "", "ts": now_ts})
                    for w in obj.get("windows", []):
                        entries.append({"type": "window", "name": w.get("title", ""), "url": "", "ts": now_ts})

                    if entries:
                        try:
                            bulk_insert(client_id, entries)
                        except Exception:
                            logger.exception("Failed to persist activity entries")

                    # call callback for packet received so UI can update if needed
                    if self.on_packet_received:
                        self.on_packet_received(client_socket, address, data)

                    continue

                if self.on_packet_received:

                    self.on_packet_received(
                        client_socket,
                        address,
                        data
                    )

        except Exception as e:

            logger.exception("Client error")

        finally:

            logger.info(f"Client disconnected: {address}")

            if client_id:
                self.remove_client(client_id)

            if self.on_client_disconnected:
                self.on_client_disconnected(client_id)

            try:
                client_socket.close()
            except:
                pass


    def handle_screen_client(
        self,
        screen_socket,
        address
    ):

        try:

            payload_size = struct.calcsize("Q")

            data = b""

            while self.is_running:

                while len(data) < payload_size:

                    packet = screen_socket.recv(4096)

                    if not packet:
                        return

                    data += packet

                packed_msg_size = data[:payload_size]

                data = data[payload_size:]

                msg_size = struct.unpack(
                    "Q",
                    packed_msg_size
                )[0]

                while len(data) < msg_size:

                    packet = screen_socket.recv(4096)

                    if not packet:
                        return

                    data += packet

                frame_data = data[:msg_size]

                data = data[msg_size:]

                client_id, frame_bytes = pickle.loads(frame_data)
                frame = pickle.loads(frame_bytes)

                frame = cv2.imdecode(
                    frame,
                    cv2.IMREAD_COLOR
                )

                if self.on_screen_frame:

                    self.on_screen_frame(
                        client_id,
                        frame
                    )

        except Exception as e:

            logger.exception("Screen error")

        finally:

            try:
                screen_socket.close()
            except:
                pass


    def accept_file_clients(self):
        while self.is_running:

            file_socket, address = (
                self.file_server_socket.accept()
            )

            logger.info(
                "File client connected:",
                address
            )

            threading.Thread(
                target=self.handle_file_client,
                args=(file_socket, address),
                daemon=True
            ).start()


    def handle_file_client(
        self,
        client_socket,
        address
    ):
        try:

            data = client_socket.recv(1024).decode()

            logger.debug("FILE SOCKET DATA: %s", data)

            parts = data.split("|")

            if parts[0] == "FILE_CONNECT":

                client_id = parts[1]

                self.file_clients[client_id] = client_socket

                logger.info(
                    f"File client registered: {client_id}"
                )

            while self.is_running:
                header = (
                    client_socket.recv(256)
                    .decode()
                    .strip()
                )

                if not header:
                    continue

                parts = header.split("|")

                # ================= FILE FROM CLIENT =================

                if parts[0] == "FILES_FROM_CLIENT":

                    filename = parts[1]

                    filesize = int(parts[2])

                    os.makedirs(
                        "files_got",
                        exist_ok=True
                    )

                    save_path = os.path.join(
                        "files_got",
                        filename
                    )

                    received = 0

                    with open(save_path, "wb") as f:

                        while received < filesize:

                            data = client_socket.recv(
                                min(
                                    4096,
                                    filesize - received
                                )
                            )

                            if not data:
                                break

                            f.write(data)

                            received += len(data)

                    logger.info(
                        f"Received file from client: {filename}"
                    )

        except Exception as e:

            logger.exception("File client error")

    def send_file(
        self,
        client_id,
        file_path
    ):

        file_socket = self.file_clients.get(
            client_id
        )

        if not file_socket:
            logger.warning("Client file socket not found")
            return

        try:

            filename = os.path.basename(
                file_path
            )

            filesize = os.path.getsize(
                file_path
            )

            header = (
                f"FILE|{filename}|{filesize}"
            )

            file_socket.sendall(
                header.encode().ljust(256)
            )

            with open(file_path, "rb") as f:

                while True:

                    data = f.read(4096)

                    if not data:
                        break

                    file_socket.sendall(data)

            logger.info(
                f"Sent file to {client_id}"
            )

        except Exception as e:

            logger.exception("Send file error")
