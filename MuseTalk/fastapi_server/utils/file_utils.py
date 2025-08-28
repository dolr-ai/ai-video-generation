import os
import uuid
import requests
import logging
from urllib.parse import urlparse
from typing import Optional
from pathlib import Path

from config.settings import settings

logger = logging.getLogger(__name__)

def is_url(path: str) -> bool:
    """Check if the path is a URL"""
    try:
        result = urlparse(path)
        return bool(result.scheme and result.netloc)
    except:
        return False

def get_file_extension(filename: str) -> str:
    """Get file extension from filename"""
    return Path(filename).suffix.lower().lstrip('.')

def is_allowed_file(filename: str, file_type: str) -> bool:
    """Check if file type is allowed"""
    extension = get_file_extension(filename)
    
    if file_type == 'image':
        return extension in settings.ALLOWED_IMAGE_EXTENSIONS
    elif file_type == 'audio':
        return extension in settings.ALLOWED_AUDIO_EXTENSIONS
    elif file_type == 'video':
        return extension in settings.ALLOWED_VIDEO_EXTENSIONS
    
    return False

def detect_file_type_from_url(url: str) -> Optional[str]:
    """Detect file type from URL based on extension"""
    try:
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        if not filename:
            return None
            
        if is_allowed_file(filename, 'image'):
            return 'image'
        elif is_allowed_file(filename, 'audio'):
            return 'audio'
        elif is_allowed_file(filename, 'video'):
            return 'video'
        
        return None
    except:
        return None

def download_file(url: str, dest_dir: str, file_type: str) -> str:
    """Download file from URL to destination directory"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Get filename from URL or generate one
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        if not filename or not is_allowed_file(filename, file_type):
            # Generate filename based on file type
            ext_map = {
                'image': 'jpg',
                'audio': 'wav',
                'video': 'mp4'
            }
            filename = f"{file_type}_{uuid.uuid4().hex[:8]}.{ext_map.get(file_type, 'bin')}"
        
        file_path = os.path.join(dest_dir, filename)
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"Downloaded file: {url} -> {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Error downloading file {url}: {str(e)}")
        raise

def generate_unique_id() -> str:
    """Generate unique ID for tasks"""
    return str(uuid.uuid4())

def create_task_directory(task_id: str) -> str:
    """Create and return task directory path"""
    task_dir = os.path.join(settings.TEMP_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    return task_dir

def get_video_path(task_id: str, filename: str) -> str:
    """Get video file path for given task"""
    return os.path.join(settings.VIDEOS_DIR, task_id, filename)

def save_video_file(task_id: str, source_path: str, filename: Optional[str] = None) -> str:
    """Save video file to videos directory"""
    if not filename:
        filename = f"generated_{task_id}.mp4"
    
    video_dir = os.path.join(settings.VIDEOS_DIR, task_id)
    os.makedirs(video_dir, exist_ok=True)
    
    dest_path = os.path.join(video_dir, filename)
    
    # Copy or move file
    import shutil
    shutil.copy2(source_path, dest_path)
    
    return dest_path