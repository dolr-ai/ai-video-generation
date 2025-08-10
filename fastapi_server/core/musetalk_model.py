import os
import sys
import torch
import logging
import subprocess
from omegaconf import OmegaConf
from transformers import WhisperModel
import numpy as np

from config.settings import settings
from core.preprocessing_wrapper import preprocessing_wrapper

logger = logging.getLogger(__name__)

class MuseTalkModel:
    def __init__(self):
        self.device = None
        self.models_loaded = False
        self.vae = None
        self.unet = None
        self.pe = None
        self.whisper = None
        self.audio_processor = None
        self.face_parser = None
        
        # Setup FFmpeg
        self._setup_ffmpeg()
        
        logger.info("MuseTalk model initialized")
        
    def _setup_ffmpeg(self):
        """Setup FFmpeg path"""
        try:
            # Check if ffmpeg is already available
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            logger.info("FFmpeg found in system PATH")
        except:
            # Add our ffmpeg to PATH
            path_separator = ';' if sys.platform == 'win32' else ':'
            os.environ["PATH"] = f"{settings.FFMPEG_PATH}{path_separator}{os.environ['PATH']}"
            
            # Check again
            try:
                subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
                logger.info(f"FFmpeg added from {settings.FFMPEG_PATH}")
            except:
                logger.warning("FFmpeg not found, video processing may fail")
    
    def load_models(self):
        """Load MuseTalk models"""
        if self.models_loaded:
            return True
            
        try:
            logger.info("Loading MuseTalk models...")
            
            # Set device
            self.device = torch.device(f"cuda:{settings.GPU_ID}" if torch.cuda.is_available() else "cpu")
            logger.info(f"Using device: {self.device}")
            
            # Change working directory for relative paths in MuseTalk components
            original_cwd = os.getcwd()
            os.chdir(settings.MUSETALK_DIR)
            
            # Import MuseTalk modules after changing directory
            from musetalk.utils.utils import load_all_model
            from musetalk.utils.face_parsing import FaceParsing
            from musetalk.utils.audio_processor import AudioProcessor
            
            # Load models (let MuseTalk handle device selection)
            self.vae, self.unet, self.pe = load_all_model(
                unet_model_path=settings.UNET_MODEL_PATH,
                vae_type='sd-vae',
                unet_config=settings.UNET_CONFIG_PATH,
                device=None  # Let MuseTalk handle device selection
            )
            
            # Convert to float16 if enabled
            if settings.USE_FLOAT16:
                self.pe = self.pe.half()
                self.vae.vae = self.vae.vae.half()
                self.unet.model = self.unet.model.half()
            
            # Move to device
            self.pe = self.pe.to(self.device)
            self.vae.vae = self.vae.vae.to(self.device)
            self.unet.model = self.unet.model.to(self.device)
            
            # Load audio processor and whisper
            self.audio_processor = AudioProcessor(feature_extractor_path=settings.WHISPER_DIR)
            weight_dtype = self.unet.model.dtype
            self.whisper = WhisperModel.from_pretrained(settings.WHISPER_DIR)
            self.whisper = self.whisper.to(device=self.device, dtype=weight_dtype).eval()
            self.whisper.requires_grad_(False)
            
            # Initialize face parser (while still in MuseTalk directory)
            if settings.MUSETALK_VERSION == "v15":
                self.face_parser = FaceParsing(
                    left_cheek_width=90,
                    right_cheek_width=90
                )
            else:
                self.face_parser = FaceParsing()
            
            # Initialize preprocessing wrapper
            preprocessing_wrapper.initialize()
                
            # Restore original working directory
            os.chdir(original_cwd)
            
            self.models_loaded = True
            logger.info("Models loaded successfully")
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"Error loading models: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            return False
    
    def generate_talking_head(self, image_path: str, audio_path: str, output_path: str, 
                            bbox_shift: int = 0, fps: int = 25, batch_size: int = 8) -> dict:
        """Generate talking head video"""
        try:
            if not self.models_loaded:
                if not self.load_models():
                    return {
                        'status': 'error',
                        'message': 'Failed to load models'
                    }
            
            logger.info(f"Generating talking head: {image_path} + {audio_path} -> {output_path}")
            
            # Change to MuseTalk directory for processing
            original_cwd = os.getcwd()
            os.chdir(settings.MUSETALK_DIR)
            
            try:
                # Process input image
                input_img_list = preprocessing_wrapper.read_imgs([image_path])
                if not input_img_list:
                    return {
                        'status': 'error',
                        'message': 'Failed to read input image'
                    }
                
                # Get landmarks and bounding box
                coord_list, frame_list = preprocessing_wrapper.get_landmark_and_bbox(input_img_list, bbox_shift)
                if not coord_list:
                    return {
                        'status': 'error',
                        'message': 'Failed to detect face landmarks'
                    }
                
                # Process audio
                whisper_feature = self.audio_processor.audio2feat(audio_path)
                whisper_chunks = self.audio_processor.feature2chunks(
                    feature_array=whisper_feature,
                    fps=fps
                )
                
                if len(whisper_chunks) == 0:
                    return {
                        'status': 'error',
                        'message': 'Failed to process audio'
                    }
                
                # Import datagen and get_image locally
                from musetalk.utils.utils import datagen
                from musetalk.utils.blending import get_image
                
                # Generate video frames
                video_num = len(whisper_chunks)
                gen = datagen(
                    whisper_chunks,
                    coord_list,
                    frame_list,
                    self.face_parser,
                    batch_size=batch_size
                )
                
                res_frame_list = []
                for i, (whisper_batch, coord_batch, frame_batch) in enumerate(gen):
                    tensor_list = [
                        torch.from_numpy(arr).to(dtype=torch.float16 if settings.USE_FLOAT16 else torch.float32, device=self.device)
                        for arr in whisper_batch
                    ]
                    
                    audio_feature_batch = torch.stack(tensor_list, dim=0)
                    audio_feature_batch = audio_feature_batch.to(self.device)
                    
                    pred = self.unet.model(
                        audio_feature_batch,
                        self.pe(coord_batch).to(self.device)
                    )
                    
                    pred = pred.cpu().numpy()
                    
                    for res, coord, frame in zip(pred, coord_batch, frame_batch):
                        res_frame = get_image(res, coord, frame, self.face_parser)
                        res_frame_list.append(res_frame)
                
                # Save video
                if res_frame_list:
                    # Create output directory
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    # Use FFmpeg to create video
                    import cv2
                    height, width = res_frame_list[0].shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                    
                    for frame in res_frame_list:
                        out.write(frame)
                    out.release()
                    
                    logger.info(f"Video generated successfully: {output_path}")
                    return {
                        'status': 'success',
                        'output_path': output_path,
                        'frames_generated': len(res_frame_list)
                    }
                else:
                    return {
                        'status': 'error',
                        'message': 'No frames generated'
                    }
                    
            finally:
                # Restore original working directory
                os.chdir(original_cwd)
                
        except Exception as e:
            logger.error(f"Error generating talking head: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def health_check(self) -> dict:
        """Check if model is loaded and ready"""
        return {
            'status': 'healthy' if self.models_loaded else 'loading',
            'models_loaded': self.models_loaded,
            'device': str(self.device) if self.device else 'unknown',
            'cuda_available': torch.cuda.is_available()
        }