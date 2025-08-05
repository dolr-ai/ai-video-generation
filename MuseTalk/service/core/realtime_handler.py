import os
import cv2
import torch
import numpy as np
import logging
import subprocess
import pickle
import json
import shutil
from tqdm import tqdm

from musetalk.utils.utils import get_file_type, datagen
from musetalk.utils.preprocessing import get_landmark_and_bbox, read_imgs, coord_placeholder
from musetalk.utils.blending import get_image_prepare_material, get_image_blending

from service.config.settings import Config

logger = logging.getLogger(__name__)

class RealtimeHandler:
    def __init__(self, vae, unet, pe, whisper, audio_processor, face_parser, device):
        self.vae = vae
        self.unet = unet
        self.pe = pe
        self.whisper = whisper
        self.audio_processor = audio_processor
        self.face_parser = face_parser
        self.device = device
        self.timesteps = torch.tensor([0], device=device)
        
    def _video2imgs(self, vid_path, save_path, ext='.png', cut_frame=10000000):
        """Extract frames from video"""
        os.makedirs(save_path, exist_ok=True)
        cap = cv2.VideoCapture(vid_path)
        count = 0
        while True:
            if count > cut_frame:
                break
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(f"{save_path}/{count:08d}.png", frame)
                count += 1
            else:
                break
        cap.release()
        return count
        
    @torch.no_grad()
    def prepare_avatar(self, avatar_id, video_path, bbox_shift=0):
        """Prepare avatar materials for real-time inference"""
        try:
            # Create avatar directories
            if Config.MUSETALK_VERSION == "v15":
                avatar_path = f"./results/{Config.MUSETALK_VERSION}/avatars/{avatar_id}"
            else:
                avatar_path = f"./results/avatars/{avatar_id}"
                
            full_imgs_path = f"{avatar_path}/full_imgs"
            coords_path = f"{avatar_path}/coords.pkl"
            latents_out_path = f"{avatar_path}/latents.pt"
            mask_out_path = f"{avatar_path}/mask"
            mask_coords_path = f"{avatar_path}/mask_coords.pkl"
            avatar_info_path = f"{avatar_path}/avatar_info.json"
            
            os.makedirs(avatar_path, exist_ok=True)
            os.makedirs(full_imgs_path, exist_ok=True)
            os.makedirs(mask_out_path, exist_ok=True)
            
            # Extract frames from video
            logger.info(f"Extracting frames for avatar {avatar_id}")
            if get_file_type(video_path) == "video":
                self._video2imgs(video_path, full_imgs_path)
            else:
                # Single image
                shutil.copy(video_path, os.path.join(full_imgs_path, "00000000.png"))
                
            # Read frames
            input_img_list = sorted([os.path.join(full_imgs_path, fname) for fname in os.listdir(full_imgs_path) if fname.endswith('.png')])
            
            # Get landmarks and bbox
            logger.info("Getting landmarks and bounding boxes...")
            coord_list, frame_list = get_landmark_and_bbox(input_img_list, bbox_shift)
            
            # Process frames and get latents
            logger.info("Processing frames and extracting latents...")
            input_latent_list = []
            weight_dtype = self.unet.model.dtype
            
            for i, (bbox, frame) in enumerate(tqdm(zip(coord_list, frame_list))):
                if bbox == coord_placeholder:
                    continue
                    
                x1, y1, x2, y2 = bbox
                
                # Version-specific adjustments
                if Config.MUSETALK_VERSION == "v15":
                    y2 = y2 + 10  # extra margin
                    y2 = min(y2, frame.shape[0])
                    
                # Crop and resize
                crop_frame = frame[y1:y2, x1:x2]
                crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                
                # Get latents
                latents = self.vae.get_latents_for_unet(crop_frame)
                latents = latents.to(dtype=weight_dtype)
                input_latent_list.append(latents.unsqueeze(0))
                
            # Prepare material
            if Config.MUSETALK_VERSION == "v15":
                mask_coords_list, mask_list, face_mask_list, lip_mask_list = get_image_prepare_material(
                    coord_list, frame_list, mask_out_path, mask_coords_path, padding=10, face_parser=self.face_parser
                )
            else:
                mask_coords_list, mask_list = get_image_prepare_material(
                    coord_list, frame_list, mask_out_path, mask_coords_path, padding=10, face_parser=self.face_parser
                )
                face_mask_list = None
                lip_mask_list = None
                
            # Create cycled latents
            input_latent_list_cycle = torch.cat(input_latent_list + input_latent_list[::-1], dim=0)
            
            # Save avatar data
            torch.save(input_latent_list_cycle, latents_out_path)
            with open(coords_path, 'wb') as f:
                pickle.dump(coord_list, f)
                
            # Save avatar info
            avatar_info = {
                "avatar_id": avatar_id,
                "video_path": video_path,
                "bbox_shift": bbox_shift,
                "version": Config.MUSETALK_VERSION,
                "num_frames": len(input_img_list)
            }
            with open(avatar_info_path, 'w') as f:
                json.dump(avatar_info, f, indent=4)
                
            logger.info(f"Avatar {avatar_id} prepared successfully")
            
            return {
                'avatar_path': avatar_path,
                'input_latent_list_cycle': input_latent_list_cycle,
                'coord_list': coord_list,
                'frame_list': frame_list,
                'mask_coords_list': mask_coords_list,
                'mask_list': mask_list,
                'face_mask_list': face_mask_list,
                'lip_mask_list': lip_mask_list
            }
            
        except Exception as e:
            logger.error(f"Error preparing avatar: {str(e)}")
            raise
            
    @torch.no_grad()
    def generate_single(self, image_path, audio_path, output_dir, bbox_shift=0, fps=25, batch_size=8):
        """Generate single talking head video using real-time inference"""
        try:
            # Create temporary avatar
            import uuid
            temp_avatar_id = f"temp_{uuid.uuid4().hex[:8]}"
            
            # Prepare avatar
            avatar_data = self.prepare_avatar(temp_avatar_id, image_path, bbox_shift)
            
            # Generate with audio
            results = self.generate_with_prepared_avatar(
                avatar_data=avatar_data,
                audio_clips=[audio_path],
                output_dir=output_dir,
                fps=fps,
                batch_size=batch_size
            )
            
            # Clean up temporary avatar
            if os.path.exists(avatar_data['avatar_path']):
                shutil.rmtree(avatar_data['avatar_path'])
                
            if results:
                return {
                    'status': 'success',
                    'output_path': results[0]['output_path']
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Failed to generate video'
                }
                
        except Exception as e:
            logger.error(f"Error in single real-time generation: {str(e)}")
            raise
            
    def generate_with_avatar(self, avatar_id, video_path, audio_clips, preparation=True, bbox_shift=0, output_dir=None):
        """Generate talking heads with avatar"""
        try:
            # Check if avatar exists
            if Config.MUSETALK_VERSION == "v15":
                avatar_path = f"./results/{Config.MUSETALK_VERSION}/avatars/{avatar_id}"
            else:
                avatar_path = f"./results/avatars/{avatar_id}"
                
            avatar_exists = os.path.exists(avatar_path)
            
            if preparation or not avatar_exists:
                # Prepare avatar
                logger.info(f"Preparing avatar {avatar_id}")
                avatar_data = self.prepare_avatar(avatar_id, video_path, bbox_shift)
            else:
                # Load existing avatar
                logger.info(f"Loading existing avatar {avatar_id}")
                avatar_data = self._load_avatar(avatar_id)
                
            # Generate videos for each audio clip
            results = self.generate_with_prepared_avatar(
                avatar_data=avatar_data,
                audio_clips=audio_clips,
                output_dir=output_dir or avatar_path,
                batch_size=Config.DEFAULT_BATCH_SIZE,
                fps=Config.DEFAULT_FPS
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error generating with avatar: {str(e)}")
            raise
            
    def _load_avatar(self, avatar_id):
        """Load existing avatar data"""
        if Config.MUSETALK_VERSION == "v15":
            avatar_path = f"./results/{Config.MUSETALK_VERSION}/avatars/{avatar_id}"
        else:
            avatar_path = f"./results/avatars/{avatar_id}"
            
        # Load data
        latents_out_path = f"{avatar_path}/latents.pt"
        coords_path = f"{avatar_path}/coords.pkl"
        mask_out_path = f"{avatar_path}/mask"
        mask_coords_path = f"{avatar_path}/mask_coords.pkl"
        full_imgs_path = f"{avatar_path}/full_imgs"
        
        input_latent_list_cycle = torch.load(latents_out_path)
        
        with open(coords_path, 'rb') as f:
            coord_list = pickle.load(f)
            
        with open(mask_coords_path, 'rb') as f:
            mask_coords_list = pickle.load(f)
            
        # Read frames
        frame_list = read_imgs(full_imgs_path)
        
        # Load masks
        mask_list = []
        face_mask_list = []
        lip_mask_list = []
        
        for i in range(len(coord_list)):
            mask_path = os.path.join(mask_out_path, f"{i:05d}.png")
            if os.path.exists(mask_path):
                mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
                mask_list.append(mask)
                
            if Config.MUSETALK_VERSION == "v15":
                face_mask_path = os.path.join(mask_out_path, f"{i:05d}_face.png")
                lip_mask_path = os.path.join(mask_out_path, f"{i:05d}_lip.png")
                
                if os.path.exists(face_mask_path):
                    face_mask = cv2.imread(face_mask_path, cv2.IMREAD_GRAYSCALE)
                    face_mask_list.append(face_mask)
                    
                if os.path.exists(lip_mask_path):
                    lip_mask = cv2.imread(lip_mask_path, cv2.IMREAD_GRAYSCALE)
                    lip_mask_list.append(lip_mask)
                    
        return {
            'avatar_path': avatar_path,
            'input_latent_list_cycle': input_latent_list_cycle,
            'coord_list': coord_list,
            'frame_list': frame_list,
            'mask_coords_list': mask_coords_list,
            'mask_list': mask_list,
            'face_mask_list': face_mask_list if face_mask_list else None,
            'lip_mask_list': lip_mask_list if lip_mask_list else None
        }
        
    @torch.no_grad()
    def generate_with_prepared_avatar(self, avatar_data, audio_clips, output_dir, batch_size=8, fps=25):
        """Generate videos using prepared avatar data"""
        results = []
        weight_dtype = self.unet.model.dtype
        
        for audio_idx, audio_path in enumerate(audio_clips):
            try:
                logger.info(f"Processing audio clip {audio_idx + 1}/{len(audio_clips)}: {audio_path}")
                
                # Process audio
                whisper_feature = self.audio_processor.audio2feat(audio_path)
                whisper_chunks = self.audio_processor.feature2chunks(feature_array=whisper_feature, fps=fps)
                
                # Prepare audio features
                audio_feat_list = []
                for i in range(len(whisper_chunks)):
                    audio_list = []
                    for whisper_chunk in whisper_chunks[i]:
                        audio_list.append(whisper_chunk)
                    audio_feat = torch.from_numpy(np.array(audio_list, dtype=np.float32)).to(device=self.device, dtype=weight_dtype)
                    audio_feat = self.pe(audio_feat).to(dtype=weight_dtype)
                    audio_feat_list.append(audio_feat)
                    
                # Generate frames
                res_latents_list = []
                latent_idx = 0
                
                for i, audio_feat_batch in enumerate(tqdm(audio_feat_list)):
                    audio_feat_batch = audio_feat_batch.unsqueeze(0)
                    
                    for j in range(audio_feat_batch.shape[1]):
                        input_latent = avatar_data['input_latent_list_cycle'][latent_idx % len(avatar_data['input_latent_list_cycle'])]
                        audio_feat_frame = audio_feat_batch[:, j:j+1]
                        
                        pred_latents = self.unet.model(input_latent, self.timesteps, encoder_hidden_states=audio_feat_frame).sample
                        res_latents_list.append(pred_latents)
                        
                        latent_idx += 1
                        
                # Decode latents and create video
                audio_name = os.path.basename(audio_path).split('.')[0]
                output_video_path = os.path.join(output_dir, f"output_{audio_name}.mp4")
                temp_frames_dir = os.path.join(output_dir, f"temp_frames_{audio_name}")
                os.makedirs(temp_frames_dir, exist_ok=True)
                
                # Decode frames
                for i, res_latents in enumerate(res_latents_list):
                    res_frame = self.vae.decode_latents(res_latents)
                    res_frame = res_frame[0]
                    
                    # Get corresponding coordinates and masks
                    frame_idx = i % len(avatar_data['coord_list'])
                    coord = avatar_data['coord_list'][frame_idx]
                    frame = avatar_data['frame_list'][frame_idx]
                    
                    if coord != coord_placeholder:
                        x1, y1, x2, y2 = coord
                        
                        if Config.MUSETALK_VERSION == "v15":
                            y2 = y2 + 10
                            y2 = min(y2, frame.shape[0])
                            
                        # Resize and blend
                        res_frame = cv2.resize(res_frame.astype(np.uint8), (x2-x1, y2-y1))
                        
                        if avatar_data['face_mask_list'] is not None and avatar_data['lip_mask_list'] is not None:
                            # v15 blending
                            frame = get_image_blending(
                                frame, res_frame, coord,
                                avatar_data['mask_list'][frame_idx],
                                avatar_data['face_mask_list'][frame_idx],
                                avatar_data['lip_mask_list'][frame_idx],
                                mask_coords=avatar_data['mask_coords_list'][frame_idx]
                            )
                        else:
                            # v1 blending
                            frame = get_image_blending(
                                frame, res_frame, coord,
                                avatar_data['mask_list'][frame_idx],
                                mask_coords=avatar_data['mask_coords_list'][frame_idx]
                            )
                            
                    # Save frame
                    frame_path = os.path.join(temp_frames_dir, f"{i:08d}.png")
                    cv2.imwrite(frame_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                    
                # Create video
                cmd_video = f"ffmpeg -y -framerate {fps} -i {temp_frames_dir}/%08d.png -c:v libx264 -pix_fmt yuv420p -preset superfast {output_video_path}.tmp.mp4 -loglevel error"
                subprocess.run(cmd_video, shell=True, check=True)
                
                # Add audio
                cmd_audio = f"ffmpeg -y -i {output_video_path}.tmp.mp4 -i {audio_path} -c:v copy -c:a aac -map 0:v -map 1:a -shortest {output_video_path} -loglevel error"
                subprocess.run(cmd_audio, shell=True, check=True)
                
                # Clean up
                if os.path.exists(f"{output_video_path}.tmp.mp4"):
                    os.remove(f"{output_video_path}.tmp.mp4")
                if os.path.exists(temp_frames_dir):
                    shutil.rmtree(temp_frames_dir)
                    
                results.append({
                    'audio_path': audio_path,
                    'output_path': output_video_path,
                    'status': 'success'
                })
                
                logger.info(f"Generated video: {output_video_path}")
                
            except Exception as e:
                logger.error(f"Error processing audio {audio_path}: {str(e)}")
                results.append({
                    'audio_path': audio_path,
                    'status': 'error',
                    'message': str(e)
                })
                
        return results