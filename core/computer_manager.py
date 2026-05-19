# -*- coding: utf-8 -*-
"""
Computer Manager - Quản lý danh sách máy tính
Fixes:
- Fixed remove_computer_by_ip() bug (using list comprehension instead of remove in loop)
- Added better error handling
- Added logging
- ĐÃ TỐI ƯU: Thêm cơ chế RLock bảo vệ đa luồng chống xung đột dữ liệu (Thread-Safe) cho >20 máy trạm.
"""

import threading  # THÊM DÒNG NÀY: Thư viện quản lý đa luồng
from models.computer import Computer
from utils.logger import LoggerSetup

logger = LoggerSetup.get_logger(__name__)


class ComputerManager:
    """
    Manages the list of connected computers with thread safety
    """

    def __init__(self):
        self.computers = []
        # SỬ DỤNG RLock (Reentrant Lock) để tránh hiện tượng Deadlock khi các hàm gọi lẫn nhau
        self.lock = threading.RLock() 
        logger.info("ComputerManager initialized")

    def load_demo_data(self):
        """
        Load demo data for testing
        """
        with self.lock:  # Đảm bảo an toàn khi ghi đè danh sách
            self.computers = [
                Computer(
                    "demo-1",
                    "PC-01",
                    "192.168.1.10",
                    "Online",
                    "2ms"
                ),
                Computer(
                    "demo-2",
                    "PC-02",
                    "192.168.1.11",
                    "Offline",
                    "-"
                ),
                Computer(
                    "demo-3",
                    "PC-03",
                    "192.168.1.12",
                    "Online",
                    "5ms"
                )
            ]
        logger.info(f"Demo data loaded with {len(self.computers)} computers")

    def get_all_computers(self):
        """
        Get all computers
        
        Returns:
            list: Bản sao dữ liệu danh sách máy tính (Tránh lỗi luồng khác sửa đổi khi UI đang vẽ lại)
        """
        with self.lock:
            return list(self.computers)  # Trả về bản sao dạng list() để luồng khác không can thiệp trực tiếp vào mảng gốc

    def add_computer(self, computer):
        """
        Add a new computer to the list
        """
        if not isinstance(computer, Computer):
            logger.error(f"Invalid computer object: {computer}")
            return False
        
        with self.lock:  # Khóa bảo vệ tiến trình kiểm tra và thêm máy
            # Check if computer already exists
            if self.find_computer_by_ip(computer.ip):
                logger.warning(f"Computer with IP {computer.ip} already exists")
                return False
            
            self.computers.append(computer)
            logger.info(f"Computer added: {computer.name} ({computer.ip})")
            return True

    def remove_computer_by_ip(self, ip):
        """
        Remove a computer by IP address
        """
        if not ip:
            logger.error("IP address cannot be empty")
            return False
        
        with self.lock:  # Khóa bảo vệ khi cập nhật lại mảng
            initial_count = len(self.computers)
            
            # Use list comprehension to filter out the computer
            self.computers = [c for c in self.computers if c.ip != ip]
            
            if len(self.computers) < initial_count:
                logger.info(f"Computer removed: IP {ip}")
                return True
            else:
                logger.warning(f"Computer not found: IP {ip}")
                return False

    def remove_computer_by_id(self, client_id):
        """
        Remove a computer by client ID
        """
        if not client_id:
            logger.error("Client ID cannot be empty")
            return False
        
        with self.lock:  # Khóa bảo vệ khi xóa máy theo ID
            initial_count = len(self.computers)
            
            # Use list comprehension
            self.computers = [c for c in self.computers if c.client_id != client_id]
            
            if len(self.computers) < initial_count:
                logger.info(f"Computer removed by ID: {client_id}")
                return True
            else:
                logger.warning(f"Computer not found by ID: {client_id}")
                return False

    def find_computer_by_ip(self, ip):
        """
        Find a computer by IP address
        """
        if not ip:
            logger.error("IP address cannot be empty")
            return None
        
        with self.lock:  # Khóa bảo vệ khi duyệt mảng tìm kiếm
            for computer in self.computers:
                if computer.ip == ip:
                    logger.debug(f"Computer found by IP: {ip}")
                    return computer
            
            logger.debug(f"Computer not found by IP: {ip}")
            return None

    def find_computer_by_name(self, name):
        """
        Find a computer by name
        """
        if not name:
            logger.error("Computer name cannot be empty")
            return None
        
        with self.lock:  # Khóa bảo vệ khi tìm kiếm theo tên
            for computer in self.computers:
                if computer.name.lower() == name.lower():
                    logger.debug(f"Computer found by name: {name}")
                    return computer
            
            logger.debug(f"Computer not found by name: {name}")
            return None

    def update_status(self, ip, status):
        """
        Update computer status by IP
        """
        if not ip or not status:
            logger.error("IP and status cannot be empty")
            return False
        
        with self.lock:  # Khóa bảo vệ toàn bộ tiến trình tìm kiếm và cập nhật trạng thái
            computer = self.find_computer_by_ip(ip)
            
            if computer:
                old_status = computer.status
                computer.status = status
                logger.info(f"Computer status updated: {ip} - {old_status} -> {status}")
                return True
            
            logger.warning(f"Computer not found for status update: {ip}")
            return False

    def get_computer_by_id(self, client_id):
        """
        Get computer by client ID
        """
        if not client_id:
            logger.error("Client ID cannot be empty")
            return None
        
        with self.lock:  # Khóa bảo vệ tìm kiếm theo ID
            for computer in self.computers:
                if computer.client_id == client_id:
                    logger.debug(f"Computer found by ID: {client_id}")
                    return computer
            
            logger.debug(f"Computer not found by ID: {client_id}")
            return None

    def get_online_computers(self):
        """
        Get list of online computers
        """
        with self.lock:  # Khóa bảo vệ khi thực hiện lọc phần tử mảng
            online = [c for c in self.computers if c.status == "Online"]
            logger.debug(f"Found {len(online)} online computers")
            return online

    def get_offline_computers(self):
        """
        Get list of offline computers
        """
        with self.lock:  # Khóa bảo vệ khi lọc máy offline
            offline = [c for c in self.computers if c.status == "Offline"]
            logger.debug(f"Found {len(offline)} offline computers")
            return offline

    def get_total_count(self):
        """Get total number of computers"""
        with self.lock:
            return len(self.computers)

    def get_online_count(self):
        """Get count of online computers"""
        with self.lock:
            return len(self.get_online_computers())

    def get_offline_count(self):
        """Get count of offline computers"""
        with self.lock:
            return len(self.get_offline_computers())

    def clear_all(self):
        """
        Clear all computers from the list
        """
        with self.lock:  # Khóa bảo vệ tuyệt đối khi dọn sạch dữ liệu mảng
            count = len(self.computers)
            self.computers.clear()
            logger.warning(f"All {count} computers cleared from manager")