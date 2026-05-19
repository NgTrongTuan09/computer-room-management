# Activity Window - UI dialog to show client activity and control actions
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout, QMessageBox
from PyQt5.QtCore import Qt, QTimer
import time
from utils.activity_db import get_activities

class ActivityWindow(QDialog):
    def __init__(self, parent, client_id, client_name, server_ref):
        super().__init__(parent)
        self.client_id = client_id
        self.client_name = client_name
        self.server = server_ref
        self.setWindowTitle(f"Hoạt động - {client_name}")
        self.setMinimumSize(700, 500)
        # styling similar to main ui
        self.setStyleSheet('background-color:#0F172A; color:white;')
        layout = QVBoxLayout(self)
        header = QLabel(f"Hoạt động của {client_name} ({client_id})")
        header.setStyleSheet("font-weight:bold; font-size:16px; color:white; padding:8px;")
        layout.addWidget(header)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("background-color:#1F2937; color:white; border-radius:8px;")
        layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("⟳ Refresh")
        self.btn_restart = QPushButton("🔄 Khởi động lại")
        self.btn_shutdown = QPushButton("⛔ Tắt máy")
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_restart)
        btn_layout.addWidget(self.btn_shutdown)
        layout.addLayout(btn_layout)
        self.btn_refresh.clicked.connect(self.reload_history)
        self.btn_shutdown.clicked.connect(self.confirm_shutdown)
        self.btn_restart.clicked.connect(self.confirm_restart)
        self.reload_history()

    def reload_history(self):
        self.list_widget.clear()
        rows = get_activities(self.client_id, limit=500)
        for r in rows:
            t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"]))
            text = f"[{t}] {r['type'].upper()} - {r['name']}"
            if r.get("url"):
                text += f" ({r['url']})"
            self.list_widget.addItem(text)

    def confirm_shutdown(self):
        ans = QMessageBox.question(self, "Xác nhận", "Bạn có chắc muốn TẮT máy client này?", QMessageBox.Yes|QMessageBox.No)
        if ans == QMessageBox.Yes:
            self.server.send_command(self.client_id, "CMD|SHUTDOWN")

    def confirm_restart(self):
        ans = QMessageBox.question(self, "Xác nhận", "Bạn có chắc muốn KHỞI ĐỘNG LẠI client này?", QMessageBox.Yes|QMessageBox.No)
        if ans == QMessageBox.Yes:
            self.server.send_command(self.client_id, "CMD|RESTART")
