"""
Wrapper for MuseTalk preprocessing to handle path issues without modifying original code
"""
import os
import sys
import torch
import numpy as np
import cv2
from typing import List, Tuple, Any

from config.settings import settings

class PreprocessingWrapper:
    """Wrapper class to handle MuseTalk preprocessing with correct paths"""
    
    def __init__(self):
        self.model = None
        self.fa = None
        self.coord_placeholder = (0.0, 0.0, 0.0, 0.0)
        self._initialized = False
        
    def initialize(self):
        """Initialize models with correct paths"""
        if self._initialized:
            return
            
        # Save current directory
        original_dir = os.getcwd()
        
        try:
            # Change to MuseTalk directory for initialization
            os.chdir(settings.MUSETALK_DIR)
            
            # Now import the modules (they will initialize with correct paths)
            from face_detection import FaceAlignment, LandmarksType
            from mmpose.apis import inference_topdown, init_model
            
            # Initialize the mmpose model
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            config_file = './musetalk/utils/dwpose/rtmpose-l_8xb32-270e_coco-ubody-wholebody-384x288.py'
            checkpoint_file = './models/dwpose/dw-ll_ucoco_384.pth'
            self.model = init_model(config_file, checkpoint_file, device=device)
            
            # Initialize the face detection model (needs string device, not torch.device)
            device_str = "cuda" if torch.cuda.is_available() else "cpu"
            self.fa = FaceAlignment(LandmarksType._2D, flip_input=False, device=device_str)
            
            # Store the functions we need
            from musetalk.utils import preprocessing
            self._preprocessing_module = preprocessing
            
            self._initialized = True
            
        finally:
            # Always restore original directory
            os.chdir(original_dir)
    
    def read_imgs(self, img_list: List[str]) -> List[np.ndarray]:
        """Read images from file paths"""
        if not self._initialized:
            self.initialize()
            
        original_dir = os.getcwd()
        try:
            os.chdir(settings.MUSETALK_DIR)
            return self._preprocessing_module.read_imgs(img_list)
        finally:
            os.chdir(original_dir)
    
    def get_landmark_and_bbox(self, img_list: List[np.ndarray], bbox_shift: int = 0) -> Tuple[List, List]:
        """Get landmarks and bounding boxes from images"""
        if not self._initialized:
            self.initialize()
            
        original_dir = os.getcwd()
        try:
            os.chdir(settings.MUSETALK_DIR)
            return self._preprocessing_module.get_landmark_and_bbox(img_list, bbox_shift)
        finally:
            os.chdir(original_dir)
    
    def get_video_landmark(self, path: str, bbox_shift: int = 0, start_idx: int = 0, 
                          stop_idx: int = None, extract_from_start: bool = True) -> Tuple[List, List, str]:
        """Extract landmarks from video"""
        if not self._initialized:
            self.initialize()
            
        original_dir = os.getcwd()
        try:
            os.chdir(settings.MUSETALK_DIR)
            return self._preprocessing_module.get_video_landmark(
                path, bbox_shift, start_idx, stop_idx, extract_from_start
            )
        finally:
            os.chdir(original_dir)

# Global instance
preprocessing_wrapper = PreprocessingWrapper()