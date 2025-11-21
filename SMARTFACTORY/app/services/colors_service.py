import threading
import json
from app.core.config.color_config import ColorConfig


class ColorsService:
    """Singleton quản lý load/save màu từ colors.json."""

    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            with cls._instance_lock:
                if not hasattr(cls, "_instance"):
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self.cfg = ColorConfig()        # đã tự fill missing fields
        self.path = self.cfg.path
        self.colors = self.cfg.colors   # list dict đã có lower/upper/bgr
        self._initialized = True

    # ------------------------------------------------------
    # Public API
    # ------------------------------------------------------
    def get_colors(self):
        return self.colors

    def update_colors(self, data: list):
        """Cập nhật colors.json + reload memory với fill_missing_fields."""
        # Dùng save() của ColorConfig để vừa ghi file vừa fill
        self.cfg.save(data)
        self.colors = self.cfg.colors
        return True


# Singleton instance
colors_service = ColorsService()
