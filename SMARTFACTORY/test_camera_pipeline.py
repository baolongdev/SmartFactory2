# test_camera_pipeline_real_config.py
from app.core.config.app_config import AppConfig
from app.core.camera import CameraPipeline

if __name__ == "__main__":
    # Load AppConfig thật
    app_cfg = AppConfig()  # mặc định sẽ load config/config_app.json
    cam_cfg = app_cfg.camera_config  # instance của CameraConfig

    # Tạo pipeline từ camera config thực
    pipeline = CameraPipeline(cam_cfg)

    print("[Test] Press ESC to exit.")
    pipeline.start()
