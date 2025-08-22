import os
import sys
import torch
import logging
import subprocess
import cv2
import numpy as np
from transformers import WhisperModel

# Import MuseTalk modules directly (they're pip installed)
# No sys.path manipulation needed
from musetalk.utils.utils import load_all_model, datagen, get_file_type
from musetalk.utils.preprocessing import get_landmark_and_bbox, read_imgs, coord_placeholder
from musetalk.utils.blending import get_image
from musetalk.utils.face_parsing import FaceParsing
from musetalk.utils.audio_processor import AudioProcessor

from config.settings import settings

# Create separate file logger for musetalk model
model_logger = logging.getLogger('musetalk_model')
model_handler = logging.FileHandler(os.path.join(settings.FASTAPI_SERVER_DIR, 'musetalk_model.log'))
model_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
model_logger.addHandler(model_handler)
model_logger.setLevel(logging.DEBUG)

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
        
        model_logger.info("MuseTalk model initialized")
        
    def _setup_ffmpeg(self):
        """Setup FFmpeg path"""
        try:
            # Check if ffmpeg is already available
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            model_logger.info("FFmpeg found in system PATH")
        except:
            # Add our ffmpeg to PATH if configured
            if hasattr(settings, 'FFMPEG_PATH') and settings.FFMPEG_PATH:
                path_separator = ';' if sys.platform == 'win32' else ':'
                os.environ["PATH"] = f"{settings.FFMPEG_PATH}{path_separator}{os.environ['PATH']}"
                
                # Check again
                try:
                    subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
                    model_logger.info(f"FFmpeg added from {settings.FFMPEG_PATH}")
                except:
                    model_logger.warning("FFmpeg not found, video processing may fail")
            else:
                model_logger.warning("FFmpeg not found, video processing may fail")
    
    def load_models(self):
        """Load MuseTalk models"""
        if self.models_loaded:
            return True
            
        try:
            model_logger.info("Loading MuseTalk models...")
            
            # Set device
            self.device = torch.device(f"cuda:{settings.GPU_ID}" if torch.cuda.is_available() else "cpu")
            model_logger.info(f"Using device: {self.device}")
            
            # CRITICAL: Change working directory for relative paths in MuseTalk components
            # This is exactly what Flask service does
            original_cwd = os.getcwd()
            model_logger.info(f"Changing working directory from {original_cwd} to {settings.MUSETALK_DIR}")
            os.chdir(settings.MUSETALK_DIR)
            
            try:
                # Load models using pip installed modules
                self.vae, self.unet, self.pe = load_all_model(
                    unet_model_path=settings.UNET_MODEL_PATH,
                    vae_type='sd-vae',
                    unet_config=settings.UNET_CONFIG_PATH,
                    device=self.device
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
                
            finally:
                # Restore original working directory
                model_logger.info(f"Restoring working directory to {original_cwd}")
                os.chdir(original_cwd)
            
            self.models_loaded = True
            model_logger.info("Models loaded successfully")
            return True
            
        except Exception as e:
            import traceback
            model_logger.error(f"Error loading models: {str(e)}")
            model_logger.error(f"Full traceback:\n{traceback.format_exc()}")
            return False
    
    def generate_talking_head(self, image_path: str, audio_path: str, output_path: str, 
                            bbox_shift: int = 0, fps: int = 25, batch_size: int = 8) -> dict:
        """Generate talking head video using the exact Flask service approach"""
        try:
            if not self.models_loaded:
                if not self.load_models():
                    return {
                        'status': 'error',
                        'message': 'Failed to load models'
                    }
            
            model_logger.info(f"Generating talking head: {image_path} + {audio_path} -> {output_path}")
            
            # Get landmarks and bounding box (exactly like Flask service)
            # Pass the file path directly, not loaded images
            model_logger.info(f"Getting landmarks and bbox for image: {image_path}")
            coord_list, frame_list = get_landmark_and_bbox([image_path], bbox_shift)
            model_logger.info(f"Got {len(coord_list)} coords and {len(frame_list)} frames")
            if not coord_list:
                return {
                    'status': 'error',
                    'message': 'Failed to detect face landmarks'
                }
            
            # Process audio (exactly like Flask service)
            model_logger.info(f"Processing audio: {audio_path}")
            weight_dtype = self.unet.model.dtype
            model_logger.info(f"Getting audio feature with weight_dtype: {weight_dtype}")
            whisper_input_features, librosa_length = self.audio_processor.get_audio_feature(audio_path, weight_dtype=weight_dtype)
            
            model_logger.info("Getting whisper chunks...")
            whisper_chunks = self.audio_processor.get_whisper_chunk(
                whisper_input_features,
                self.device,
                weight_dtype,
                self.whisper,
                librosa_length,
                fps=fps,
                audio_padding_length_left=2,
                audio_padding_length_right=2,
            )
            model_logger.info(f"Got {len(whisper_chunks)} whisper chunks")
            
            # Prepare VAE latents (exactly like Flask service)
            model_logger.info("Preparing VAE latents...")
            input_latent_list = []
            
            # Version-specific parameters
            if settings.MUSETALK_VERSION == "v15":
                extra_margin = 10
                parsing_mode = "jaw"
            else:
                extra_margin = 0
                parsing_mode = "raw"
            
            for idx, (bbox, frame) in enumerate(zip(coord_list, frame_list)):
                if bbox == coord_placeholder:
                    continue
                x1, y1, x2, y2 = bbox
                if settings.MUSETALK_VERSION == "v15":
                    y2 = y2 + extra_margin
                    y2 = min(y2, frame.shape[0])
                    coord_list[idx] = [x1, y1, x2, y2]  # Update bbox
                crop_frame = frame[y1:y2, x1:x2]
                resized_crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                latents = self.vae.get_latents_for_unet(resized_crop_frame)
                input_latent_list.append(latents)
            
            # Check if we have any valid latents
            if not input_latent_list:
                model_logger.error("No valid face regions found in the image - all frames had coord_placeholder")
                return {
                    'status': 'error', 
                    'message': 'No face detected in the image. Please provide an image with a clear face.'
                }
            
            # Create cyclic list for looping
            input_latent_list_cycle = input_latent_list + input_latent_list[::-1]
            coord_list_cycle = coord_list + coord_list[::-1]
            frame_list_cycle = frame_list + frame_list[::-1]
            
            # Generate frames (exactly like Flask service)
            model_logger.info("Generating frames...")
            video_num = len(whisper_chunks)
            gen = datagen(whisper_chunks, input_latent_list_cycle, batch_size, device=self.device)
            
            res_frame_list = []
            timesteps = torch.tensor([0], device=self.device)
            
            for i, (whisper_batch, latent_batch) in enumerate(gen):
                audio_feature_batch = self.pe(whisper_batch.to(self.device))
                latent_batch = latent_batch.to(device=self.device, dtype=self.unet.model.dtype)

                pred_latents = self.unet.model(
                    latent_batch,
                    timesteps,
                    encoder_hidden_states=audio_feature_batch
                ).sample
                
                pred_latents = pred_latents.to(device=self.device, dtype=self.vae.vae.dtype)
                recon = self.vae.decode_latents(pred_latents)
                
                for res_frame in recon:
                    res_frame_list.append(res_frame)
            
            model_logger.info(f"Generated {len(res_frame_list)} frames")
            
            # Save frames and create video (exactly like Flask service)
            model_logger.info("Saving frames...")
            output_path_str = str(output_path)
            os.makedirs(os.path.dirname(output_path_str), exist_ok=True)
            
            # Create result directory for frames
            input_basename = os.path.basename(image_path).split('.')[0]
            audio_basename = os.path.basename(audio_path).split('.')[0]
            output_vid_name = f"{input_basename}_{audio_basename}"
            result_img_save_path = os.path.join(os.path.dirname(output_path_str), output_vid_name)
            os.makedirs(result_img_save_path, exist_ok=True)
            
            # Save frames (exactly like Flask service)
            for idx, res_frame in enumerate(res_frame_list):
                bbox = coord_list_cycle[idx % len(coord_list_cycle)]
                ori_frame = frame_list_cycle[idx % len(frame_list_cycle)]
                x1, y1, x2, y2 = bbox
                
                try:
                    res_frame = cv2.resize(res_frame.astype(np.uint8), (x2 - x1, y2 - y1))
                except:
                    continue
                
                # Blend with original
                combine_frame = get_image(ori_frame, res_frame, bbox, mode=parsing_mode, fp=self.face_parser)
                
                # Save frame
                frame_filename = f"{idx:08d}.png"
                frame_path = os.path.join(result_img_save_path, frame_filename)
                cv2.imwrite(frame_path, combine_frame)
            
            # Create output video (exactly like Flask service)
            model_logger.info("Creating output video...")
            
            # Use ffmpeg to create video with even dimensions filter
            cmd_video = f"ffmpeg -y -framerate {fps} -i {result_img_save_path}/%08d.png -vf 'pad=ceil(iw/2)*2:ceil(ih/2)*2' -c:v libx264 -pix_fmt yuv420p -preset superfast {output_path_str}.tmp.mp4 -loglevel error"
            subprocess.run(cmd_video, shell=True, check=True)
            
            # Add audio
            cmd_audio = f"ffmpeg -y -i {output_path_str}.tmp.mp4 -i {audio_path} -c:v copy -c:a aac -map 0:v -map 1:a -shortest {output_path_str} -loglevel error"
            subprocess.run(cmd_audio, shell=True, check=True)
            
            # Clean up temp file
            if os.path.exists(f"{output_path_str}.tmp.mp4"):
                os.remove(f"{output_path_str}.tmp.mp4")
            
            model_logger.info(f"Video saved to: {output_path_str}")
            
            # Clean up VRAM after successful generation
            self._cleanup_vram()
            
            return {
                'status': 'success',
                'output_path': output_path_str,
                'frames_generated': len(res_frame_list)
            }
                    
        except Exception as e:
            model_logger.error(f"Error generating talking head: {str(e)}")
            import traceback
            model_logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            # Clean up VRAM even on failure
            self._cleanup_vram()
            
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _cleanup_vram(self):
        """Clean up GPU memory after processing"""
        try:
            if torch.cuda.is_available() and self.device and 'cuda' in str(self.device):
                # Get memory stats before cleanup
                if hasattr(torch.cuda, 'memory_allocated'):
                    memory_before = torch.cuda.memory_allocated(self.device) / (1024**3)  # GB
                    memory_cached_before = torch.cuda.memory_reserved(self.device) / (1024**3)  # GB
                else:
                    memory_before = memory_cached_before = 0
                
                # Clear cache and collect garbage
                torch.cuda.empty_cache()
                import gc
                gc.collect()
                
                # Get memory stats after cleanup
                if hasattr(torch.cuda, 'memory_allocated'):
                    memory_after = torch.cuda.memory_allocated(self.device) / (1024**3)  # GB
                    memory_cached_after = torch.cuda.memory_reserved(self.device) / (1024**3)  # GB
                    
                    model_logger.info(f"🧹 VRAM cleanup completed:")
                    model_logger.info(f"   • Allocated: {memory_before:.2f}GB → {memory_after:.2f}GB (freed {memory_before-memory_after:.2f}GB)")
                    model_logger.info(f"   • Cached: {memory_cached_before:.2f}GB → {memory_cached_after:.2f}GB (freed {memory_cached_before-memory_cached_after:.2f}GB)")
                else:
                    model_logger.info("🧹 VRAM cleanup completed (memory stats unavailable)")
                    
        except Exception as e:
            model_logger.warning(f"VRAM cleanup failed: {str(e)}")
    
    def health_check(self) -> dict:
        """Check if model is loaded and ready"""
        health_data = {
            'status': 'healthy' if self.models_loaded else 'loading',
            'models_loaded': self.models_loaded,
            'device': str(self.device) if self.device else 'unknown',
            'cuda_available': torch.cuda.is_available()
        }
        
        # Add GPU memory info if available
        if torch.cuda.is_available() and self.device and 'cuda' in str(self.device):
            try:
                if hasattr(torch.cuda, 'memory_allocated'):
                    allocated_gb = torch.cuda.memory_allocated(self.device) / (1024**3)
                    cached_gb = torch.cuda.memory_reserved(self.device) / (1024**3)
                    total_gb = torch.cuda.get_device_properties(self.device).total_memory / (1024**3)
                    
                    health_data['vram'] = {
                        'allocated_gb': round(allocated_gb, 2),
                        'cached_gb': round(cached_gb, 2),
                        'total_gb': round(total_gb, 2),
                        'usage_percent': round((allocated_gb / total_gb) * 100, 1)
                    }
            except Exception as e:
                health_data['vram'] = {'error': str(e)}
        
        return health_data