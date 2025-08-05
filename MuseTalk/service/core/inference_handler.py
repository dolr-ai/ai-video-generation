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
            whisper_feature = self.audio_processor.audio2feat(audio_path)
            whisper_chunks = self.audio_processor.feature2chunks(feature_array=whisper_feature, fps=fps)
            
            # Get face coordinates and frames
            logger.info("Detecting faces and landmarks...")
            coord_list, frame_list = get_landmark_and_bbox(input_img_list, bbox_shift)
            
            # Process audio features
            audio_feat_list = []
            for audio_idx in range(len(whisper_chunks)):
                # Process whisper chunks
                audio_list = []
                for whisper_chunk in whisper_chunks[audio_idx]:
                    audio_list.append(whisper_chunk)
                audio_feat = torch.from_numpy(np.array(audio_list, dtype=np.float32)).to(device=self.device, dtype=weight_dtype)
                audio_feat = self.pe(audio_feat).to(dtype=weight_dtype)
                audio_feat_list.append(audio_feat)
                
            # Create data generator
            logger.info("Creating data generator...")
            gen = datagen(
                whisper_chunks,
                coord_list,
                frame_list,
                batch_size,
                os.path.join(output_dir, "mask"),
                os.path.join(output_dir, "mask_coords.pkl")
            )
            
            # Process batches
            logger.info("Generating frames...")
            res_frame_list = []
            frame_idx = 0
            
            # Version-specific parameters
            if Config.MUSETALK_VERSION == "v15":
                extra_margin = 10
                parsing_mode = "jaw"
            else:
                extra_margin = 0
                parsing_mode = "full"
            
            for i, (whisper_batch, coord_batch, frame_batch) in enumerate(tqdm(gen, total=int(np.ceil(len(whisper_chunks) / batch_size)))):
                if coord_batch.shape[1] == 0:
                    continue
                    
                audio_feat_batch = audio_feat_list[i]
                audio_feat_batch = audio_feat_batch.unsqueeze(0).repeat(coord_batch.shape[0], 1, 1, 1).reshape(-1, audio_feat_batch.shape[-2], audio_feat_batch.shape[-1])
                
                # Process each frame in batch
                for j in range(coord_batch.shape[0]):
                    coords = coord_batch[j]
                    
                    for k in range(coords.shape[0]):
                        y1, y2, x1, x2 = coords[k].tolist()
                        
                        # Skip if invalid coordinates
                        if y1 == -1:
                            if len(res_frame_list) > frame_idx:
                                frame = res_frame_list[frame_idx].copy()
                            else:
                                frame = frame_batch[j][k].copy()
                        else:
                            frame = frame_batch[j][k]
                            y2 = y2 + extra_margin
                            y2 = min(y2, frame.shape[0])
                            
                            # Crop and resize
                            crop_frame = frame[y1:y2, x1:x2]
                            if crop_frame.shape[0] == 0 or crop_frame.shape[1] == 0:
                                logger.warning(f"Invalid crop dimensions at frame {frame_idx}")
                                continue
                                
                            crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                            
                            # Get latents
                            latents = self.vae.get_latents_for_unet(crop_frame)
                            latents = latents.to(dtype=weight_dtype)
                            
                            # Model prediction
                            audio_feat_frame = audio_feat_batch[k].unsqueeze(0)
                            pred_latents = self.unet.model(latents.unsqueeze(0), self.timesteps, encoder_hidden_states=audio_feat_frame).sample
                            recon = self.vae.decode_latents(pred_latents)
                            
                            # Blend back to original
                            recon_frame = recon[0]
                            recon_frame = cv2.resize(recon_frame.astype(np.uint8), (x2-x1, y2-y1))
                            frame = get_image(frame, recon_frame, [x1, y1, x2, y2], mode=parsing_mode, fp=self.face_parser)
                        
                        # Save frame
                        frame_filename = f"{frame_idx:08d}.png"
                        frame_path = os.path.join(result_img_save_path, frame_filename)
                        cv2.imwrite(frame_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                        
                        if frame_idx == 0 or len(res_frame_list) <= frame_idx:
                            res_frame_list.append(frame)
                        else:
                            res_frame_list[frame_idx] = frame
                        frame_idx += 1
            
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
                'frames_generated': frame_idx
            }
            
        except Exception as e:
            logger.error(f"Error in inference: {str(e)}")
            raise