import os
import sys
import torch
import logging
import subprocess
import cv2
import numpy as np
import threading
import queue
import time
import tempfile
import shutil
from typing import List, Tuple, Optional
from datetime import datetime
from transformers import WhisperModel

# Import MuseTalk modules directly (they're pip installed)
# No sys.path manipulation needed
from musetalk.utils.utils import load_all_model, datagen
from musetalk.utils.preprocessing import get_landmark_and_bbox, coord_placeholder
from musetalk.utils.blending import get_image
from musetalk.utils.face_parsing import FaceParsing
from musetalk.utils.audio_processor import AudioProcessor

from config.settings import settings
from utils.video_utils import (
    extract_frames,
    create_video_from_frames,
    cleanup_extracted_frames
)
from utils.cache_utils import FaceDetectionCache, RealtimePreparationCache

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
        
        # Initialize caching systems
        if settings.ENABLE_FACE_CACHE:
            self.face_cache = FaceDetectionCache(
                cache_dir=settings.CACHE_DIR,
                max_size_gb=settings.CACHE_MAX_SIZE_GB
            )
            model_logger.info("Face detection cache initialized")
        else:
            self.face_cache = None
            
        if settings.ENABLE_REALTIME_MODE:
            self.realtime_cache = RealtimePreparationCache(
                prep_dir=settings.REALTIME_PREP_DIR,
                cleanup_days=settings.REALTIME_CLEANUP_DAYS
            )
            model_logger.info("Realtime preparation cache initialized")
        else:
            self.realtime_cache = None
        
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
    
    def process_frames(self, res_frame_queue, video_len, coord_list_cycle, frame_list_cycle, 
                      result_img_save_path, parsing_mode):
        """Process frames in parallel thread for realtime performance"""
        idx = 0
        model_logger.info(f"Starting frame processor thread for {video_len} frames")
        
        while idx < video_len:
            try:
                # Get frame from queue with timeout
                res_frame = res_frame_queue.get(block=True, timeout=1)
            except queue.Empty:
                continue
            
            # Get coordinates and original frame
            bbox = coord_list_cycle[idx % len(coord_list_cycle)]
            ori_frame = frame_list_cycle[idx % len(frame_list_cycle)]
            x1, y1, x2, y2 = bbox
            
            try:
                # Resize generated frame to match bbox
                res_frame = cv2.resize(res_frame.astype(np.uint8), (x2 - x1, y2 - y1))
            except Exception as e:
                model_logger.warning(f"Failed to resize frame {idx}: {str(e)}")
                idx += 1
                continue
            
            # Blend with original frame
            combine_frame = get_image(ori_frame, res_frame, bbox, mode=parsing_mode, fp=self.face_parser)
            
            # Save frame
            cv2.imwrite(f"{result_img_save_path}/{str(idx).zfill(8)}.png", combine_frame)
            
            idx += 1
            
            if idx % 10 == 0:
                model_logger.debug(f"Processed {idx}/{video_len} frames")
        
        model_logger.info(f"Frame processor thread completed - processed {idx} frames")
    
    def get_face_data_cached(self, image_paths: List[str], bbox_shift: int = 0) -> Tuple[List, List]:
        """
        Get face detection data with caching support
        
        Args:
            image_paths: List of image file paths
            bbox_shift: Bounding box shift parameter
            
        Returns:
            Tuple of (coord_list, frame_list)
        """
        # Check if caching is enabled and this is a single video
        use_cache = (self.face_cache is not None and 
                    len(image_paths) > 10)  # Only cache for substantial datasets
        
        cache_key = None
        if use_cache:
            # For multiple images, use the directory path as cache key base
            if len(image_paths) > 1:
                base_dir = os.path.dirname(image_paths[0])
                # Create a combined hash of all image files
                import hashlib
                combined_hash = hashlib.md5()
                for path in sorted(image_paths):
                    combined_hash.update(path.encode())
                cache_params = {
                    'base_dir': base_dir,
                    'num_images': len(image_paths),
                    'combined_hash': combined_hash.hexdigest()[:16],
                    'version': settings.MUSETALK_VERSION
                }
            else:
                cache_params = {'version': settings.MUSETALK_VERSION}
                
            cache_key = self.face_cache.get_cache_key(
                image_paths[0] if len(image_paths) == 1 else base_dir,
                bbox_shift,
                cache_params
            )
            
            # Try to load from cache
            cached_data = self.face_cache.load_face_data(cache_key)
            if cached_data:
                model_logger.info(f"✅ Using cached face detection data")
                coord_list = cached_data['coord_list']
                
                # Need to reload frames (not cached due to size)
                frame_list = []
                for img_path in image_paths:
                    frame = cv2.imread(img_path)
                    if frame is not None:
                        frame_list.append(frame)
                
                if len(frame_list) == len(coord_list):
                    return coord_list, frame_list
                else:
                    model_logger.warning("Cached coordinates don't match current frames, recomputing...")
        
        # Perform face detection
        model_logger.info(f"🔍 Computing face detection for {len(image_paths)} images...")
        coord_list, frame_list = get_landmark_and_bbox(image_paths, bbox_shift)
        
        # Save to cache if enabled
        if use_cache and cache_key and coord_list:
            self.face_cache.save_face_data(
                cache_key, 
                coord_list,
                frame_list,
                extra_data={'version': settings.MUSETALK_VERSION}
            )
        
        return coord_list, frame_list
    
    def prepare_realtime_video(self, video_path: str, prep_id: str, 
                              bbox_shift: int = settings.DEFAULT_BBOX_SHIFT) -> dict:
        """
        Prepare video for realtime inference by pre-processing all materials
        
        Args:
            video_path: Path to input video
            prep_id: Unique preparation ID
            bbox_shift: Bounding box shift parameter
            
        Returns:
            Preparation result dictionary
        """
        try:
            if not self.models_loaded:
                if not self.load_models():
                    return {
                        'status': 'error',
                        'message': 'Failed to load models'
                    }
            
            if not self.realtime_cache:
                return {
                    'status': 'error',
                    'message': 'Realtime mode not enabled'
                }
            
            model_logger.info(f"🚀 Preparing realtime video: {video_path} -> {prep_id}")
            
            # Extract frames from video
            temp_dir = tempfile.mkdtemp(prefix="realtime_prep_")
            frames_dir = os.path.join(temp_dir, "frames")
            
            try:
                # Extract frames
                from utils.video_utils import get_video_info
                video_info = get_video_info(video_path)
                if not video_info:
                    return {'status': 'error', 'message': 'Invalid video file'}
                
                frame_paths = extract_frames(
                    video_path,
                    frames_dir,
                    extract_fps=min(video_info['fps'], 25),  # Limit to 25fps max
                    max_frames=300  # Limit for realtime prep
                )
                
                if not frame_paths:
                    return {'status': 'error', 'message': 'Failed to extract frames'}
                
                model_logger.info(f"Extracted {len(frame_paths)} frames for preparation")
                
                # Get face detection data (with caching)
                coord_list, frame_list = self.get_face_data_cached(frame_paths, bbox_shift)
                
                if not coord_list:
                    return {
                        'status': 'error',
                        'message': 'No faces detected in video'
                    }
                
                # Process latents and masks
                input_latent_list = []
                mask_coords_list = []
                valid_frame_indices = []
                
                # Version-specific parameters
                if settings.MUSETALK_VERSION == "v15":
                    extra_margin = 10
                    parsing_mode = "jaw"
                else:
                    extra_margin = 0
                    parsing_mode = "raw"
                
                for idx, (bbox, frame) in enumerate(zip(coord_list, frame_list)):
                    if bbox == coord_placeholder:
                        input_latent_list.append(None)
                        mask_coords_list.append(None)
                        continue
                    
                    x1, y1, x2, y2 = bbox
                    if settings.MUSETALK_VERSION == "v15":
                        y2 = y2 + extra_margin
                        y2 = min(y2, frame.shape[0])
                        coord_list[idx] = [x1, y1, x2, y2]
                    
                    # Prepare latents
                    crop_frame = frame[y1:y2, x1:x2]
                    resized_crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                    latents = self.vae.get_latents_for_unet(resized_crop_frame)
                    input_latent_list.append(latents)
                    
                    # Prepare mask coordinates
                    from musetalk.utils.blending import get_image_prepare_material
                    mask, crop_box = get_image_prepare_material(frame, [x1, y1, x2, y2], fp=self.face_parser, mode=parsing_mode)
                    mask_coords_list.append(crop_box)
                    valid_frame_indices.append(idx)
                
                # Apply frame smoothing if enabled
                if settings.REALTIME_FRAME_SMOOTHING:
                    model_logger.info("Applying frame smoothing (forward + reverse)")
                    coord_list_cycle = coord_list + coord_list[::-1]
                    input_latent_list_cycle = input_latent_list + input_latent_list[::-1]
                    mask_coords_list_cycle = mask_coords_list + mask_coords_list[::-1]
                else:
                    coord_list_cycle = coord_list
                    input_latent_list_cycle = input_latent_list
                    mask_coords_list_cycle = mask_coords_list
                
                # Save preparation data
                prep_data = {
                    'coordinates': coord_list_cycle,
                    'latents': input_latent_list_cycle,
                    'masks': mask_coords_list_cycle,
                    'metadata': {
                        'prep_id': prep_id,
                        'video_path': video_path,
                        'bbox_shift': bbox_shift,
                        'version': settings.MUSETALK_VERSION,
                        'num_frames': len(frame_list),
                        'valid_frames': len(valid_frame_indices),
                        'smoothing_enabled': settings.REALTIME_FRAME_SMOOTHING,
                        'created_at': datetime.now().isoformat(),
                        'video_info': video_info
                    }
                }
                
                success = self.realtime_cache.save_preparation(prep_id, prep_data)
                
                if success:
                    model_logger.info(f"✅ Realtime preparation saved: {prep_id}")
                    return {
                        'status': 'success',
                        'prep_id': prep_id,
                        'num_frames': len(frame_list),
                        'valid_frames': len(valid_frame_indices),
                        'smoothing_enabled': settings.REALTIME_FRAME_SMOOTHING
                    }
                else:
                    return {
                        'status': 'error',
                        'message': 'Failed to save preparation data'
                    }
                    
            finally:
                # Clean up temp directory
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    
        except Exception as e:
            model_logger.error(f"Error preparing realtime video: {str(e)}")
            import traceback
            model_logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def generate_realtime_video(self, prep_id: str, audio_path: str, output_path: str,
                               fps: int = 25) -> dict:
        """
        Generate video using pre-processed realtime preparation
        
        Args:
            prep_id: Preparation ID from prepare_realtime_video
            audio_path: Path to audio file
            output_path: Path for output video
            fps: Output video FPS
            
        Returns:
            Generation result dictionary
        """
        try:
            if not self.models_loaded:
                if not self.load_models():
                    return {
                        'status': 'error',
                        'message': 'Failed to load models'
                    }
            
            if not self.realtime_cache:
                return {
                    'status': 'error',
                    'message': 'Realtime mode not enabled'
                }
            
            model_logger.info(f"🎬 Generating realtime video: {prep_id} + {audio_path} -> {output_path}")
            
            # Load preparation data
            prep_data = self.realtime_cache.load_preparation(prep_id)
            if not prep_data:
                return {
                    'status': 'error',
                    'message': f'Preparation not found: {prep_id}'
                }
            
            coord_list_cycle = prep_data['coordinates']
            input_latent_list_cycle = prep_data['latents']
            mask_coords_list_cycle = prep_data['masks']
            metadata = prep_data['metadata']
            
            model_logger.info(f"Loaded preparation: {metadata['num_frames']} frames, {metadata['valid_frames']} with faces")
            
            # Process audio
            model_logger.info(f"Processing audio: {audio_path}")
            weight_dtype = self.unet.model.dtype
            whisper_input_features, librosa_length = self.audio_processor.get_audio_feature(audio_path, weight_dtype=weight_dtype)
            
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
            
            video_num = len(whisper_chunks)
            model_logger.info(f"Generating {video_num} frames using realtime mode...")
            
            # Create temp directory for output frames
            temp_dir = tempfile.mkdtemp(prefix="realtime_gen_")
            output_frames_dir = os.path.join(temp_dir, "frames")
            os.makedirs(output_frames_dir, exist_ok=True)
            
            try:
                # Generate frames with ultra-small batch size for realtime
                gen = datagen(whisper_chunks, input_latent_list_cycle, settings.REALTIME_BATCH_SIZE, device=self.device)
                timesteps = torch.tensor([0], device=self.device)
                
                start_gen_time = time.time()
                frames_generated = 0
                
                # Process in batches and immediately blend
                frame_idx = 0
                for whisper_batch, latent_batch in gen:
                    audio_feature_batch = self.pe(whisper_batch.to(self.device))
                    latent_batch = latent_batch.to(device=self.device, dtype=self.unet.model.dtype)
                    
                    pred_latents = self.unet.model(
                        latent_batch,
                        timesteps,
                        encoder_hidden_states=audio_feature_batch
                    ).sample
                    
                    pred_latents = pred_latents.to(device=self.device, dtype=self.vae.vae.dtype)
                    recon = self.vae.decode_latents(pred_latents)
                    
                    # Process each frame immediately
                    for res_frame in recon:
                        if frame_idx >= video_num:
                            break
                            
                        bbox = coord_list_cycle[frame_idx % len(coord_list_cycle)]
                        mask_crop_box = mask_coords_list_cycle[frame_idx % len(mask_coords_list_cycle)]
                        
                        # Create synthetic frame (since we don't store original frames)
                        # Use average frame size from metadata
                        frame_shape = (720, 1280, 3)  # Default size
                        if 'video_info' in metadata:
                            frame_shape = (metadata['video_info']['height'], metadata['video_info']['width'], 3)
                        
                        ori_frame = np.zeros(frame_shape, dtype=np.uint8)  # Black background
                        
                        if bbox != coord_placeholder and mask_crop_box:
                            x1, y1, x2, y2 = bbox
                            try:
                                res_frame_resized = cv2.resize(res_frame.astype(np.uint8), (x2 - x1, y2 - y1))
                                
                                # Simple blending (place face region)
                                ori_frame[y1:y2, x1:x2] = res_frame_resized
                            except Exception as e:
                                model_logger.warning(f"Frame blending failed for frame {frame_idx}: {e}")
                        
                        # Save frame
                        cv2.imwrite(f"{output_frames_dir}/{str(frame_idx).zfill(8)}.png", ori_frame)
                        
                        frame_idx += 1
                        frames_generated += 1
                    
                    # Clear VRAM frequently for realtime performance
                    if frames_generated % 20 == 0:
                        torch.cuda.empty_cache()
                
                generation_time = time.time() - start_gen_time
                model_logger.info(f"Realtime generation completed: {frames_generated} frames in {generation_time:.2f}s ({frames_generated/generation_time:.1f} fps)")
                
                # Create output video
                model_logger.info("Creating output video...")
                success = create_video_from_frames(
                    output_frames_dir,
                    output_path,
                    fps=fps,
                    audio_path=audio_path
                )
                
                if not success:
                    return {
                        'status': 'error',
                        'message': 'Failed to create output video'
                    }
                
                model_logger.info(f"Realtime video saved to: {output_path}")
                
                # Clean up VRAM
                self._cleanup_vram()
                
                return {
                    'status': 'success',
                    'output_path': output_path,
                    'frames_generated': frames_generated,
                    'generation_time': round(generation_time, 2),
                    'fps_achieved': round(frames_generated / generation_time, 1),
                    'prep_id': prep_id
                }
                
            finally:
                # Clean up temp directory
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    
        except Exception as e:
            model_logger.error(f"Error generating realtime video: {str(e)}")
            import traceback
            model_logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            # Clean up VRAM even on failure
            self._cleanup_vram()
            
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def generate_talking_head(self, image_path: str, audio_path: str, output_path: str, 
                            bbox_shift: int = settings.DEFAULT_BBOX_SHIFT, fps: int = settings.DEFAULT_FPS, 
                            batch_size: int = settings.DEFAULT_BATCH_SIZE) -> dict:
        """Generate talking head video using the exact Flask service approach"""
        try:
            if not self.models_loaded:
                if not self.load_models():
                    return {
                        'status': 'error',
                        'message': 'Failed to load models'
                    }
            
            model_logger.info(f"Generating talking head: {image_path} + {audio_path} -> {output_path}")
            
            # Get landmarks and bounding box with caching
            model_logger.info(f"Getting landmarks and bbox for image: {image_path}")
            coord_list, frame_list = self.get_face_data_cached([image_path], bbox_shift)
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
            
            # Setup for realtime generation
            video_num = len(whisper_chunks)
            model_logger.info(f"Generating {video_num} frames using realtime approach...")
            
            # Create result directory for frames early
            output_path_str = str(output_path)
            os.makedirs(os.path.dirname(output_path_str), exist_ok=True)
            
            input_basename = os.path.basename(image_path).split('.')[0]
            audio_basename = os.path.basename(audio_path).split('.')[0]
            output_vid_name = f"{input_basename}_{audio_basename}"
            result_img_save_path = os.path.join(os.path.dirname(output_path_str), output_vid_name)
            os.makedirs(result_img_save_path, exist_ok=True)
            
            # Create queue for realtime frame processing
            res_frame_queue = queue.Queue()
            
            # Start frame processor thread
            process_thread = threading.Thread(
                target=self.process_frames, 
                args=(res_frame_queue, video_num, coord_list_cycle, frame_list_cycle, 
                      result_img_save_path, parsing_mode)
            )
            process_thread.start()
            
            # Generate frames and put them in queue
            gen = datagen(whisper_chunks, input_latent_list_cycle, batch_size, device=self.device)
            timesteps = torch.tensor([0], device=self.device)
            
            start_gen_time = time.time()
            frames_generated = 0
            
            for whisper_batch, latent_batch in gen:
                audio_feature_batch = self.pe(whisper_batch.to(self.device))
                latent_batch = latent_batch.to(device=self.device, dtype=self.unet.model.dtype)

                pred_latents = self.unet.model(
                    latent_batch,
                    timesteps,
                    encoder_hidden_states=audio_feature_batch
                ).sample
                
                pred_latents = pred_latents.to(device=self.device, dtype=self.vae.vae.dtype)
                recon = self.vae.decode_latents(pred_latents)
                
                # Put frames in queue for processing
                for res_frame in recon:
                    res_frame_queue.put(res_frame)
                    frames_generated += 1
            
            # Wait for processor thread to complete
            process_thread.join()
            
            generation_time = time.time() - start_gen_time
            model_logger.info(f"Realtime generation completed: {frames_generated} frames in {generation_time:.2f}s ({frames_generated/generation_time:.1f} fps)")
            
            # Frames have already been saved by the processor thread
            # No need to process them again
            
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
                'frames_generated': frames_generated
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
    
    def process_video_frames(self, res_frame_queue, frame_paths: List[str], coord_list: List, 
                            frame_list: List, result_img_save_path: str, parsing_mode: str):
        """Process video frames in parallel thread"""
        idx = 0
        total_frames = len(frame_paths)
        model_logger.info(f"Starting video frame processor thread for {total_frames} frames")
        
        while idx < total_frames:
            try:
                # Get frame from queue with timeout
                res_frame = res_frame_queue.get(block=True, timeout=1)
            except queue.Empty:
                continue
            
            # Handle missing face detections
            if idx >= len(coord_list) or coord_list[idx] == coord_placeholder:
                # Use original frame if no face detected
                model_logger.warning(f"No face detected in frame {idx}, using original")
                original_frame = cv2.imread(frame_paths[idx])
                cv2.imwrite(f"{result_img_save_path}/{str(idx).zfill(8)}.png", original_frame)
                idx += 1
                continue
            
            # Get coordinates and original frame
            bbox = coord_list[idx]
            ori_frame = frame_list[idx] if idx < len(frame_list) else cv2.imread(frame_paths[idx])
            x1, y1, x2, y2 = bbox
            
            try:
                # Resize generated frame to match bbox
                res_frame = cv2.resize(res_frame.astype(np.uint8), (x2 - x1, y2 - y1))
            except Exception as e:
                model_logger.warning(f"Failed to resize frame {idx}: {str(e)}")
                # Use original frame on resize failure
                cv2.imwrite(f"{result_img_save_path}/{str(idx).zfill(8)}.png", ori_frame)
                idx += 1
                continue
            
            # Blend with original frame
            combine_frame = get_image(ori_frame, res_frame, bbox, mode=parsing_mode, fp=self.face_parser)
            
            # Save frame
            cv2.imwrite(f"{result_img_save_path}/{str(idx).zfill(8)}.png", combine_frame)
            
            idx += 1
            
            if idx % 50 == 0:
                model_logger.debug(f"Processed {idx}/{total_frames} video frames")
        
        model_logger.info(f"Video frame processor thread completed - processed {idx} frames")
    
    def generate_video_to_video(self, video_path: str, audio_path: str, output_path: str,
                               bbox_shift: int = settings.DEFAULT_BBOX_SHIFT,
                               fps: int = settings.DEFAULT_FPS,
                               batch_size: int = settings.VIDEO_BATCH_SIZE,
                               start_time: float = 0,
                               end_time: Optional[float] = None) -> dict:
        """Generate talking head video from input video"""
        try:
            if not self.models_loaded:
                if not self.load_models():
                    return {
                        'status': 'error',
                        'message': 'Failed to load models'
                    }
            
            model_logger.info(f"Generating video-to-video: {video_path} + {audio_path} -> {output_path}")
            model_logger.info(f"Parameters: start={start_time}s, end={end_time}s, fps={fps}, batch_size={batch_size}")
            
            # Create temporary directory for frames
            temp_dir = tempfile.mkdtemp(prefix="musetalk_video_")
            frames_dir = os.path.join(temp_dir, "frames")
            output_frames_dir = os.path.join(temp_dir, "output_frames")
            os.makedirs(frames_dir, exist_ok=True)
            os.makedirs(output_frames_dir, exist_ok=True)
            
            try:
                # Extract frames from video
                model_logger.info(f"Extracting frames at {settings.VIDEO_EXTRACT_FPS} FPS...")
                frame_paths = extract_frames(
                    video_path,
                    frames_dir,
                    extract_fps=settings.VIDEO_EXTRACT_FPS,
                    start_time=start_time,
                    end_time=end_time,
                    max_frames=settings.VIDEO_FRAME_BUFFER_SIZE * 3  # Extract more, process in batches
                )
                
                if not frame_paths:
                    return {
                        'status': 'error',
                        'message': 'Failed to extract frames from video'
                    }
                
                model_logger.info(f"Extracted {len(frame_paths)} frames")
                
                # Process frames in batches to manage memory
                all_coord_lists = []
                all_frame_lists = []
                all_input_latents = []
                
                # Version-specific parameters
                if settings.MUSETALK_VERSION == "v15":
                    extra_margin = 10
                    parsing_mode = "jaw"
                else:
                    extra_margin = 0
                    parsing_mode = "raw"
                
                # Process frames in chunks for face detection
                chunk_size = settings.VIDEO_FRAME_BUFFER_SIZE
                for i in range(0, len(frame_paths), chunk_size):
                    chunk_paths = frame_paths[i:i+chunk_size]
                    model_logger.info(f"Processing face detection for frames {i} to {min(i+chunk_size, len(frame_paths))}")
                    
                    # Get landmarks and bounding boxes for chunk with caching
                    coord_list, frame_list = self.get_face_data_cached(chunk_paths, bbox_shift)
                    
                    # Process VAE latents for valid faces
                    chunk_latents = []
                    for idx, (bbox, frame) in enumerate(zip(coord_list, frame_list)):
                        if bbox == coord_placeholder:
                            chunk_latents.append(None)  # Mark as no face
                            continue
                        
                        x1, y1, x2, y2 = bbox
                        if settings.MUSETALK_VERSION == "v15":
                            y2 = y2 + extra_margin
                            y2 = min(y2, frame.shape[0])
                            coord_list[idx] = [x1, y1, x2, y2]
                        
                        crop_frame = frame[y1:y2, x1:x2]
                        resized_crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                        latents = self.vae.get_latents_for_unet(resized_crop_frame)
                        chunk_latents.append(latents)
                    
                    all_coord_lists.extend(coord_list)
                    all_frame_lists.extend(frame_list)
                    all_input_latents.extend(chunk_latents)
                
                # Filter out frames without faces for processing
                valid_indices = [i for i, latent in enumerate(all_input_latents) if latent is not None]
                
                if not valid_indices:
                    model_logger.error("No valid faces found in any video frames")
                    return {
                        'status': 'error',
                        'message': 'No faces detected in the video frames'
                    }
                
                model_logger.info(f"Found {len(valid_indices)} frames with valid faces out of {len(frame_paths)} total")
                
                # Get only valid latents for processing
                valid_latents = [all_input_latents[i] for i in valid_indices]
                
                # Process audio
                model_logger.info(f"Processing audio: {audio_path}")
                weight_dtype = self.unet.model.dtype
                whisper_input_features, librosa_length = self.audio_processor.get_audio_feature(audio_path, weight_dtype=weight_dtype)
                
                whisper_chunks = self.audio_processor.get_whisper_chunk(
                    whisper_input_features,
                    self.device,
                    weight_dtype,
                    self.whisper,
                    librosa_length,
                    fps=settings.VIDEO_EXTRACT_FPS,  # Use extraction FPS
                    audio_padding_length_left=2,
                    audio_padding_length_right=2,
                )
                
                video_num = min(len(whisper_chunks), len(frame_paths))
                model_logger.info(f"Generating {video_num} frames using video approach...")
                
                # Create queue for realtime frame processing
                res_frame_queue = queue.Queue()
                
                # Start frame processor thread
                process_thread = threading.Thread(
                    target=self.process_video_frames,
                    args=(res_frame_queue, frame_paths, all_coord_lists, all_frame_lists,
                          output_frames_dir, parsing_mode)
                )
                process_thread.start()
                
                # Generate frames with smaller batch size for video
                # Cycle through valid latents if needed
                if len(valid_latents) < video_num:
                    # Repeat latents to match video length
                    repeat_count = (video_num // len(valid_latents)) + 1
                    extended_latents = valid_latents * repeat_count
                    extended_latents = extended_latents[:video_num]
                else:
                    extended_latents = valid_latents[:video_num]
                
                # Adjust whisper chunks to match
                whisper_chunks = whisper_chunks[:video_num]
                
                gen = datagen(whisper_chunks, extended_latents, batch_size, device=self.device)
                timesteps = torch.tensor([0], device=self.device)
                
                start_gen_time = time.time()
                frames_generated = 0
                
                for whisper_batch, latent_batch in gen:
                    audio_feature_batch = self.pe(whisper_batch.to(self.device))
                    latent_batch = latent_batch.to(device=self.device, dtype=self.unet.model.dtype)
                    
                    pred_latents = self.unet.model(
                        latent_batch,
                        timesteps,
                        encoder_hidden_states=audio_feature_batch
                    ).sample
                    
                    pred_latents = pred_latents.to(device=self.device, dtype=self.vae.vae.dtype)
                    recon = self.vae.decode_latents(pred_latents)
                    
                    # Put frames in queue for processing
                    for res_frame in recon:
                        res_frame_queue.put(res_frame)
                        frames_generated += 1
                    
                    # Clean up VRAM periodically
                    if frames_generated % 100 == 0:
                        torch.cuda.empty_cache()
                
                # Wait for processor thread to complete
                process_thread.join()
                
                generation_time = time.time() - start_gen_time
                model_logger.info(f"Video generation completed: {frames_generated} frames in {generation_time:.2f}s")
                
                # Create output video from processed frames
                model_logger.info("Creating output video from frames...")
                success = create_video_from_frames(
                    output_frames_dir,
                    output_path,
                    fps=settings.VIDEO_EXTRACT_FPS,
                    audio_path=audio_path
                )
                
                if not success:
                    return {
                        'status': 'error',
                        'message': 'Failed to create output video from frames'
                    }
                
                model_logger.info(f"Video saved to: {output_path}")
                
                # Clean up VRAM after successful generation
                self._cleanup_vram()
                
                return {
                    'status': 'success',
                    'output_path': output_path,
                    'frames_generated': frames_generated,
                    'frames_with_faces': len(valid_indices),
                    'total_frames': len(frame_paths)
                }
                
            finally:
                # Clean up temporary directory
                if settings.TEMP_FRAME_CLEANUP and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    model_logger.info(f"Cleaned up temporary directory: {temp_dir}")
                    
        except Exception as e:
            model_logger.error(f"Error generating video-to-video: {str(e)}")
            import traceback
            model_logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            # Clean up VRAM even on failure
            self._cleanup_vram()
            
            return {
                'status': 'error',
                'message': str(e)
            }
    
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
        
        # Add cache statistics
        if self.face_cache:
            health_data['face_cache'] = self.face_cache.get_statistics()
        
        if self.realtime_cache:
            health_data['realtime_cache'] = self.realtime_cache.get_statistics()
        
        return health_data