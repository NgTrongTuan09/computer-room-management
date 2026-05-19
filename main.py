# -*- coding: utf-8 -*-
""" 
19/5
Main GUI Application - Phần mềm quản lý phòng máy tính
Improvements:
- Added comprehensive logging
- File transfer progress bar
- Better error handling
- Status indicators
- Improved UI responsiveness
"""
import sys
import time
import threading
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QFrame,
    QMainWindow,
    QPushButton,
    QTableWidgetItem,
    QMessageBox,
    QProgressDialog
)
import cv2
import numpy as np

from ui.ui_main1 import Ui_quanlyphongmay
from core.computer_manager import ComputerManager
from network.server import SocketServer
from models.computer import Computer
from utils.logger import LoggerSetup

# New imports for activity DB and dialog
from utils.activity_db import init_db
from ui.activity_window import ActivityWindow

logger = LoggerSetup.get_logger(__name__)

# Constants
TIMEOUT_THRESHOLD = 15
TIMEOUT_CHECK_INTERVAL = 5


class FileTransferSignals(QtCore.QObject):
    """Signals for file transfer progress"""
    progress = pyqtSignal(str, str, float)  # client_id, filename, progress

class ServerSignals(QtCore.QObject):
    client_status_changed = pyqtSignal() # Tín hiệu làm mới bảng
    frame_received = pyqtSignal(str, object)

class MainWindow(QMainWindow):
    """
    Main application window for Computer Room Management
    """
    
    def __init__(self):
        super().__init__()

        logger.info("Initializing MainWindow")

        self.ui = Ui_quanlyphongmay()
        self.ui.setupUi(self)
        self.ui.list_clients.setSelectionMode(
            QtWidgets.QAbstractItemView.MultiSelection
        )

        self.setWindowTitle("Phần mềm quản lý phòng máy")
        self.ui.main_stacked_widget.setCurrentIndex(0)
        self.ui.label_page_title.setText("Dashboard")

        self.computer_manager = ComputerManager()
        self.selected_computer = None
        self.selected_file = None
        
        # File transfer signals
        self.file_signals = FileTransferSignals()
        self.file_signals.progress.connect(self.on_file_progress)

        self.signals = ServerSignals()
        self.signals.client_status_changed.connect(self.refresh_table)
        self.signals.frame_received.connect(self.update_screen_ui)

        # Progress dialogs for file transfers
        self.progress_dialogs = {}

        # init activity DB
        init_db()
        # track open activity windows: client_id -> ActivityWindow
        self.open_activity_windows = {}

        logger.info("Starting Socket Server")
        self.server = SocketServer(
            on_packet_received=self.on_packet_received,
            on_client_disconnected=self.on_client_disconnected,
            on_screen_frame=self.on_screen_frame,
            on_file_progress=self.on_file_progress_callback
        )
        
        self.server.start()

        # UI initialization
        self.setup_navigation()
        self.setup_table()

        self.screen_buffers = {}
        self.monitor_labels = {}

        self.signals.client_status_changed.emit()
        self.start_timeout_checker()

        self.ui.computer_card.hide()
        
        logger.info("MainWindow initialized successfully")

    def setup_navigation(self):
        """Setup navigation button connections"""
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

        self.ui.btn_refresh.clicked.connect(self.refresh_table)
        self.ui.btn_choose_file.clicked.connect(self.choose_file)
        self.ui.btn_send_file.clicked.connect(self.send_selected_file)
        self.ui.btn_getfiles.clicked.connect(self.request_files_from_clients)
        
        logger.info("Navigation setup completed")

    def switch_page(self, index, title):
        """Switch to page and update title"""
        self.ui.main_stacked_widget.setCurrentIndex(index)
        self.ui.label_page_title.setText(title)
        logger.debug(f"Switched to page: {title} (index: {index})")

    def setup_table(self):
        """Setup table widget properties"""
        self.ui.tableWidget.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )

        self.ui.tableWidget.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )

        self.ui.tableWidget.verticalHeader().setVisible(False)
        self.ui.tableWidget.setColumnWidth(0, 180)
        self.ui.tableWidget.setColumnWidth(1, 180)
        self.ui.tableWidget.setColumnWidth(2, 120)
        self.ui.tableWidget.setColumnWidth(3, 120)

    def add_computer_to_table(self, row, computer):
        """Add computer row to table"""
        values = [
            computer.name,
            computer.ip,
            computer.status,
            computer.ping
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            
            # Color code status
            if col == 2:  # Status column
                if value == "Online":
                    item.setBackground(QColor("#10B981"))  # Green
                else:
                    item.setBackground(QColor("#EF4444"))  # Red
            
            self.ui.tableWidget.setItem(row, col, item)

        # Disconnect or reconnect button
        if computer.status == "Online":
            btn = QPushButton("Ngắt kết nối")
            btn.clicked.connect(lambda _, c=computer: self.disconnect_client(c))
            btn.setStyleSheet("""
                QPushButton{ background-color:#EF4444; color:white; border:none; padding:6px 10px; border-radius:8px; font-weight: bold; }
                QPushButton:hover{ background-color:#DC2626; }
            """)
        else:
            btn = QPushButton("Kết nối lại")
            btn.clicked.connect(lambda _, c=computer: self.reconnect_client(c))
            btn.setStyleSheet("""
                QPushButton{ background-color:#10B981; color:white; border:none; padding:6px 10px; border-radius:8px; font-weight: bold; }
                QPushButton:hover{ background-color:#059669; }
            """)

        self.ui.tableWidget.setCellWidget(row, 4, btn)

    def refresh_table(self):
        """Refresh dashboard table and cards"""
        try:
            self.ui.tableWidget.setRowCount(0)
            computers = self.computer_manager.get_all_computers()

            self.ui.tableWidget.setRowCount(len(computers))

            online = 0
            offline = 0

            for row, computer in enumerate(computers):
                self.add_computer_to_table(row, computer)

                if computer.status == "Online":
                    online += 1
                else:
                    offline += 1

            self.ui.label_online_count.setText(str(online))
            self.ui.label_offline_count.setText(str(offline))

            # Auto-stretch columns
            self.ui.tableWidget.horizontalHeader().setStretchLastSection(True)
            self.ui.tableWidget.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )

            self.render_computer_cards()
            self.render_monitor_cards()
            self.refresh_clients_list()
            
            logger.debug(f"Table refreshed - Online: {online}, Offline: {offline}")

        except Exception as e:
            logger.error(f"Error refreshing table: {e}", exc_info=True)

    def on_packet_received(self, client_socket, address, data):
        """Handle received packet from client"""
        try:
            ip = address[0]
            parts = data.split("|")
            packet_type = parts[0]

            if packet_type == "INFO" and len(parts) >= 5:
                self._handle_info_packet(parts, ip)

            elif packet_type == "PING" and len(parts) >= 2:
                self._handle_ping_packet(parts)

            elif packet_type == "ACTIVITY" and len(parts) >= 2:
                # Server already persisted activity entries into DB.
                # If an ActivityWindow is open for this client, refresh it.
                client_id = parts[1]
                if client_id in self.open_activity_windows:
                    QTimer.singleShot(0, lambda cid=client_id: self.open_activity_windows[cid].reload_history())

        except Exception as e:
            logger.error(f"Error processing packet: {e}", exc_info=True)

    def _handle_info_packet(self, parts, ip):
        """Handle INFO packet from client"""
        try:
            client_id = parts[1]
            computer_name = parts[2]
            username = parts[3]
            os_name = parts[4]

            existing = self.computer_manager.get_computer_by_id(client_id)

            # KIỂM TRA CHẶN: Nếu máy đã có trong data và đang bị block
            if existing and getattr(existing, 'is_blocked', False):
                logger.info(f"Từ chối kết nối từ máy đang bị chặn: {computer_name}")
                self.server.send_command(client_id, "DISCONNECT")
                return # Thoát luôn, không set nó thành Online

            if existing:
                existing.status = "Online"
                existing.ping = "1ms"
                existing.ip = ip # Cập nhật ip phòng trường hợp đổi mạng
            else:
                computer = Computer(
                    client_id=client_id,
                    name=computer_name,
                    ip=ip,
                    status="Online",
                    ping="1ms"
                )
                self.computer_manager.add_computer(computer)

            logger.info(f"Computer connected: {computer_name} ({ip}) - User: {username} - OS: {os_name}")
            QTimer.singleShot(0, self.refresh_table)

        except (IndexError, ValueError) as e:
            logger.error(f"Invalid INFO packet format: {e}")

    def _handle_ping_packet(self, parts):
        """Handle PING packet from client"""
        try:
            client_id = parts[1]
            computer = self.computer_manager.get_computer_by_id(client_id)

            if computer:
                computer.last_heartbeat = time.time()
                logger.debug(f"Heartbeat received from: {computer.name}")

        except Exception as e:
            logger.error(f"Error handling PING packet: {e}")

    def on_client_disconnected(self, client_id):
        """Handle client disconnection"""
        try:
            computer = self.computer_manager.get_computer_by_id(client_id)

            if not computer:
                logger.warning(f"Disconnected client not found: {client_id}")
                return

            computer.status = "Offline"
            computer.ping = "-"

            logger.info(f"Client disconnected: {computer.name} ({client_id})")
            QTimer.singleShot(0, self.refresh_table)

        except Exception as e:
            logger.error(f"Error handling disconnection: {e}")

    def disconnect_client(self, computer):
        """Send disconnect command to client"""
        try:
            result = self.server.send_command(
                computer.client_id, "DISCONNECT"
            )
            if result:
                logger.info(f"Disconnect command sent to: {computer.name}")
                self.ui.text_log.append(f"Disconnect command sent to {computer.name}")
            else:
                logger.warning(f"Failed to send disconnect to: {computer.name}")
                QMessageBox.warning(self, "Lỗi", f"Không thể kết nối tới {computer.name}")
        except Exception as e:
            logger.error(f"Error disconnecting client: {e}")
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi ngắt kết nối: {str(e)}")

    def reconnect_client(self, computer):
        """Xử lý khi bấm nút Kết nối lại"""
        computer.is_blocked = False # Gỡ chặn
        self.ui.text_log.append(f"Đã cho phép {computer.name} kết nối lại. Đang đợi...")
        self.signals.client_status_changed.emit()
        # Client đang tự động reconnect mỗi 5s, nên sẽ chui vào ngay lập tức sau thao tác này

    def start_timeout_checker(self):
        """Start timeout checker thread"""
        threading.Thread(
            target=self.timeout_checker_loop,
            daemon=True,
            name="TimeoutChecker"
        ).start()
        logger.info("Timeout checker thread started")

    def timeout_checker_loop(self):
        """Check for client timeouts"""
        while True:
            try:
                current_time = time.time()
                computers = self.computer_manager.get_all_computers()
                updated = False

                for computer in computers:
                    if computer.status == "Offline":
                        continue

                    elapsed = current_time - computer.last_heartbeat

                    if elapsed > TIMEOUT_THRESHOLD:
                        computer.status = "Offline"
                        computer.ping = "-"
                        logger.warning(f"Client timeout: {computer.name} (no heartbeat for {elapsed:.1f}s)")
                        updated = True

                if updated:
                    QTimer.singleShot(0, self.refresh_table)

                time.sleep(TIMEOUT_CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"Error in timeout checker: {e}", exc_info=True)
                time.sleep(TIMEOUT_CHECK_INTERVAL)

    def render_computer_cards(self):
        """Render computer cards for online machines"""
        try:
            layout = self.ui.gridLayout_2
            
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

            computers = self.computer_manager.get_all_computers()
            online_computers = [c for c in computers if c.status == "Online"]

            row = col = 0

            for computer in online_computers:
                card = self.create_card(computer)
                layout.addWidget(card, row, col)

                col += 1
                if col >= 4:
                    col = 0
                    row += 1

            logger.debug(f"Rendered {len(online_computers)} computer cards")

        except Exception as e:
            logger.error(f"Error rendering computer cards: {e}", exc_info=True)

    def create_card(self, computer):
        """Create a computer card widget"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame{
                background-color:#1E293B;
                border-radius:15px;
            }
        """)

        card.setFixedSize(220, 140)
        layout = QtWidgets.QVBoxLayout(card)

        label_name = QLabel(computer.name)
        label_name.setStyleSheet("""
            color:white;
            font-size:18px;
            font-weight:bold;
        """)

        label_ip = QLabel(computer.ip)
        label_ip.setStyleSheet("color:#CBD5E1;")

        label_status = QLabel("● Online")
        label_status.setStyleSheet("color:#22C55E; font-weight:bold;")

        label_ping = QLabel(f"Ping: {computer.ping}")
        label_ping.setStyleSheet("color:#CBD5E1;")

        btn = QPushButton("Điều khiển")
        # open ActivityWindow for this client (page_computers)
        btn.clicked.connect(lambda _, c=computer: self.open_activity_window(c))
        btn.setStyleSheet("""
            QPushButton{
                background-color:#2563EB;
                color:white;
                border:none;
                padding:8px;
                border-radius:10px;
                font-weight: bold;
            }
            QPushButton:hover{
                background-color:#3B82F6;
            }
        """)

        layout.addWidget(label_name)
        layout.addWidget(label_ip)
        layout.addWidget(label_status)
        layout.addWidget(label_ping)
        layout.addStretch()
        layout.addWidget(btn)

        return card

    def open_activity_window(self, computer):
        """Open the ActivityWindow for a client (reuse if already open)."""
        existing = self.open_activity_windows.get(computer.client_id)
        if existing:
            try:
                existing.raise_()
                existing.activateWindow()
            except Exception:
                pass
            return

        w = ActivityWindow(self, computer.client_id, computer.name, self.server)
        self.open_activity_windows[computer.client_id] = w

        def on_close(result=0, cid=computer.client_id):
            try:
                del self.open_activity_windows[cid]
            except KeyError:
                pass

        try:
            w.finished.connect(on_close)
        except Exception:
            try:
                w.destroyed.connect(lambda _: on_close())
            except Exception:
                pass

        w.show()

    def open_monitor(self, computer):
        """Open monitor page for selected computer (kept if needed)"""
        self.selected_computer = computer
        self.switch_page(2, "Điều khiển")
        logger.info(f"Opened monitor for: {computer.name}")

    def update_screen_preview(self, image_data):
        """Update screen preview in monitor page"""
        try:
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)

            self.ui.label_16.setPixmap(
                pixmap.scaled(
                    self.ui.label_16.width(),
                    self.ui.label_16.height(),
                    Qt.KeepAspectRatio
                )
            )
        except Exception as e:
            logger.error(f"Error updating screen preview: {e}")

    def on_screen_frame(self, client_id, frame):
        """Hứng frame từ luồng chạy ngầm Server và bắn tín hiệu sang luồng Main UI"""
        self.signals.frame_received.emit(client_id, frame)

    def update_screen_ui(self, client_id, frame):
        """Luồng Main UI nhận tín hiệu và cập nhật lên Label"""
        try:
            label = self.monitor_labels.get(client_id)

            if not label:
                return

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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

        except Exception as e:
            logger.error(f"Error processing screen frame UI: {e}")

    def render_monitor_cards(self):
        """Render monitor cards"""
        try:
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

            row = col = 0

            for computer in online_computers:
                card, preview_label = self.create_monitor_card(computer)
                self.monitor_labels[computer.client_id] = preview_label
                layout.addWidget(card, row, col)

                col += 1
                if col >= 2:
                    col = 0
                    row += 1

            logger.debug(f"Rendered {len(online_computers)} monitor cards")

        except Exception as e:
            logger.error(f"Error rendering monitor cards: {e}", exc_info=True)

    def create_monitor_card(self, computer):
        """Create monitor card widget"""
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
        preview.setText("Đang tải stream...")

        layout.addWidget(title)
        layout.addWidget(preview)

        return card, preview

    def refresh_clients_list(self):
        """Refresh client list for file transfer"""
        try:
            self.ui.list_clients.clear()

            computers = [
                c for c in self.computer_manager.get_all_computers()
                if c.status == "Online"
            ]

            for computer in computers:
                item = QtWidgets.QListWidgetItem(
                    f"{computer.name} ({computer.ip})"
                )
                item.setData(QtCore.Qt.UserRole, computer.client_id)
                self.ui.list_clients.addItem(item)

            logger.debug(f"Refreshed clients list - {len(computers)} online")

        except Exception as e:
            logger.error(f"Error refreshing clients list: {e}")

    def choose_file(self):
        """Open file dialog to choose file"""
        try:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Chọn file để gửi"
            )

            if not file_path:
                logger.info("File selection cancelled")
                return

            self.selected_file = file_path
            self.ui.line_file_path.setText(file_path)
            logger.info(f"File selected: {file_path}")

        except Exception as e:
            logger.error(f"Error choosing file: {e}")

    def send_selected_file(self):
        """Send selected file to clients"""
        try:
            items = self.ui.list_clients.selectedItems()

            if not items:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn máy nhận file")
                logger.warning("No clients selected for file transfer")
                return

            if not self.selected_file:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn file để gửi")
                logger.warning("No file selected for transfer")
                return

            for item in items:
                client_id = item.data(QtCore.Qt.UserRole)
                
                # Start file transfer in thread
                threading.Thread(
                    target=self._send_file_thread,
                    args=(client_id, item.text()),
                    daemon=True
                ).start()

            logger.info(f"File transfer initiated for {len(items)} client(s)")

        except Exception as e:
            logger.error(f"Error sending file: {e}")
            QMessageBox.critical(self, "Lỗi", f"Lỗi: {str(e)}")

    def _send_file_thread(self, client_id, display_name):
        """Send file in separate thread"""
        try:
            success = self.server.send_file(
                client_id,
                self.selected_file,
                callback=self.on_file_progress_callback
            )

            if success:
                QTimer.singleShot(0, lambda: self.ui.text_log.append(
                    f"✓ Đã gửi file tới {display_name}"
                ))
            else:
                QTimer.singleShot(0, lambda: self.ui.text_log.append(
                    f"✗ Lỗi gửi file tới {display_name}"
                ))

        except Exception as e:
            logger.error(f"Error in file transfer thread: {e}")

    def on_file_progress_callback(self, client_id, filename, progress):
        """Callback for file transfer progress"""
        self.file_signals.progress.emit(client_id, filename, progress)

    def on_file_progress(self, client_id, filename, progress):
        """Update file transfer progress"""
        try:
            # Log progress periodically
            if int(progress) % 25 == 0:
                logger.debug(f"File transfer progress - {filename}: {progress:.1f}%")

        except Exception as e:
            logger.error(f"Error updating file progress: {e}")

    def request_files_from_clients(self):
        """Request files from selected clients"""
        try:
            items = self.ui.list_clients.selectedItems()

            if not items:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn máy để lấy file")
                logger.warning("No clients selected for file request")
                return

            for item in items:
                client_id = item.data(QtCore.Qt.UserRole)
                self.server.send_command(client_id, "GET_FILES")
                self.ui.text_log.append(f"Đang lấy file từ {item.text()}")
                logger.info(f"File request sent to: {item.text()}")

        except Exception as e:
            logger.error(f"Error requesting files: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    logger.info("Application started")
    sys.exit(app.exec_())
