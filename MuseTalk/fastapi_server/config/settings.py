import os
from typing import List


class Settings:
    # Server settings
    MODEL_SERVER_HOST: str = "localhost"
    MODEL_SERVER_PORT: int = 8001
    HANDLER_SERVER_HOST: str = "0.0.0.0"
    HANDLER_SERVER_PORT: int = 8000

    # MuseTalk paths (fastapi_server is now inside MuseTalk)
    FASTAPI_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    MUSETALK_DIR = os.path.dirname(FASTAPI_SERVER_DIR)  # Parent of fastapi_server
    MODELS_DIR = os.path.join(MUSETALK_DIR, "models")

    # Model paths
    UNET_MODEL_PATH = os.path.join(MODELS_DIR, "musetalkV15", "unet.pth")
    UNET_CONFIG_PATH = os.path.join(MODELS_DIR, "musetalkV15", "musetalk.json")
    VAE_DIR = os.path.join(MODELS_DIR, "sd-vae")
    WHISPER_DIR = os.path.join(MODELS_DIR, "whisper")

    # FFmpeg path
    FFMPEG_PATH = os.path.join(MUSETALK_DIR, "ffmpeg-master-latest-linux64-gpl", "bin")

    # Storage settings
    STORAGE_DIR = os.path.join(FASTAPI_SERVER_DIR, "storage")
    TEMP_DIR = os.path.join(STORAGE_DIR, "temp")
    VIDEOS_DIR = os.path.join(STORAGE_DIR, "videos")
    UPLOADS_DIR = os.path.join(STORAGE_DIR, "uploads")

    # File settings
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_IMAGE_EXTENSIONS: List[str] = ["png", "jpg", "jpeg"]
    ALLOWED_AUDIO_EXTENSIONS: List[str] = ["wav", "mp3", "aac", "m4a", "ogg"]
    ALLOWED_VIDEO_EXTENSIONS: List[str] = ["mp4", "avi", "mov", "mkv", "webm", "flv"]

    # Image processing settings
    MAX_IMAGE_WIDTH: int = 1920   # Max width (1080p)
    MAX_IMAGE_HEIGHT: int = 1080  # Max height (1080p)
    AUTO_RESIZE_IMAGES: bool = True  # Automatically resize images larger than max dimensions
    RESIZE_QUALITY: int = 95  # JPEG quality for resized images (1-100)

    # Model settings
    DEFAULT_FPS: int = 25
    DEFAULT_BATCH_SIZE: int = 16
    DEFAULT_BBOX_SHIFT: int = 0
    USE_FLOAT16: bool = True
    GPU_ID: int = 0

    # Video processing settings
    MAX_VIDEO_DURATION: int = 30  # Maximum video duration in seconds (start with 30s)
    VIDEO_EXTRACT_FPS: int = 10  # FPS for frame extraction (lower = fewer frames to process)
    VIDEO_BATCH_SIZE: int = 4  # Smaller batch for video (memory constraint)
    VIDEO_FRAME_BUFFER_SIZE: int = 100  # Max frames to keep in memory at once
    MAX_VIDEO_RESOLUTION: int = 720  # Max resolution for video (start with 720p for performance)
    VIDEO_RESIZE_QUALITY: str = "medium"  # fast/medium/high
    TEMP_FRAME_CLEANUP: bool = True  # Clean extracted frames after processing

    # Memory management
    VIDEO_MEMORY_LIMIT_GB: float = 8.0  # Max GPU memory for video processing
    ADAPTIVE_BATCH_SIZE: bool = True  # Adjust batch based on available memory

    # Face detection caching
    ENABLE_FACE_CACHE: bool = True  # Enable face detection caching
    CACHE_DIR = os.path.join(STORAGE_DIR, "cache")  # Cache storage directory
    CACHE_MAX_SIZE_GB: float = 5.0  # Maximum cache size in GB

    # Realtime video generation
    ENABLE_REALTIME_MODE: bool = True  # Enable realtime generation endpoints
    REALTIME_PREP_DIR = os.path.join(STORAGE_DIR, "realtime")  # Realtime preparation directory
    REALTIME_CLEANUP_DAYS: int = 7  # Days to keep realtime preparations
    REALTIME_BATCH_SIZE: int = 2  # Smaller batch for realtime (ultra-fast)
    REALTIME_FRAME_SMOOTHING: bool = True  # Enable frame smoothing for better quality

    # Version
    MUSETALK_VERSION: str = "v15"

    # Timeouts
    MODEL_SERVER_TIMEOUT: int = 300  # 5 minutes
    GENERATION_TIMEOUT: int = 600  # 10 minutes

    # Queue settings
    MAX_CONCURRENT_MODEL_REQUESTS: int = 1  # Only 1 request to model server at a time

    # Google Cloud Storage settings
    GCS_ENABLED: bool = False  # Enable/disable GCS upload
    GCS_BUCKET_NAME: str = "yral_ai_generated_videos"
    GCS_BASE_PATH: str = "talking-head"  # Base path in bucket
    GCP_CREDENTIALS: str = os.environ.get("GCP_CREDENTIALS", "")  # GCP credentials from environment
    GCS_CLEANUP_LOCAL: bool = True  # Delete local files after successful GCS upload

    @classmethod
    def init_dirs(cls):
        """Create necessary directories if they don't exist"""
        os.makedirs(cls.STORAGE_DIR, exist_ok=True)
        os.makedirs(cls.TEMP_DIR, exist_ok=True)
        os.makedirs(cls.VIDEOS_DIR, exist_ok=True)
        os.makedirs(cls.UPLOADS_DIR, exist_ok=True)
        os.makedirs(cls.CACHE_DIR, exist_ok=True)
        os.makedirs(cls.REALTIME_PREP_DIR, exist_ok=True)


settings = Settings()
