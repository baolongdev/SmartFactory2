# Hướng dẫn mở rộng SmartFactory

## 1. Thêm API mới (ví dụ: /api/system)

1. Tạo file `app/api/api_system.py`:

   - Định nghĩa `api_system = Blueprint("system", __name__, url_prefix="/api/system")`
   - Viết các route: `/status`, `/reboot`, v.v.

2. Thêm vào `app/api/__init__.py`:

   ```python
   from .api_camera import api_camera
   from .api_mqtt import api_mqtt
   from .api_system import api_system

   __all__ = ["api_camera", "api_mqtt", "api_system"]
   ```
