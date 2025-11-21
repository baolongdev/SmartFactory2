class ConfigValidator:
    @staticmethod
    def require(data: dict, key: str, default=None, *, fallback_keys=None, expected_type=None):
        """
        Safe getter for JSON config.

        Args:
            data (dict): nguồn dữ liệu JSON.
            key (str): key chính cần lấy.
            default: giá trị trả về nếu không tìm thấy key.
            fallback_keys (list[str]): danh sách key fallback (ví dụ: ['lower', 'hsv_lower']).
            expected_type: type mong muốn (ví dụ list, dict, int...), nếu sai type → dùng default.

        Returns:
            Giá trị lấy từ JSON, hoặc default nếu không hợp lệ.
        """

        if not isinstance(data, dict):
            return default

        # --- Primary key ---
        if key in data:
            value = data[key]
        else:
            # --- Fallback keys ---
            value = None
            if fallback_keys:
                for fb in fallback_keys:
                    if fb in data:
                        value = data[fb]
                        break

            if value is None:
                return default

        # --- Type checking ---
        if expected_type and not isinstance(value, expected_type):
            return default

        return value
