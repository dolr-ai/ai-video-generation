import os
import cv2
import torch
import numpy as np
import logging
import subprocess
from tqdm import tqdm
import shutil
import glob

from musetalk.utils.utils import get_file_type, get_video_fps, datagen
from musetalk.utils.preprocessing import get_landmark_and_bbox, read_imgs, coord_placeholder
from musetalk.utils.blending import get_image

from service.config.settings import Config

logger = logging.getLogger(__name__)

class InferenceHandler:
    def __init__(self, vae, unet, pe, whisper, audio_processor, face_parser, device):
        self.vae = vae
        self.unet = unet
        self.pe = pe
        self.whisper = whisper
        self.audio_processor = audio_processor
        self.face_parser = face_parser
        self.device = device
        self.timesteps = torch.tensor([0], device=device)
        
    @torch.no_grad()
    def generate(self, video_path, audio_path, output_dir, bbox_shift=0, 
                fps=25, batch_size=8, script=None):
        """Generate talking head video using normal inference"""
        try:
            weight_dtype = self.unet.model.dtype
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Get input names
            input_basename = os.path.basename(video_path).split('.')[0]
            audio_basename = os.path.basename(audio_path).split('.')[0]
            output_vid_name = f"{input_basename}_{audio_basename}"
            
            # Result paths
            result_img_save_path = os.path.join(output_dir, output_vid_name)
            os.makedirs(result_img_save_path, exist_ok=True)
            
            # Process input video/image
            if get_file_type(video_path) == "video":
                logger.info("Processing video input")
                save_dir_full = os.path.join(output_dir, "full_imgs")
                os.makedirs(save_dir_full, exist_ok=True)
                
                # Extract frames
                cmd = f"ffmpeg -i {video_path} -start_number 0 {save_dir_full}/%08d.png -loglevel error"
                subprocess.run(cmd, shell=True, check=True)
                input_img_list = sorted(glob.glob(os.path.join(save_dir_full, '*.png')))
            else:
                logger.info("Processing image input")
                input_img_list = [video_path]
            
            # Get video FPS
            if get_file_type(video_path) == "video":
                fps = get_video_fps(video_path)
                logger.info(f"Video FPS: {fps}")
            else:
                fps = Config.DEFAULT_FPS
                
            # Process audio
            logger.info("Processing audio...")
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
            
            # Get face coordinates and frames
            logger.info("Detecting faces and landmarks...")
            coord_list, frame_list = get_landmark_and_bbox(input_img_list, bbox_shift)
            
            # Prepare VAE latents for each frame
            logger.info("Preparing VAE latents...")
            input_latent_list = []
            coord_placeholder = (0.0, 0.0, 0.0, 0.0)
            
            # Version-specific parameters
            if Config.MUSETALK_VERSION == "v15":
                extra_margin = 10
                parsing_mode = "jaw"
            else:
                extra_margin = 0  
                parsing_mode = "raw"
            
            for idx, (bbox, frame) in enumerate(zip(coord_list, frame_list)):
                if bbox == coord_placeholder:
                    continue
                x1, y1, x2, y2 = bbox
                if Config.MUSETALK_VERSION == "v15":
                    y2 = y2 + extra_margin
                    y2 = min(y2, frame.shape[0])
                    coord_list[idx] = [x1, y1, x2, y2]  # Update bbox
                crop_frame = frame[y1:y2, x1:x2]
                resized_crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                latents = self.vae.get_latents_for_unet(resized_crop_frame)
                input_latent_list.append(latents)
            
            # Create cyclic list for looping
            input_latent_list_cycle = input_latent_list + input_latent_list[::-1]
            coord_list_cycle = coord_list + coord_list[::-1]
            frame_list_cycle = frame_list + frame_list[::-1]
            
            # Create data generator
            logger.info("Generating frames...")
            gen = datagen(whisper_chunks, input_latent_list_cycle, batch_size, device=self.device)
            
            video_num = len(whisper_chunks)
            res_frame_list = []
            
            for i, (whisper_batch, latent_batch) in enumerate(tqdm(gen, total=int(np.ceil(float(video_num) / batch_size)))):
                audio_feature_batch = self.pe(whisper_batch.to(self.device))
                latent_batch = latent_batch.to(device=self.device, dtype=self.unet.model.dtype)

                pred_latents = self.unet.model(latent_batch,
                                        self.timesteps,
                                        encoder_hidden_states=audio_feature_batch).sample
                pred_latents = pred_latents.to(device=self.device, dtype=self.vae.vae.dtype)
                recon = self.vae.decode_latents(pred_latents)
                for res_frame in recon:
                    res_frame_list.append(res_frame)
            
            # Save frames and create video
            logger.info("Saving frames...")
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
            
            # Create output video
            logger.info("Creating output video...")
            output_video_path = os.path.join(output_dir, f"{output_vid_name}.mp4")
            
            # Use ffmpeg to create video
            cmd_video = f"ffmpeg -y -framerate {fps} -i {result_img_save_path}/%08d.png -c:v libx264 -pix_fmt yuv420p -preset superfast {output_video_path}.tmp.mp4 -loglevel error"
            subprocess.run(cmd_video, shell=True, check=True)
            
            # Add audio
            cmd_audio = f"ffmpeg -y -i {output_video_path}.tmp.mp4 -i {audio_path} -c:v copy -c:a aac -map 0:v -map 1:a -shortest {output_video_path} -loglevel error"
            subprocess.run(cmd_audio, shell=True, check=True)
            
            # Clean up temp file
            if os.path.exists(f"{output_video_path}.tmp.mp4"):
                os.remove(f"{output_video_path}.tmp.mp4")
            
            logger.info(f"Video saved to: {output_video_path}")
            
            return {
                'status': 'success',
                'output_path': output_video_path,
                'frames_generated': len(res_frame_list)
            }
            
        except Exception as e:
            logger.error(f"Error in inference: {str(e)}")
            raise