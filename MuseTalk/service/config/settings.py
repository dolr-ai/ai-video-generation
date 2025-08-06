import os

class Config:
    # Flask settings
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # MuseTalk model paths
    SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    MUSETALK_DIR = os.path.dirname(SERVICE_DIR)
    MODELS_DIR = os.path.join(MUSETALK_DIR, 'models')

    # Model paths
    UNET_MODEL_PATH = os.path.join(MODELS_DIR, 'musetalkV15', 'unet.pth')
    UNET_CONFIG_PATH = os.path.join(MODELS_DIR, 'musetalkV15', 'musetalk.json')
    VAE_DIR = os.path.join(MODELS_DIR, 'sd-vae')
    WHISPER_DIR = os.path.join(MODELS_DIR, 'whisper')

    # FFmpeg path
    FFMPEG_PATH = os.path.join(MUSETALK_DIR, 'ffmpeg-master-latest-linux64-gpl', 'bin')

    # Results directory
    RESULTS_DIR = os.path.join(MUSETALK_DIR, 'results', 'api')
    TEMP_DIR = os.path.join(RESULTS_DIR, 'temp')

    # API settings
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    ALLOWED_AUDIO_EXTENSIONS = {'wav', 'mp3', 'aac', 'm4a', 'ogg'}
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

    # Model settings
    DEFAULT_FPS = 30
    DEFAULT_BATCH_SIZE = 8
    DEFAULT_BBOX_SHIFT = 0
    USE_FLOAT16 = True
    GPU_ID = 0

    # Version
    MUSETALK_VERSION = "v15"  # v15 or v1

    @classmethod
    def init_dirs(cls):
        """Create necessary directories if they don't exist"""
        os.makedirs(cls.RESULTS_DIR, exist_ok=True)
        os.makedirs(cls.TEMP_DIR, exist_ok=True)