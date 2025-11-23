name: convey
pass: convey12
wifi: convey
pass: convey12

## 🐍 1. Tạo môi trường ảo (virtualenv)

**Bước 1 – Cài venv (nếu chưa có)**

```bash
sudo apt update
sudo apt install python3-venv
```

**Bước 2 – Tạo môi trường ảo trong thư mục project**
(Ví dụ bạn đang ở: `~/Desktop/SMARTFACTORY`)

```bash
python3 -m venv env
```

**Bước 3 – Kích hoạt môi trường ảo**

```bash
source env/bin/activate
```

Thấy đầu dòng có `(env)` là OK.

**Bước 4 – Cài numpy, scipy, OpenBLAS… ở hệ thống**

```bash
sudo apt update
sudo apt install -y python3-numpy python3-scipy python3-dev libopenblas-dev liblapack-dev gfortran
```

**Bước 5 – Cài thư viện vào venv**

```bash
pip install -r requirements.txt
# hoặc từng cái
# pip install <tên-package>
```

**Bước 6 – Thoát môi trường ảo khi không dùng nữa**

```bash
deactivate
```

---

## ⚙️ 2. Tạo service tự chạy khi khởi động (systemd)

Giả sử:

- User: `convey`
- Project: `/home/convey/Desktop/SMARTFACTORY`
- Venv: `/home/convey/Desktop/SMARTFACTORY/env`
- App Flask/Gunicorn: `app:app` (tập tin `app.py`, biến Flask tên `app`)

### Bước 1 – Tạo file service

```bash
sudo nano /etc/systemd/system/smartfactory.service
```

Dán nội dung (nhớ sửa đường dẫn/user nếu khác):

```ini
[Unit]
Description=SMARTFACTORY Flask Service
After=network.target

[Service]
User=convey
WorkingDirectory=/home/convey/Desktop/SMARTFACTORY
Environment="PATH=/home/convey/Desktop/SMARTFACTORY/env/bin"
ExecStart=/home/convey/Desktop/SMARTFACTORY/env/bin/gunicorn -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Lưu & thoát: `Ctrl + O`, Enter, rồi `Ctrl + X`.

### Bước 2 – Load service + bật chạy cùng hệ thống

```bash
sudo systemctl daemon-reload
sudo systemctl enable smartfactory.service
sudo systemctl start smartfactory.service
```

---

## 📋 3. Cách xem log service

**Xem log mới nhất:**

```bash
sudo journalctl -u smartfactory.service
```

**Xem log realtime (theo dõi liên tục):**

```bash
sudo journalctl -u smartfactory.service -f
```

**Xem trạng thái service:**

```bash
sudo systemctl status smartfactory.service
```

Nếu app của bạn không phải `app:app` (ví dụ `main:app` hay tên khác), gửi mình tên file + biến Flask, mình chỉnh lại dòng `ExecStart` cho chuẩn luôn 👍
