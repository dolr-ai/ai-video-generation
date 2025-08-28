import os
import cv2
import logging
import subprocess
import tempfile
import shutil
from typing import Optional, Tuple, List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

def get_video_info(video_path: str) -> Optional[Dict]:
    """
    Get comprehensive information about a video file
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary with video information or None if error
    """
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video: {video_path}")
            return None
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        return {
            'width': width,
            'height': height,
            'fps': fps,
            'frame_count': frame_count,
            'duration': duration,
            'aspect_ratio': round(width / height, 2) if height > 0 else 0,
            'needs_resize': max(width, height) > 1080,
            'file_size': os.path.getsize(video_path),
            'megapixels': round((width * height) / 1_000_000, 2)
        }
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return None

def extract_frames(video_path: str, output_dir: str, 
                  extract_fps: int = 10, 
                  start_time: float = 0, 
                  end_time: Optional[float] = None,
                  max_frames: Optional[int] = None) -> List[str]:
    """
    Extract frames from video at specified FPS
    
    Args:
        video_path: Path to input video
        output_dir: Directory to save extracted frames
        extract_fps: FPS for frame extraction (lower = fewer frames)
        start_time: Start time in seconds
        end_time: End time in seconds (None = until end)
        max_frames: Maximum number of frames to extract
        
    Returns:
        List of paths to extracted frames
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video: {video_path}")
            return []
        
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = frame_count / video_fps if video_fps > 0 else 0
        
        # Validate time range
        start_time = max(0, start_time)
        if end_time is None or end_time > video_duration:
            end_time = video_duration
        
        # Calculate frame interval
        frame_interval = int(video_fps / extract_fps) if extract_fps < video_fps else 1
        
        # Calculate start and end frames
        start_frame = int(start_time * video_fps)
        end_frame = int(end_time * video_fps)
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        extracted_frames = []
        frame_idx = start_frame
        extracted_count = 0
        
        logger.info(f"Extracting frames from {start_time:.1f}s to {end_time:.1f}s at {extract_fps} FPS")
        logger.info(f"Frame interval: {frame_interval}, Total frames to extract: ~{(end_frame - start_frame) // frame_interval}")
        
        while frame_idx < end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Only save frames at the specified interval
            if (frame_idx - start_frame) % frame_interval == 0:
                frame_filename = f"frame_{extracted_count:06d}.jpg"
                frame_path = os.path.join(output_dir, frame_filename)
                cv2.imwrite(frame_path, frame)
                extracted_frames.append(frame_path)
                extracted_count += 1
                
                if max_frames and extracted_count >= max_frames:
                    logger.info(f"Reached max frames limit: {max_frames}")
                    break
            
            frame_idx += 1
            
            # Log progress
            if extracted_count % 50 == 0 and extracted_count > 0:
                logger.info(f"Extracted {extracted_count} frames...")
        
        cap.release()
        
        logger.info(f"Successfully extracted {len(extracted_frames)} frames")
        return extracted_frames
        
    except Exception as e:
        logger.error(f"Error extracting frames: {str(e)}")
        return []

def resize_video(input_path: str, output_path: str, 
                max_dimension: int = 1080, 
                quality: str = "medium") -> bool:
    """
    Resize video to specified maximum dimension while maintaining aspect ratio
    
    Args:
        input_path: Path to input video
        output_path: Path to output video
        max_dimension: Maximum dimension (width or height)
        quality: Encoding quality preset (fast/medium/high)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get video info
        video_info = get_video_info(input_path)
        if not video_info:
            return False
        
        width = video_info['width']
        height = video_info['height']
        
        # Check if resize is needed
        if max(width, height) <= max_dimension:
            logger.info("Video already within size limits, copying original")
            shutil.copy2(input_path, output_path)
            return True
        
        # Calculate new dimensions
        if width > height:
            new_width = max_dimension
            new_height = int(height * (max_dimension / width))
        else:
            new_height = max_dimension
            new_width = int(width * (max_dimension / height))
        
        # Ensure even dimensions for video encoding
        new_width = new_width if new_width % 2 == 0 else new_width - 1
        new_height = new_height if new_height % 2 == 0 else new_height - 1
        
        logger.info(f"Resizing video from {width}x{height} to {new_width}x{new_height}")
        
        # Choose encoding preset based on quality
        preset_map = {
            "fast": "superfast",
            "medium": "medium",
            "high": "slow"
        }
        preset = preset_map.get(quality, "medium")
        
        # Build ffmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", f"scale={new_width}:{new_height}",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", "23",  # Quality factor (lower = better, 23 is default)
            "-c:a", "copy",  # Copy audio without re-encoding
            output_path
        ]
        
        logger.info(f"Running resize command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg resize failed: {result.stderr}")
            return False
        
        logger.info(f"Video resized successfully to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error resizing video: {str(e)}")
        return False

def create_video_from_frames(frame_dir: str, output_path: str, 
                            fps: int = 25, 
                            audio_path: Optional[str] = None) -> bool:
    """
    Create video from a directory of frames
    
    Args:
        frame_dir: Directory containing frame images
        output_path: Path for output video
        fps: Frames per second for output video
        audio_path: Optional audio file to add to video
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if frames exist
        frame_pattern = os.path.join(frame_dir, "*.jpg")
        if not any(Path(frame_dir).glob("*.jpg")) and not any(Path(frame_dir).glob("*.png")):
            logger.error(f"No frames found in {frame_dir}")
            return False
        
        # Determine frame pattern
        if any(Path(frame_dir).glob("*.png")):
            frame_pattern = os.path.join(frame_dir, "%08d.png")
        else:
            frame_pattern = os.path.join(frame_dir, "frame_%06d.jpg")
        
        logger.info(f"Creating video from frames in {frame_dir}")
        
        # Create video without audio first
        temp_video = output_path + ".temp.mp4"
        cmd_video = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", frame_pattern,
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",  # Ensure even dimensions
            "-c:v", "libx264",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            temp_video
        ]
        
        result = subprocess.run(cmd_video, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg video creation failed: {result.stderr}")
            return False
        
        # Add audio if provided
        if audio_path and os.path.exists(audio_path):
            logger.info(f"Adding audio from {audio_path}")
            cmd_audio = [
                "ffmpeg", "-y",
                "-i", temp_video,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v",
                "-map", "1:a",
                "-shortest",  # Match duration to shorter of video/audio
                output_path
            ]
            
            result = subprocess.run(cmd_audio, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"FFmpeg audio addition failed: {result.stderr}")
                # Keep video without audio
                shutil.move(temp_video, output_path)
            else:
                os.remove(temp_video)
        else:
            # No audio, just move temp video to final location
            shutil.move(temp_video, output_path)
        
        logger.info(f"Video created successfully: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating video from frames: {str(e)}")
        return False

def estimate_video_memory(width: int, height: int, 
                         frame_count: int, 
                         batch_size: int = 4) -> float:
    """
    Estimate GPU memory requirements for video processing
    
    Args:
        width: Video width
        height: Video height
        frame_count: Number of frames to process
        batch_size: Processing batch size
        
    Returns:
        Estimated memory in GB
    """
    # Rough estimation based on frame size and batch processing
    bytes_per_pixel = 4  # RGBA
    frame_size_mb = (width * height * bytes_per_pixel) / (1024 * 1024)
    
    # Account for:
    # - Input frames in batch
    # - Model intermediate representations (roughly 4x input)
    # - Output frames
    memory_per_batch_mb = frame_size_mb * batch_size * 6
    
    # Convert to GB
    memory_gb = memory_per_batch_mb / 1024
    
    # Add base model memory (~2GB)
    total_memory_gb = memory_gb + 2.0
    
    return round(total_memory_gb, 2)

def validate_video_for_processing(video_path: str, 
                                 max_duration: int = 60,
                                 max_resolution: int = 1080) -> Dict[str, any]:
    """
    Validate if video is suitable for processing
    
    Args:
        video_path: Path to video file
        max_duration: Maximum allowed duration in seconds
        max_resolution: Maximum allowed resolution
        
    Returns:
        Dictionary with validation results
    """
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'video_info': None
    }
    
    # Get video info
    video_info = get_video_info(video_path)
    if not video_info:
        result['errors'].append("Failed to read video file")
        return result
    
    result['video_info'] = video_info
    
    # Check duration
    if video_info['duration'] > max_duration:
        result['errors'].append(f"Video duration ({video_info['duration']:.1f}s) exceeds maximum ({max_duration}s)")
    
    # Check resolution
    max_dim = max(video_info['width'], video_info['height'])
    if max_dim > max_resolution * 2:  # Way too large
        result['errors'].append(f"Video resolution ({max_dim}p) is too large (max {max_resolution * 2}p)")
    elif max_dim > max_resolution:
        result['warnings'].append(f"Video will be resized from {max_dim}p to {max_resolution}p")
    
    # Check frame count
    if video_info['frame_count'] > 3000:
        result['warnings'].append(f"Video has many frames ({video_info['frame_count']}), processing may be slow")
    
    # Check if video is valid
    result['valid'] = len(result['errors']) == 0
    
    return result

def cleanup_extracted_frames(frame_dir: str) -> bool:
    """
    Clean up extracted frame directory
    
    Args:
        frame_dir: Directory containing extracted frames
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if os.path.exists(frame_dir):
            shutil.rmtree(frame_dir)
            logger.info(f"Cleaned up frame directory: {frame_dir}")
        return True
    except Exception as e:
        logger.error(f"Error cleaning up frames: {str(e)}")
        return False