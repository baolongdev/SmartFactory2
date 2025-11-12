import os

from flask import json


class ConfigLoader:
    @staticmethod
    def load(path: str, default: dict = None) -> dict:
        """
        Load JSON config. If not exists, create with default.
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