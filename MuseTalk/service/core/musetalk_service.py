import os
import torch
import logging
import shutil
import subprocess
from omegaconf import OmegaConf
from transformers import WhisperModel
import numpy as np

# Import MuseTalk modules using absolute imports
from musetalk.utils.utils import load_all_model, datagen
from musetalk.utils.face_parsing import FaceParsing
from musetalk.utils.audio_processor import AudioProcessor
from musetalk.utils.preprocessing import get_landmark_and_bbox, read_imgs
from musetalk.utils.blending import get_image

from service.config.settings import Config
from service.core.inference_handler import InferenceHandler
from service.core.realtime_handler import RealtimeHandler

logger = logging.getLogger(__name__)

class MuseTalkService:
    def __init__(self):
        self.device = None
        self.models_loaded = False
        self.vae = None
        self.unet = None
        self.pe = None
        self.whisper = None
        self.audio_processor = None
        self.face_parser = None
        self.inference_handler = None
        self.realtime_handler = None
        
        # Initialize directories
        Config.init_dirs()
        
        # Setup FFmpeg
        self._setup_ffmpeg()
        
        # Load models on first use
        logger.info("MuseTalk service initialized")
        
    def _setup_ffmpeg(self):
        """Setup FFmpeg path"""
        try:
            # Check if ffmpeg is already available
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            logger.info("FFmpeg found in system PATH")
        except:
            # Add our ffmpeg to PATH
            path_separator = ';' if sys.platform == 'win32' else ':'
            os.environ["PATH"] = f"{Config.FFMPEG_PATH}{path_separator}{os.environ['PATH']}"
            
            # Check again
            try:
                subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
                logger.info(f"FFmpeg added from {Config.FFMPEG_PATH}")
            except:
                logger.warning("FFmpeg not found, video processing may fail")
    
    def _load_models(self):
        """Load MuseTalk models"""
        if self.models_loaded:
            return
            
        logger.info("Loading MuseTalk models...")
        
        # Set device
        self.device = torch.device(f"cuda:{Config.GPU_ID}" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        
        # Load models
        self.vae, self.unet, self.pe = load_all_model(
            unet_model_path=Config.UNET_MODEL_PATH,
            vae_type='mse',
            unet_config=Config.UNET_CONFIG_PATH,
            device=self.device
        )
        
        # Convert to float16 if enabled
        if Config.USE_FLOAT16:
            self.pe = self.pe.half()
            self.vae.vae = self.vae.vae.half()
            self.unet.model = self.unet.model.half()
        
        # Move to device
        self.pe = self.pe.to(self.device)
        self.vae.vae = self.vae.vae.to(self.device)
        self.unet.model = self.unet.model.to(self.device)
        
        # Load audio processor and whisper
        self.audio_processor = AudioProcessor(feature_extractor_path=Config.WHISPER_DIR)
        weight_dtype = self.unet.model.dtype
        self.whisper = WhisperModel.from_pretrained(Config.WHISPER_DIR)
        self.whisper = self.whisper.to(device=self.device, dtype=weight_dtype).eval()
        self.whisper.requires_grad_(False)
        
        # Initialize face parser
        if Config.MUSETALK_VERSION == "v15":
            self.face_parser = FaceParsing(
                left_cheek_width=90,
                right_cheek_width=90
            )
        else:
            self.face_parser = FaceParsing()
        
        # Initialize handlers
        self.inference_handler = InferenceHandler(
            vae=self.vae,
            unet=self.unet,
            pe=self.pe,
            whisper=self.whisper,
            audio_processor=self.audio_processor,
            face_parser=self.face_parser,
            device=self.device
        )
        
        self.realtime_handler = RealtimeHandler(
            vae=self.vae,
            unet=self.unet,
            pe=self.pe,
            whisper=self.whisper,
            audio_processor=self.audio_processor,
            face_parser=self.face_parser,
            device=self.device
        )
        
        self.models_loaded = True
        logger.info("Models loaded successfully")
    
    def generate_talking_head(self, image_path, audio_path, output_dir, 
                            bbox_shift=0, realtime=False, fps=25, 
                            batch_size=8, script=None):
        """Generate talking head video"""
        try:
            # Ensure models are loaded
            self._load_models()
            
            if realtime:
                # Use realtime inference
                logger.info("Using real-time inference mode")
                return self.realtime_handler.generate_single(
                    image_path=image_path,
                    audio_path=audio_path,
                    output_dir=output_dir,
                    bbox_shift=bbox_shift,
                    fps=fps,
                    batch_size=batch_size
                )
            else:
                # Use normal inference
                logger.info("Using normal inference mode")
                return self.inference_handler.generate(
                    video_path=image_path,
                    audio_path=audio_path,
                    output_dir=output_dir,
                    bbox_shift=bbox_shift,
                    fps=fps,
                    batch_size=batch_size,
                    script=script
                )
                
        except Exception as e:
            logger.error(f"Error generating talking head: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def generate_realtime(self, avatar_id, video_path, audio_clips, 
                         preparation=True, bbox_shift=0, output_dir=None):
        """Generate talking head using real-time inference with avatar"""
        try:
            # Ensure models are loaded
            self._load_models()
            
            logger.info(f"Generating real-time talking head for avatar: {avatar_id}")
            
            return self.realtime_handler.generate_with_avatar(
                avatar_id=avatar_id,
                video_path=video_path,
                audio_clips=audio_clips,
                preparation=preparation,
                bbox_shift=bbox_shift,
                output_dir=output_dir
            )
            
        except Exception as e:
            logger.error(f"Error in real-time generation: {str(e)}")
            return []