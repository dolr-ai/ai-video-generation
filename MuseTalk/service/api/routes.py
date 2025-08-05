import os
import uuid
import logging
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename

from service.core.musetalk_service import MuseTalkService
from service.utils.file_utils import download_file, is_url, get_file_extension, allowed_file
from service.config.settings import Config

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

# Initialize MuseTalk service (singleton)
musetalk_service = None

def get_musetalk_service():
    global musetalk_service
    if musetalk_service is None:
        musetalk_service = MuseTalkService()
    return musetalk_service

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'MuseTalk API',
        'version': Config.MUSETALK_VERSION
    })

@api_bp.route('/generate', methods=['POST'])
def generate_talking_head():
    """
    Generate talking head video from image and audio
    
    Request body:
    {
        "image": "url or local path",
        "audio": "url or local path", 
        "script": "optional text script",
        "local_dev": true/false,
        "bbox_shift": 0,
        "realtime": false,
        "fps": 25,
        "batch_size": 8
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        # Validate required fields
        if 'image' not in data or 'audio' not in data:
            return jsonify({'error': 'Both image and audio are required'}), 400
            
        # Extract parameters
        image_source = data['image']
        audio_source = data['audio']
        script = data.get('script', '')
        local_dev = data.get('local_dev', True)
        bbox_shift = data.get('bbox_shift', Config.DEFAULT_BBOX_SHIFT)
        realtime = data.get('realtime', False)
        fps = data.get('fps', Config.DEFAULT_FPS)
        batch_size = data.get('batch_size', Config.DEFAULT_BATCH_SIZE)
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(Config.TEMP_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        try:
            # Process image input
            if is_url(image_source):
                logger.info(f"Downloading image from URL: {image_source}")
                image_path = download_file(image_source, task_dir, 'image')
            else:
                # Assume it's a local path
                if not os.path.exists(image_source):
                    return jsonify({'error': f'Image file not found: {image_source}'}), 404
                image_path = image_source
                
            # Process audio input
            if is_url(audio_source):
                logger.info(f"Downloading audio from URL: {audio_source}")
                audio_path = download_file(audio_source, task_dir, 'audio')
            else:
                # Assume it's a local path
                if not os.path.exists(audio_source):
                    return jsonify({'error': f'Audio file not found: {audio_source}'}), 404
                audio_path = audio_source
                
            # Get MuseTalk service
            service = get_musetalk_service()
            
            # Generate talking head
            logger.info(f"Generating talking head for task {task_id}")
            result = service.generate_talking_head(
                image_path=image_path,
                audio_path=audio_path,
                output_dir=task_dir,
                bbox_shift=bbox_shift,
                realtime=realtime,
                fps=fps,
                batch_size=batch_size,
                script=script
            )
            
            if result['status'] == 'success':
                output_path = result['output_path']
                
                if local_dev:
                    # Return local file path
                    return jsonify({
                        'status': 'success',
                        'task_id': task_id,
                        'output_path': output_path,
                        'message': 'Talking head generated successfully'
                    })
                else:
                    # Return file download
                    return send_file(
                        output_path,
                        mimetype='video/mp4',
                        as_attachment=True,
                        download_name=f'talking_head_{task_id}.mp4'
                    )
            else:
                return jsonify({
                    'status': 'error',
                    'message': result.get('message', 'Failed to generate talking head')
                }), 500
                
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/generate_realtime', methods=['POST'])
def generate_realtime():
    """
    Generate talking head using real-time inference
    
    Request body:
    {
        "avatar_id": "unique_avatar_id",
        "video": "url or local path",
        "audio_clips": ["audio1.wav", "audio2.wav"],
        "preparation": true/false,
        "bbox_shift": 0,
        "local_dev": true/false
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        # Validate required fields
        if 'avatar_id' not in data or 'video' not in data:
            return jsonify({'error': 'Both avatar_id and video are required'}), 400
            
        avatar_id = data['avatar_id']
        video_source = data['video']
        audio_clips = data.get('audio_clips', [])
        preparation = data.get('preparation', True)
        bbox_shift = data.get('bbox_shift', 0)
        local_dev = data.get('local_dev', True)
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(Config.TEMP_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        try:
            # Process video input
            if is_url(video_source):
                logger.info(f"Downloading video from URL: {video_source}")
                video_path = download_file(video_source, task_dir, 'video')
            else:
                if not os.path.exists(video_source):
                    return jsonify({'error': f'Video file not found: {video_source}'}), 404
                video_path = video_source
                
            # Process audio clips
            processed_audio_clips = []
            for i, audio_clip in enumerate(audio_clips):
                if is_url(audio_clip):
                    audio_path = download_file(audio_clip, task_dir, f'audio_{i}')
                else:
                    if not os.path.exists(audio_clip):
                        return jsonify({'error': f'Audio file not found: {audio_clip}'}), 404
                    audio_path = audio_clip
                processed_audio_clips.append(audio_path)
                
            # Get MuseTalk service
            service = get_musetalk_service()
            
            # Generate talking head with real-time inference
            logger.info(f"Generating real-time talking head for avatar {avatar_id}")
            results = service.generate_realtime(
                avatar_id=avatar_id,
                video_path=video_path,
                audio_clips=processed_audio_clips,
                preparation=preparation,
                bbox_shift=bbox_shift,
                output_dir=task_dir
            )
            
            if local_dev:
                # Return local file paths
                return jsonify({
                    'status': 'success',
                    'task_id': task_id,
                    'avatar_id': avatar_id,
                    'outputs': results,
                    'message': 'Real-time talking heads generated successfully'
                })
            else:
                # For non-local dev, return the first generated video
                if results and len(results) > 0:
                    return send_file(
                        results[0]['output_path'],
                        mimetype='video/mp4',
                        as_attachment=True,
                        download_name=f'talking_head_{avatar_id}_{task_id}.mp4'
                    )
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'No videos generated'
                    }), 500
                    
        except Exception as e:
            logger.error(f"Error processing real-time task {task_id}: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"Error in generate_realtime endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload file endpoint for direct file uploads
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_id = str(uuid.uuid4())
        upload_dir = os.path.join(Config.TEMP_DIR, 'uploads', upload_id)
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        return jsonify({
            'status': 'success',
            'upload_id': upload_id,
            'file_path': file_path,
            'filename': filename
        })
    else:
        return jsonify({'error': 'File type not allowed'}), 400