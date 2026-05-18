# 💻 Phần Mềm Quản Lý Phòng Máy Tính

Ứng dụng Desktop quản lý phòng tin học với các tính năng monitoring, điều khiển từ xa và truyền file.

## 📋 Tính Năng

- 🏠 **Dashboard** - Hiển thị tổng quan máy online/offline
- 🖥️ **Máy Tính** - Danh sách các máy client đang kết nối
- 🎮 **Điều Khiển** - Xem màn hình live, tắt máy từ xa
- 📁 **File Transfer** - Gửi/nhận file giữa server và client
- 📊 **Real-time Monitoring** - Theo dõi trạng thái máy theo thời gian thực
- 💗 **Heartbeat Detection** - Tự động phát hiện máy offline

## 🛠️ Công Nghệ

- **Frontend:** PyQt5
- **Backend:** Python Socket, Threading
- **Image Processing:** OpenCV, PIL
- **Screen Capture:** MSS

## 📦 Yêu Cầu Hệ Thống

- Python 3.8+
- Windows 10/11 (hoặc Linux/macOS với điều chỉnh)
- 100MB RAM tối thiểu

## 🚀 Cài Đặt

1. **Clone repository:**
```bash
git clone https://github.com/NgTrongTuan09/computer-room-management.git
cd computer-room-management
```

2. **Tạo Virtual Environment:**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

3. **Cài đặt Dependencies:**
```bash
pip install -r requirements.txt
```

## 🏃 Chạy Ứng Dụng

### Server (Quản Lý)
```bash
python main.py
```

### Client (Máy Tính Trong Phòng)
```bash
python client_main.py
```

## 📁 Cấu Trúc Project

```
computer-room-management/
├── models/
│   └── computer.py           # Model lớp Computer
├── core/
│   └── computer_manager.py   # Quản lý danh sách máy
├── ui/
│   └── ui_main1.py          # Giao diện PyQt5
├── network/
│   ├── server.py            # Socket Server
│   └── client.py            # Socket Client
├── main.py                  # Server GUI
├── client_main.py           # Client entry point
├── requirements.txt         # Dependencies
├── .gitignore              # Git ignore file
└── README.md               # Hướng dẫn (file này)
```

## 🔧 Cấu Hình

### Server
- **Host:** `0.0.0.0` (lắng nghe tất cả interface)
- **Port 5000:** Giao tiếp chính (lệnh, info)
- **Port 5001:** Stream màn hình
- **Port 5002:** Truyền file

### Client
- Sửa địa chỉ server trong `client_main.py`:
```python
client = SocketClient("192.168.1.100")  # Thay IP của server
```

## 🐛 Troubleshooting

| Lỗi | Giải Pháp |
|-----|----------|
| ConnectionRefusedError | Kiểm tra server đã chạy, firewall settings |
| Permission Denied (file) | Chạy với quyền admin |
| Virtual drive không tạo được | Chỉ hoạt động trên Windows, chạy admin |

## 📝 Changelog

### v1.0 (Hiện tại)
- ✅ Kết nối Client-Server
- ✅ Heartbeat mechanism
- ✅ Screen streaming
- ✅ File transfer
- 🔄 Đang cải thiện: bugs fixes, optimization

## 🤝 Đóng Góp

Mọi pull request, issue, suggestion đều được chào đón!

## 📄 License

MIT License - Tự do sử dụng, sửa đổi

## 👨‍💻 Tác Giả

**Nguyễn Trọng Tuân** - [@NgTrongTuan09](https://github.com/NgTrongTuan09)

---

**Last Updated:** 2026-05-18
