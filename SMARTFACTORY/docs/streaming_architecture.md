# Streaming Architecture — SmartFactory2

## Mục đích tài liệu

Tài liệu này mô tả chính xác cách hệ thống stream video từ camera USB/RTSP/MJPEG
lên trình duyệt web, những điểm nghẽn hiện tại, và hướng cải thiện để stream mượt
trên Raspberry Pi 4.

---

## 1. Luồng dữ liệu hiện tại (end-to-end)

```
USB Camera (30 FPS)
    │
    ▼
[THREAD 1] CameraReader._update_loop()
    cap.grab()      ← luôn drain buffer, giữ frame mới nhất
    cap.retrieve()  ← lấy frame ra numpy array (BGR)
    └─ self.frame   (protected by CameraReader.lock)
    │
    ▼
[THREAD 2] pipeline._detection_loop()          rate: max_detection_fps=20
    camera.read()          ← copy frame từ Thread 1
    detector.detect()      ← HSV mask + morphology + findContours
    tracker.update()       ← centroid matching, assign IDs
    └─ _pending            (protected by _pending_lock)
    │
    ▼
[THREAD 3] pipeline._encode_loop()             rate: unlimited (as fast as possible)
    drawer.render()        ← vẽ bounding box + label + trajectory lên frame
    cv2.imencode(".jpg",   ← encode JPEG quality=72
        frame, [72])
    └─ self._jpeg          (protected by frame_lock)
    │
    ▼
[FLASK GENERATOR] camera_service.stream()
    get_frame_bytes()      ← đọc self._jpeg
    yield b"--frame\r\n"   ← MJPEG multipart boundary
          b"Content-Type: image/jpeg\r\n\r\n"
          + frame_bytes
          + b"\r\n"
    │
    ▼
GET /api/camera/stream
    Response(stream_generator,
             mimetype="multipart/x-mixed-replace; boundary=frame")
    Headers: Cache-Control: no-cache, Connection: close
    │
    ▼
Browser: <img id="video-stream" src="/api/camera/stream">
    ← native MJPEG decoding, auto-refresh frame on each boundary
```

---

## 2. Kiến trúc 3 thread

| Thread | Tên | Công việc | Tốc độ (Pi 4) |
|--------|-----|-----------|---------------|
| 1 | `sf-capture` (CameraReader) | grab/retrieve từ USB | 30 FPS |
| 2 | `sf-detect` (detection_loop) | HSV detect + track | ≤20 FPS (rate-limited) |
| 3 | `sf-encode` (encode_loop) | draw + JPEG encode | ~15–22 FPS (ARM bottleneck) |

Thread 2 và Thread 3 chạy **song song** vì OpenCV giải phóng GIL khi thực hiện
C-level operations (`imencode`, `cvtColor`, `morphologyEx`). Tốc độ cuối cùng
browser nhận được bị giới hạn bởi Thread 3 (encode chậm hơn detect).

**FPS đo bằng EMA (α=0.1):**
- `_det_fps` — throughput Thread 2 (được đo sau khi detect xong)
- `_enc_fps` — throughput Thread 3 (hiển thị trong HUD)
- `GET /api/camera/status` → `{"det_fps": 18.3, "enc_fps": 15.7}`

---

## 3. Điểm nghẽn hiện tại trên Pi 4

### 3.1 JPEG encode (Thread 3) — bottleneck chính
`cv2.imencode(".jpg", frame, [quality=72])` trên ARM Cortex-A72 @ 1.8 GHz:
- 640×480 quality=72 → ~35–55 ms/frame → tối đa ~18–28 FPS
- Không có hardware JPEG encoder trên Pi 4 (không dùng được V4L2 JPEG offload)

### 3.2 Flask streaming generator — không có sleep
`camera_service.stream()` chạy vòng lặp `while self.running` không có sleep.
Khi `get_frame_bytes()` trả về cùng frame cũ (chưa có frame mới), generator
vẫn yield lại frame đó ngay lập tức → gửi duplicate frames + waste network.

```python
# Hiện tại (camera_service.py:257-268)
while self.running:
    frame_bytes = self.get_frame_bytes()
    if not frame_bytes:
        time.sleep(0.01)
        continue
    yield (...)       # ← yield ngay dù frame có thể là frame cũ
```

### 3.3 Gunicorn worker type — quan trọng nhất
MJPEG stream là **long-lived HTTP connection**. Với Gunicorn worker mặc định
(sync), mỗi worker process bị block bởi 1 stream connection. Nếu có 4 workers
và 4 browser tab mở stream → hết worker, các request khác bị treo.

**Phải dùng async worker** (`gevent` hoặc `eventlet`) để 1 worker xử lý
nhiều concurrent stream.

### 3.4 DrawManager — không cần thiết mỗi frame
`drawer.render()` vẽ trajectory + label + HUD ngay cả khi không có object nào.
Trên Pi 4: ~10–15 ms. Có thể skip bước này nếu không có detection.

---

## 4. Cấu hình hiện tại

**`config/config_camera.json`:**
```json
{
    "camera":    { "src": 0, "width": 640, "height": 480, "fps": 30 },
    "detection": { "min_contour_area": 1500, "max_detection_fps": 20, "max_objects": 1 },
    "tracker":   { "max_lost": 2.0, "max_history": 30, "match_dist": 80 },
    "drawing":   { "show_fps": true, "overlay_alpha": 0.25, "trajectory_ttl": 3.0 }
}
```

**`.env`:**
```
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
UART_PORT=/dev/ttyACM0
UART_BAUDRATE=115200
```

---

## 5. Hướng cải thiện để stream mượt hơn

### 5.1 [Quan trọng nhất] Chạy Gunicorn với gevent worker

```bash
# Thay vì: python run.py
gunicorn -b 0.0.0.0:5000 -w 2 -k gevent --worker-connections 100 wsgi:app
```

Lý do: `gevent` dùng coroutine — 1 worker giữ nhiều stream connection đồng thời,
không block. Với Pi 4, `w 2` là đủ (2 worker process × nhiều coroutine mỗi worker).

### 5.2 Fix stream generator: chỉ yield khi có frame mới

**File:** `app/services/camera_service.py` → `stream()`

```python
# Thêm tracking frame cũ để tránh gửi duplicate
def stream(self):
    last_frame = None
    try:
        while self.running:
            frame_bytes = self.get_frame_bytes()
            if not frame_bytes or frame_bytes is last_frame:
                time.sleep(0.005)   # 5ms poll
                continue
            last_frame = frame_bytes
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                frame_bytes +
                b"\r\n"
            )
    except GeneratorExit:
        ...
```

### 5.3 Giảm resolution detect, giữ resolution stream

Tách resolution: stream 640×480 đẹp, detect trên 320×240 nhanh.
Hiện tại `ColorDetector` đã downscale nội bộ xuống `_MAX_DETECT_W=320`
trước khi detect → detect đã tối ưu. Không cần thay đổi.

### 5.4 Giới hạn FPS stream (tuỳ chọn)

Nếu mạng WiFi yếu hoặc muốn giảm tải Pi, thêm sleep vào generator:

```python
# 15 FPS stream
time.sleep(1/15)
```

### 5.5 [Tùy chọn nâng cao] WebRTC thay MJPEG

MJPEG không có adaptive bitrate, không có P-frame compression.
Với aiortc (Python WebRTC library), có thể stream H.264 — nhỏ hơn 5–10×,
độ trễ thấp hơn. Nhưng phức tạp hơn đáng kể và cần browser ICE negotiation.
**Không nên** cho project này ở giai đoạn hiện tại.

---

## 6. Lệnh chạy production được khuyên dùng (Pi 4)

```bash
# Cài gevent nếu chưa có
pip install gevent

# Chạy server
gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --worker-class gevent \
  --worker-connections 50 \
  --timeout 120 \
  --keep-alive 5 \
  wsgi:app
```

Hoặc tạo file `gunicorn.conf.py`:

```python
bind             = "0.0.0.0:5000"
workers          = 2
worker_class     = "gevent"
worker_connections = 50
timeout          = 120
keepalive        = 5
accesslog        = "-"
errorlog         = "-"
loglevel         = "info"
```

Rồi chạy: `gunicorn -c gunicorn.conf.py wsgi:app`

---

## 7. Tóm tắt các file liên quan đến stream

| File | Vai trò |
|------|---------|
| `app/core/camera/camera_reader.py` | Thread 1: capture USB/RTSP frame |
| `app/core/camera/mjpeg_reader.py` | Thread 1 (MJPEG-HTTP): parse JPEG từ HTTP stream |
| `app/core/camera/color_detector.py` | Detect màu HSV + MORPH_OPEN/CLOSE |
| `app/core/camera/tracker.py` | Gán tracker_id, coast, trim(max_objects) |
| `app/core/camera/draw_manager.py` | Vẽ bounding box + label + trajectory + HUD |
| `app/core/camera/pipeline.py` | Điều phối 3 thread, lưu _jpeg atomic |
| `app/services/camera_service.py` | Facade: start/stop/stream/get_detections |
| `app/api/api_camera.py` | Endpoints: /start /stop /stream /detections /status |
| `app/static/js/camera_control.js` | Frontend: gọi API start/stop, set img.src |
| `app/static/js/ui_camera.js` | Frontend: flip/rotate transform trên img |
| `config/config_camera.json` | Cấu hình camera, detection, tracker, drawing |
| `wsgi.py` | Entry point cho Gunicorn |
| `requirements.txt` | gunicorn, gevent, opencv-python-headless |
