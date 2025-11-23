Hệ thống: Raspberry Pi OS Trixie
Python: 3.11 (tự build)
User: convey
Pass: convey12

chmod +x run_setup.sh
./run_setup.sh

---

Dưới đây là nội dung file **README.md** / **Hướng dẫn.md** theo đúng yêu cầu — được trình bày đẹp, rõ ràng và **tương thích Python 3.11 trên Raspberry Pi OS**.

---

# 📘 SMARTFACTORY – Hướng dẫn cài đặt Python 3.11 + Virtualenv + Service

---

## 🧩 **1. Tạo môi trường Python 3.11**

Sau khi bạn đã build Python 3.11 từ source và có:

```
/usr/local/bin/python3.11
```

### **Bước 1 – Tạo virtual environment trong thư mục project**

```bash
cd ~/Desktop/SMARTFACTORY
python3.11 -m venv env
```

### **Bước 2 – Kích hoạt môi trường ảo**

```bash
source env/bin/activate
```

### **Bước 3 – Cài các gói cần thiết trong hệ thống**

```bash
sudo apt update
sudo apt install -y libopenblas-dev liblapack-dev gfortran python3-dev
```

⚠ Lưu ý: KHÔNG cài numpy/scipy hệ thống (`python3-numpy`, `python3-scipy`) vì chúng thuộc Python 3.13 → xung đột với Python 3.11.

### **Bước 4 – Cài thư viện vào venv Python 3.11**

```bash
pip install --upgrade pip setuptools wheel
pip install --extra-index-url https://www.piwheels.org/simple -r requirements.txt

```

Nếu cần OpenCV cho Raspberry Pi:

```bash
pip install --extra-index-url https://www.piwheels.org/simple opencv-python-headless==4.8.1.78
```

### **Bước 5 – Thoát môi trường ảo nếu cần**

```bash
deactivate
```

---

## ⚙️ **2. Tạo service tự chạy bằng systemd (Flask + Gunicorn)**

Giả sử:

- User: `convey`
- Project: `/home/convey/Desktop/SMARTFACTORY`
- Virtualenv: `/home/convey/Desktop/SMARTFACTORY/env`
- File Flask: `app.py`
- Biến Flask: `app`

### **Bước 1 – Tạo file service**

```bash
sudo nano /etc/systemd/system/smartfactory.service
```

### **Nội dung service**

```ini
[Unit]
Description=SMARTFACTORY Flask Service (Python 3.11)
After=network.target

[Service]
User=convey
WorkingDirectory=/home/convey/Desktop/SMARTFACTORY

# Virtual environment Python 3.11
Environment="PATH=/home/convey/Desktop/SMARTFACTORY/env/bin"

# Gunicorn chạy Flask app
ExecStart=/home/convey/Desktop/SMARTFACTORY/env/bin/gunicorn -b 0.0.0.0:5000 app:app

Restart=always

[Install]
WantedBy=multi-user.target
```

Lưu: **Ctrl + O**
Thoát: **Ctrl + X**

---

## 🚀 **3. Khởi động service**

```bash
sudo systemctl daemon-reload
sudo systemctl enable smartfactory.service
sudo systemctl start smartfactory.service
```

---

## 📄 **4. Kiểm tra service**

**Trạng thái:**

```bash
sudo systemctl status smartfactory.service
```

**Xem log realtime:**

```bash
sudo journalctl -u smartfactory.service -f
```

---

# 📝 **5. Ghi chú**

- Không thay thế `python3` mặc định của hệ thống (Python 3.13) → có thể làm lỗi Raspberry Pi OS.
- Python 3.11 chỉ dùng qua virtualenv hoặc gọi trực tiếp `python3.11`.
- Service luôn chạy Python 3.11 vì đã gán PATH trong file `.service`.
