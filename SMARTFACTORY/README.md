# SmartFactory2 - IoT Smart Conveyor System

Hệ thống băng tải thông minh tích hợp thị giác máy tính và MQTT, dùng để phát hiện vật thể theo màu sắc và điều khiển băng tải ESP32.

## Công nghệ sử dụng
- **Backend**: Flask 3.0+, Python 3.8+
- **Computer Vision**: OpenCV 4.8+, NumPy, SciPy
- **IoT Communication**: MQTT (paho-mqtt)
- **Deployment**: Gunicorn (production), Virtualenv

## Cấu trúc dự án
```
SMARTFACTORY/
├── run.py                  # Development entry point
├── wsgi.py                # Production WSGI entry
├── config/                # JSON config files
│   ├── config_app.json    # Main app config
│   ├── config_camera.json # Camera settings
│   ├── config_mqtt.json   # MQTT settings
│   └── colors.json        # Color detection config
├── app/
│   ├── api/               # API routes (camera, mqtt, colors, wifi)
│   ├── services/          # Business logic services
│   ├── core/              # Core processing (camera pipeline, config)
│   ├── templates/         # HTML templates
│   └── static/            # CSS/JS assets
└── requirements.txt       # Python dependencies
```

## Hướng dẫn cài đặt

### 1. Yêu cầu môi trường
- Python 3.8 trở lên
- pip, virtualenv
- (Tùy chọn) Raspberry Pi cho deployment thực tế

### 2. Cài đặt
```bash
# Clone repository
git clone <repo-url>
cd SmartFactory2/SMARTFACTORY

# Tạo virtual environment
python -m venv venv

# Kích hoạt (Windows)
venv\Scripts\activate
# Kích hoạt (Linux/RPi)
source venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt
```

### 3. Cấu hình
Chỉnh sửa các file trong thư mục `config/`:
- `config_app.json`: Cấu hình chính
- `config_camera.json`: Nguồn camera, thông số phát hiện
- `config_mqtt.json`: MQTT broker, topics
- `colors.json`: Danh sách màu cần phát hiện

Tạo file `.env` từ `.env.example` (nếu có) để cấu hình biến môi trường:
```
FLASK_ENV=development
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
MQTT_SERVER=mqtt.ohstem.vn
API_KEY=your_secret_key_here  # Tùy chọn, để bảo mật API
```

### 4. Chạy ứng dụng
```bash
# Development mode
python run.py

# Production mode (Gunicorn)
gunicorn -b 0.0.0.0:5000 wsgi:app
```

Truy cập: http://localhost:5000

## API Documentation

### Camera APIs
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/api/camera/start` | POST | Khởi động camera pipeline |
| `/api/camera/stop` | POST | Dừng camera |
| `/api/camera/status` | GET | Trạng thái camera |
| `/api/camera/stream` | GET | MJPEG video stream |
| `/api/camera/detections` | GET | Danh sách vật thể phát hiện |
| `/api/camera/list` | GET | Danh sách camera khả dụng |

### MQTT APIs
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/api/mqtt/publish` | POST | Gửi tin nhắn MQTT (yêu cầu API key) |
| `/api/mqtt/status` | GET | Trạng thái kết nối MQTT |
| `/api/mqtt/messages` | GET | Tin nhắn cuối cùng của topic |

### Color APIs
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/api/colors/` | GET | Lấy danh sách màu cấu hình |
| `/api/colors/` | POST | Cập nhật màu (yêu cầu API key) |

### WiFi APIs
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/api/wifi/scan` | GET | Quét mạng WiFi xung quanh |
| `/api/wifi/status` | GET | Trạng thái kết nối WiFi |
| `/api/wifi/connect` | POST | Kết nối WiFi (yêu cầu API key) |

### Bảo mật API
Nếu biến môi trường `API_KEY` được cấu hình, các endpoint nhạy cảm (publish MQTT, update colors, connect WiFi) yêu cầu header:
```
X-API-Key: your_secret_key_here
```

## Deployment trên Raspberry Pi
1. Cài đặt Raspberry Pi OS Lite
2. Cài đặt dependencies: `sudo apt install python3-venv python3-pip`
3. Copy dự án vào RPi
4. Cấu hình `config_camera.json` với source camera phù hợp
5. Chạy với Gunicorn: `gunicorn -b 0.0.0.0:5000 wsgi:app`

## Đóng góp
Mọi đóng góp vui lòng gửi pull request hoặc báo issue tại repository.

## Logging

SmartFactory2 sử dụng **structlog** để cung cấp structured logging chuyên nghiệp.

### Cấu hình

Sử dụng các biến môi trường sau:

| Biến | Mô tả | Mặc định |
|------|--------|---------|
| `LOG_LEVEL` | Mức log (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO` |
| `LOG_FORMAT` | Định dạng log: `json` hoặc `console` | `console` |
| `ENVIRONMENT` | Môi trường: `development`, `staging`, `production` | `development` |
| `SERVICE_NAME` | Tên dịch vụ | `SmartFactory2` |

### Development vs Production

**Development (console format):**
- Log có màu sắc, dễ đọc
- Hiển thị module, function, line number
- Phù hợp cho debug

**Production (JSON format):**
- Log dạng JSON, dễ parse bằng log aggregation tools
- Có timestamp ISO format
- Bao gồm request_id, user_id (nếu có)
- Phù hợp cho ELK, Splunk, Datadog, etc.

### Cách sử dụng trong code

```python
import structlog

logger = structlog.get_logger(__name__)

# Log event với structured fields
logger.info("user_login", user_id=123, email="user@example.com")

# Log exception
try:
    risky_operation()
except Exception as e:
    logger.exception("operation_failed", error_type=type(e).__name__)
```

### Request Context

Trong môi trường web, các thông tin sau được tự động gắn vào mọi log:
- `request_id`: Unique ID cho mỗi request (từ header `X-Request-ID` hoặc tự sinh)
- `method`: HTTP method
- `path`: Request path
- `client_ip`: IP của client
- `user_agent`: User agent string

### Bảo mật

Tự động redact các sensitive fields:
- `password`, `token`, `access_token`, `refresh_token`
- `authorization`, `cookie`, `secret`, `api_key`
- `private_key`, `credit_card`, `ssn`

Ví dụ: `logger.info("auth", password="secret")` sẽ log `"password": "***REDACTED***"`

### Log Levels

- **debug**: Chi tiết phát triển/debug
- **info**: Sự kiện bình thường của hệ thống
- **warning**: Vấn đề bất thường nhưng có thể khôi phục
- **error**: Thao tác thất bại cần chú ý
- **exception**: Lỗi với traceback (trong except blocks)
- **critical**: Lỗi nghiêm trọng hệ thống

### Event Naming Convention

Sử dụng snake_case, ngắn gọn, mô tả hành động:
- `app_started`, `app_stopping`
- `request_started`, `request_finished`, `request_failed`
- `camera_started`, `camera_stopped`, `camera_failed_to_open`
- `mqtt_connected`, `mqtt_disconnected`, `mqtt_published`
- `wifi_scan_completed`, `wifi_connected`

### Ví dụ log output

**Console format (development):**
```
2026-05-04 18:05:23 [info    ] request_started       method=GET path=/api/camera/status request_id=abc-123
2026-05-04 18:05:23 [info    ] camera_status_api_called connected=True detected=3 tracked=3 request_id=abc-123
```

**JSON format (production):**
```json
{"timestamp": "2026-05-04T18:05:23Z", "level": "info", "logger": "app.api.api_camera", "event": "request_started", "request_id": "abc-123", "method": "GET", "path": "/api/camera/status", "service": "SmartFactory2", "environment": "production"}
```
