# app/core/config/loader.py
import os
import json
from typing import Dict, Any, Optional


class ConfigLoader:
    @staticmethod
    def load(path: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Load JSON config.
        Nếu file không tồn tại:
            - Nếu có default: tạo file với default rồi trả về default.
            - Nếu không có default: raise FileNotFoundError.
        """
        if not os.path.exists(path):
            if default is not None:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=4)
                return default
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
