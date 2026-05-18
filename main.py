import sys
import time
import threading
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QTimer , Qt
from PyQt5.QtGui import QPixmap , QImage
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QFrame,
    QMainWindow,
    QPushButton,
    QTableWidgetItem
)
import cv2
import pickle
import struct
import numpy as np


from ui.ui_main1 import Ui_quanlyphongmay
from core.computer_manager import ComputerManager
from network.server import SocketServer
from models.computer import Computer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_quanlyphongmay()
        self.ui.setupUi(self)
        self.ui.list_clients.setSelectionMode(
            QtWidgets.QAbstractItemView.MultiSelection
        )

#         self.ui.list_clients.setSelectionMode(
#     QtWidgets.QAbstractItemView.ExtendedSelection
# )

        self.setWindowTitle("Phần mềm quản lý phòng máy")
        self.ui.main_stacked_widget.setCurrentIndex(0)
        self.ui.label_page_title.setText("Dashboard")

        self.computer_manager = ComputerManager()
        self.selected_computer = None
        #self.computer_manager.load_demo_data()

        self.server = SocketServer(
        on_packet_received=self.on_packet_received,
        on_client_disconnected=self.on_client_disconnected,
        on_screen_frame=self.on_screen_frame
    )
        
        self.server.start()
        

        
        

       # init
        self.setup_navigation()
        self.setup_table()

        self.screen_buffers = {}
        self.monitor_labels = {}

        self.refresh_table()

        self.start_timeout_checker()

        self.ui.computer_card.hide()
        

    def setup_navigation(self):
        self.ui.btn_dashboard.clicked.connect(
            lambda: self.switch_page(0, "Dashboard")
        )

        self.ui.btn_computers.clicked.connect(
            lambda: self.switch_page(1, "Máy tính")
        )

        self.ui.btn_monitor.clicked.connect(
            lambda: self.switch_page(2, "Điều khiển")
        )

        self.ui.btn_files.clicked.connect(
            lambda: self.switch_page(4, "Tệp tin")
        )

        self.ui.btn_settings.clicked.connect(
            lambda: self.switch_page(3, "Cài đặt")
        )

        self.ui.btn_choose_file.clicked.connect(
            self.choose_file
        )

        self.ui.btn_send_file.clicked.connect(
            self.send_selected_file
        )

        self.ui.btn_getfiles.clicked.connect(
            self.request_files_from_clients
        )


    def switch_page(self, index, title):
        self.ui.main_stacked_widget.setCurrentIndex(index)
        self.ui.label_page_title.setText(title)


    def setup_table(self):

        self.ui.tableWidget.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )

        self.ui.tableWidget.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )

        self.ui.tableWidget.verticalHeader().setVisible(False)

        header = self.ui.tableWidget.horizontalHeader()

        header.setStretchLastSection(True)

        self.ui.tableWidget.setColumnWidth(0, 180)
        self.ui.tableWidget.setColumnWidth(1, 180)
        self.ui.tableWidget.setColumnWidth(2, 120)
        self.ui.tableWidget.setColumnWidth(3, 120)
    


    def add_computer_to_table(self, row, computer):
        values = [
            computer.name,
            computer.ip,
            computer.status,
            computer.ping
        ]

        for col, value in enumerate(values):

            self.ui.tableWidget.setItem(
                row,
                col,
                QTableWidgetItem(value)
            )

        # button
        btn = QPushButton("Ngat ket noi")
        btn.clicked.connect(lambda _, c=computer: self.disconnect_client(c))
        btn.setStyleSheet("""
            QPushButton{
                background-color:#2563EB;
                color:white;
                border:none;
                padding:6px 10px;
                border-radius:8px;
            }

            QPushButton:hover{
                background-color:#3B82F6;
            }
        """)

        self.ui.tableWidget.setCellWidget(row, 4, btn)

    def update_computer_row(self, row, computer):
        self.ui.tableWidget.item(row, 0).setText(computer.name)
        self.ui.tableWidget.item(row, 1).setText(computer.ip)
        self.ui.tableWidget.item(row, 2).setText(computer.status)
        self.ui.tableWidget.item(row, 3).setText(computer.ping)

    def refresh_table(self):
        self.ui.tableWidget.setRowCount(0)
        computers = self.computer_manager.get_all_computers()

        self.ui.tableWidget.setRowCount(len(computers))

        online = 0
        offline = 0

        for row, computer in enumerate(computers):
            self.add_computer_to_table(row, computer)

            # đếm trạng thái
            if computer.status == "Online":
                online += 1
            else:
                offline += 1

        self.ui.label_online_count.setText(str(online))
        self.ui.label_offline_count.setText(str(offline))

        # table đẹp hơn
        self.ui.tableWidget.horizontalHeader().setStretchLastSection(True)
        self.ui.tableWidget.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        self.render_computer_cards()
        self.render_monitor_cards()
        self.refresh_clients_list()
    
    # Nhận dữ liệu từ client
    def on_packet_received(self, client_socket, address, data):

        ip = address[0]

        parts = data.split("|")

        packet_type = parts[0]

        # ================= INFO =================

        if packet_type == "INFO":

            try:

                client_id = parts[1]
                computer_name = parts[2]
                username = parts[3]
                os_name = parts[4]

            except:
                return

            computer = Computer(
                client_id=client_id,
                name=computer_name,
                ip=ip,
                status="Online",
                ping="1ms"
            )

            existing = self.computer_manager.get_computer_by_id(client_id)

            if existing:

                existing.status = "Online"
                existing.ping = "1ms"

            else:

                self.computer_manager.add_computer(computer)

            print(f"{computer_name} connected")

            QTimer.singleShot(0, self.refresh_table)

        # ================= PING =================

        elif packet_type == "PING":
            if len(parts) < 2:
                return

            client_id = parts[1]

            computer = self.computer_manager.get_computer_by_id(
                client_id
            )

            if not computer:
                return

            computer.last_heartbeat = time.time()

            print(f"Heartbeat from {computer.name}")

        elif packet_type == "SCREEN":
            client_id = parts[1]

            image_size = int(parts[2])

            image_data = b""

            while len(image_data) < image_size:

                chunk = client_socket.recv(
                    image_size - len(image_data)
                )

                if not chunk:
                    return

                image_data += chunk

            self.screen_buffers[client_id] = image_data

            if (
                hasattr(self, "selected_computer")
                and
                self.selected_computer.client_id == client_id
            ):

                QTimer.singleShot(
                    0,
                    lambda d=image_data:
                    self.update_screen_preview(d)
                )
    
    
    def on_client_disconnected(self, client_id):
        computer = self.computer_manager.get_computer_by_id(
            client_id
        )

        if not computer:
            return

        computer.status = "Offline"
        computer.ping = "-"

        print(f"{computer.name} offline")

        QTimer.singleShot(0, self.refresh_table)

    def disconnect_client(self, computer):
        self.server.send_command(
            computer.client_id,
            "DISCONNECT"
        )

    def start_timeout_checker(self):
        threading.Thread(
            target=self.timeout_checker_loop,
            daemon=True
        ).start()


    def timeout_checker_loop(self):
        while True:

            current_time = time.time()

            computers = self.computer_manager.get_all_computers()

            updated = False

            for computer in computers:

                if computer.status == "Offline":
                    continue

                elapsed = current_time - computer.last_heartbeat

                if elapsed > 15:

                    computer.status = "Offline"
                    computer.ping = "-"

                    print(f"{computer.name} timeout")

                    updated = True

            if updated:

                QTimer.singleShot(0, self.refresh_table)

            time.sleep(5)



    def render_computer_cards(self):
        layout = self.ui.gridLayout_2
        
        # clear old cards
        while layout.count():

            item = layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

        computers = self.computer_manager.get_all_computers()

        online_computers = [
            c for c in computers
            if c.status == "Online"
        ]

        row = 0
        col = 0

        for computer in online_computers:

            card = self.create_card(computer)

            layout.addWidget(card, row, col)

            col += 1

            if col >= 4:
                col = 0
                row += 1



    def create_card(self, computer):
        card = QFrame()
        
        card.setStyleSheet("""
            QFrame{
                background-color:#1E293B;
                border-radius:15px;
            }
        """)

        card.setFixedSize(220, 140)

        layout = QtWidgets.QVBoxLayout(card)

        # name
        label_name = QLabel(computer.name)

        label_name.setStyleSheet("""
            color:white;
            font-size:18px;
            font-weight:bold;
        """)

        # ip
        label_ip = QLabel(computer.ip)

        label_ip.setStyleSheet("""
            color:#CBD5E1;
        """)

        # status
        label_status = QLabel("● Online")

        label_status.setStyleSheet("""
            color:#22C55E;
            font-weight:bold;
        """)

        # ping
        label_ping = QLabel(f"Ping: {computer.ping}")

        label_ping.setStyleSheet("""
            color:#CBD5E1;
        """)

        # button
        btn = QPushButton("Điều khiển")
        btn.clicked.connect(
            lambda _, c=computer: self.open_monitor(c)
        )
        btn.setStyleSheet("""
            QPushButton{
                background-color:#2563EB;
                color:white;
                border:none;
                padding:8px;
                border-radius:10px;
            }
        """)

        layout.addWidget(label_name)
        layout.addWidget(label_ip)
        layout.addWidget(label_status)
        layout.addWidget(label_ping)

        layout.addStretch()

        layout.addWidget(btn)

        return card

    def open_monitor(self, computer):
        self.selected_computer = computer

        self.switch_page(2, "Điều khiển")

        self.ui.label_15.setText(f"🖥 {computer.name}")
    
    #hien thi anh 
    def update_screen_preview(self, image_data):
        pixmap = QPixmap()

        pixmap.loadFromData(image_data)

        self.ui.label_16.setPixmap(

            pixmap.scaled(
                self.ui.label_16.width(),
                self.ui.label_16.height()
            )
        )

    def on_screen_frame(self, client_id, frame):
        label = self.monitor_labels.get(client_id)

        if not label:
            return

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        h, w, ch = rgb.shape

        bytes_per_line = ch * w

        image = QImage(
            rgb.data,
            w,
            h,
            bytes_per_line,
            QImage.Format_RGB888
        )

        pixmap = QPixmap.fromImage(image)

        label.setPixmap(
            pixmap.scaled(
                label.width(),
                label.height(),
                Qt.KeepAspectRatio
            )
        )


    def render_monitor_cards(self):

        layout = self.ui.gridLayout

        while layout.count():

            item = layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.monitor_labels.clear()

        online_computers = [
            c for c in self.computer_manager.get_all_computers()
            if c.status == "Online"
        ]

        row = 0
        col = 0

        for computer in online_computers:

            card, preview_label = self.create_monitor_card(
                computer
            )

            self.monitor_labels[
                computer.client_id
            ] = preview_label

            layout.addWidget(card, row, col)

            col += 1

            if col >= 2:
                col = 0
                row += 1

    def create_monitor_card(self, computer):
        card = QFrame()

        card.setStyleSheet("""
            QFrame{
                background-color:#111827;
                border-radius:20px;
            }
        """)

        card.setMinimumSize(400, 260)

        layout = QtWidgets.QVBoxLayout(card)

        title = QLabel(f"🖥 {computer.name}")

        title.setStyleSheet("""
            color:white;
            font-size:18px;
            font-weight:bold;
        """)

        preview = QLabel()

        preview.setMinimumSize(350, 180)

        preview.setStyleSheet("""
            background-color:#1F2937;
            border-radius:15px;
            color:#6B7280;
        """)

        preview.setAlignment(Qt.AlignCenter)

        preview.setText("Loading stream...")

        layout.addWidget(title)
        layout.addWidget(preview)

        return card, preview
    
    def refresh_clients_list(self):
        self.ui.list_clients.clear()

        computers = [
            c for c in
            self.computer_manager.get_all_computers()
            if c.status == "Online"
        ]

        for computer in computers:

            item = QtWidgets.QListWidgetItem(
                f"{computer.name} ({computer.ip})"
            )

            item.setData(
                QtCore.Qt.UserRole,
                computer.client_id
            )

            self.ui.list_clients.addItem(item)


    def choose_file(self):

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Chọn file"
        )

        if not file_path:
            return
        self.selected_file = file_path

        self.ui.line_file_path.setText(
            file_path
        )

    def send_selected_file(self):
        items = self.ui.list_clients.selectedItems()

        if not items:
            print("Chưa chọn client")
            return

        if not self.selected_file:
            print("Chưa chọn file")
            return

        for item in items:

            client_id = item.data(
                QtCore.Qt.UserRole
            )

            self.server.send_file(
                client_id,
                self.selected_file
            )

            self.ui.text_log.append(
                f"Đã gửi file tới {item.text()}"
            )
    
    
    def request_files_from_clients(self):

        items = self.ui.list_clients.selectedItems()

        if not items:
            return

        for item in items:

            client_id = item.data(
                QtCore.Qt.UserRole
            )

            self.server.send_command(
                client_id,
                "GET_FILES"
            )

            self.ui.text_log.append(
                f"Đang lấy file từ {item.text()}"
            )

    # def test_update(self):
    #     computers = self.computer_manager.get_all_computers()

    #     if len(computers) > 0:

    #         computer = computers[0]

    #         computer.status = "Offline"
    #         computer.ping = "-"

    #         self.update_computer_row(0, computer)


if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())