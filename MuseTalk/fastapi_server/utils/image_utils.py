import os
import logging
from typing import Tuple, Optional
from PIL import Image, ImageOps
import tempfile

logger = logging.getLogger(__name__)

def get_1080p_dimensions(original_width: int, original_height: int) -> Tuple[int, int]:
    """
    Scale image down along the longer dimension while maintaining aspect ratio
    - Always scale so the longer dimension becomes 1080px maximum
    - Landscape images: width becomes 1080px (height scales proportionally)
    - Portrait images: height becomes 1080px (width scales proportionally)
    - Square images: both dimensions become 1080px
    
    Args:
        original_width: Original image width
        original_height: Original image height
    
    Returns:
        Tuple of (new_width, new_height)
    """
    MAX_DIMENSION = 1080  # Max size for the longer side
    
    # If image is already within bounds, return original dimensions
    if max(original_width, original_height) <= MAX_DIMENSION:
        return original_width, original_height
    
    # Always scale based on the longer dimension
    longer_dimension = max(original_width, original_height)
    scale_ratio = MAX_DIMENSION / longer_dimension
    
    # Calculate new dimensions
    new_width = int(original_width * scale_ratio)
    new_height = int(original_height * scale_ratio)
    
    # Ensure dimensions are even numbers (required for video encoding)
    new_width = new_width if new_width % 2 == 0 else new_width - 1
    new_height = new_height if new_height % 2 == 0 else new_height - 1
    
    return new_width, new_height

def resize_image_to_1080p(input_path: str, output_dir: str) -> Optional[str]:
    """
    Resize image to fit within 1080p bounds while maintaining aspect ratio
    
    Args:
        input_path: Path to input image
        output_dir: Directory to save resized image
    
    Returns:
        Path to resized image, or None if resizing failed
    """
    try:
        # Open and analyze the image
        with Image.open(input_path) as img:
            original_width, original_height = img.size
            original_format = img.format
            
            logger.info(f"Original image: {original_width}x{original_height} ({original_format})")
            
            # Get target dimensions
            new_width, new_height = get_1080p_dimensions(original_width, original_height)
            
            # If no resizing needed, return original path
            if new_width == original_width and new_height == original_height:
                logger.info("Image already within 1080p bounds, no resizing needed")
                return input_path
            
            logger.info(f"Resizing to: {new_width}x{new_height}")
            
            # Resize image with high-quality resampling
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Handle orientation based on EXIF data
            resized_img = ImageOps.exif_transpose(resized_img)
            
            # Generate output filename
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_filename = f"{base_name}_resized_1080p.jpg"  # Always save as JPG for consistency
            output_path = os.path.join(output_dir, output_filename)
            
            # Save resized image
            # Convert to RGB if necessary (for PNG with transparency)
            if resized_img.mode in ('RGBA', 'LA', 'P'):
                # Create a white background
                background = Image.new('RGB', resized_img.size, (255, 255, 255))
                if resized_img.mode == 'P':
                    resized_img = resized_img.convert('RGBA')
                background.paste(resized_img, mask=resized_img.split()[-1] if resized_img.mode == 'RGBA' else None)
                resized_img = background
            
            # Save with high quality
            resized_img.save(output_path, 'JPEG', quality=95, optimize=True)
            
            logger.info(f"Image resized and saved to: {output_path}")
            
            # Log file size reduction
            original_size = os.path.getsize(input_path)
            new_size = os.path.getsize(output_path)
            reduction = (original_size - new_size) / original_size * 100
            
            logger.info(f"File size: {original_size:,} bytes → {new_size:,} bytes ({reduction:.1f}% reduction)")
            
            return output_path
            
    except Exception as e:
        logger.error(f"Failed to resize image {input_path}: {str(e)}")
        return None

def get_image_info(image_path: str) -> dict:
    """
    Get basic information about an image
    
    Args:
        image_path: Path to image file
        
    Returns:
        Dictionary with image information
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            megapixels = (width * height) / 1_000_000
            
            return {
                'width': width,
                'height': height,
                'format': img.format,
                'mode': img.mode,
                'megapixels': round(megapixels, 2),
                'aspect_ratio': round(width / height, 2),
                'needs_resize': max(width, height) > 1080,
                'file_size': os.path.getsize(image_path)
            }
    except Exception as e:
        logger.error(f"Failed to get image info for {image_path}: {str(e)}")
        return {}

def estimate_processing_time(width: int, height: int, audio_duration: int) -> int:
    """
    Estimate processing time based on image resolution and audio duration
    Based on stress test data: ~50 seconds per megapixel + minimal audio impact
    
    Args:
        width: Image width
        height: Image height  
        audio_duration: Audio duration in seconds
        
    Returns:
        Estimated processing time in seconds
    """
    megapixels = (width * height) / 1_000_000
    
    # Base time: ~50 seconds per megapixel
    base_time = megapixels * 50
    
    # Audio impact is minimal (correlation 0.279), add small factor
    audio_factor = 1 + (audio_duration - 20) * 0.01
    
    estimated_time = base_time * audio_factor
    
    return max(int(estimated_time), 10)  # Minimum 10 seconds