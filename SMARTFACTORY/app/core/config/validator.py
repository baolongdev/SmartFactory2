class ConfigValidator:
    @staticmethod
    def require(data: dict, key: str, default=None):
        return data[key] if key in data else default