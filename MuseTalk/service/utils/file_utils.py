import os
import requests
import logging
from urllib.parse import urlparse, unquote
from service.config.settings import Config

logger = logging.getLogger(__name__)

def is_url(string):
    """Check if string is a valid URL"""
    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_file_extension(filename):
    """Get file extension from filename"""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def allowed_file(filename):
    """Check if file extension is allowed"""
    ext = get_file_extension(filename)
    return ext in (Config.ALLOWED_IMAGE_EXTENSIONS | 
                   Config.ALLOWED_AUDIO_EXTENSIONS | 
                   Config.ALLOWED_VIDEO_EXTENSIONS)

def download_file(url, save_dir, prefix='file'):
    """Download file from URL to local directory"""
    try:
        # Get filename from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(unquote(parsed_url.path))
        
        # If no filename in URL, generate one
        if not filename or '.' not in filename:
            # Try to get extension from content-type
            response = requests.head(url, timeout=10)
            content_type = response.headers.get('content-type', '')
            ext = content_type.split('/')[-1] if '/' in content_type else 'bin'
            filename = f"{prefix}.{ext}"
        
        # Ensure filename is safe
        filename = f"{prefix}_{filename}"
        filepath = os.path.join(save_dir, filename)
        
        # Download file
        logger.info(f"Downloading {url} to {filepath}")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        logger.info(f"Successfully downloaded {url}")
        return filepath
        
    except Exception as e:
        logger.error(f"Error downloading file from {url}: {str(e)}")
        raise Exception(f"Failed to download file: {str(e)}")

def cleanup_temp_files(directory):
    """Clean up temporary files in directory"""
    try:
        if os.path.exists(directory):
            import shutil
            shutil.rmtree(directory)
            logger.info(f"Cleaned up directory: {directory}")
    except Exception as e:
        logger.error(f"Error cleaning up directory {directory}: {str(e)}")