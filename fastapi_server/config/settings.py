import os
from typing import List

class Settings:
    # Server settings
    MODEL_SERVER_HOST: str = "localhost"
    MODEL_SERVER_PORT: int = 8001
    HANDLER_SERVER_HOST: str = "0.0.0.0"
    HANDLER_SERVER_PORT: int = 8000
    
    # MuseTalk paths
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    MUSETALK_DIR = os.path.join(ROOT_DIR, 'MuseTalk')
    MODELS_DIR = os.path.join(MUSETALK_DIR, 'models')
    
    # Model paths
    UNET_MODEL_PATH = os.path.join(MODELS_DIR, 'musetalkV15', 'unet.pth')
    UNET_CONFIG_PATH = os.path.join(MODELS_DIR, 'musetalkV15', 'musetalk.json')
    VAE_DIR = os.path.join(MODELS_DIR, 'sd-vae')
    WHISPER_DIR = os.path.join(MODELS_DIR, 'whisper')
    
    # FFmpeg path
    FFMPEG_PATH = os.path.join(MUSETALK_DIR, 'ffmpeg-master-latest-linux64-gpl', 'bin')
    
    # Storage settings
    FASTAPI_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    STORAGE_DIR = os.path.join(FASTAPI_SERVER_DIR, 'storage')
    TEMP_DIR = os.path.join(STORAGE_DIR, 'temp')
    VIDEOS_DIR = os.path.join(STORAGE_DIR, 'videos')
    UPLOADS_DIR = os.path.join(STORAGE_DIR, 'uploads')
    
    # File settings
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_IMAGE_EXTENSIONS: List[str] = ['png', 'jpg', 'jpeg', 'gif', 'bmp']
    ALLOWED_AUDIO_EXTENSIONS: List[str] = ['wav', 'mp3', 'aac', 'm4a', 'ogg']
    
    # Model settings
    DEFAULT_FPS: int = 25
    DEFAULT_BATCH_SIZE: int = 8
    DEFAULT_BBOX_SHIFT: int = 0
    USE_FLOAT16: bool = True
    GPU_ID: int = 0
    
    # Version
    MUSETALK_VERSION: str = "v15"
    
    # Timeouts
    MODEL_SERVER_TIMEOUT: int = 300  # 5 minutes
    GENERATION_TIMEOUT: int = 600    # 10 minutes
    
    @classmethod
    def init_dirs(cls):
        """Create necessary directories if they don't exist"""
        os.makedirs(cls.STORAGE_DIR, exist_ok=True)
        os.makedirs(cls.TEMP_DIR, exist_ok=True)
        os.makedirs(cls.VIDEOS_DIR, exist_ok=True)
        os.makedirs(cls.UPLOADS_DIR, exist_ok=True)

settings = Settings()