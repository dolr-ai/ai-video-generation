import os
import logging
import httpx
from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from core.task_manager import task_manager, TaskStatus
from utils.file_utils import (
    is_url,
    download_file,
    generate_unique_id,
    create_task_directory,
    save_video_file,
    is_allowed_file,
    detect_file_type_from_url,
)
from utils.image_utils import resize_image_to_1080p, get_image_info, estimate_processing_time
from utils.video_utils import (
    get_video_info,
    validate_video_for_processing,
    resize_video,
    estimate_video_memory
)
from utils.file_utils import generate_unique_id
from config.settings import settings

# Create separate file logger for endpoints with better formatting
endpoint_logger = logging.getLogger("endpoints")
endpoint_handler = logging.FileHandler(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "endpoints.log")
)
endpoint_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
endpoint_logger.addHandler(endpoint_handler)
endpoint_logger.setLevel(logging.DEBUG)

# Also add console output for endpoints
endpoint_console_handler = logging.StreamHandler()
endpoint_console_handler.setFormatter(
    logging.Formatter("%(asctime)s - ENDPOINTS - %(levelname)s - %(message)s")
)
endpoint_logger.addHandler(endpoint_console_handler)

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response models
class GenerateVideoRequest(BaseModel):
    image: str  # URL or local path (image OR video)
    audio: str  # URL or local path
    user_id: str  # User identifier
    bbox_shift: int = settings.DEFAULT_BBOX_SHIFT
    fps: int = settings.DEFAULT_FPS
    batch_size: Optional[int] = None  # Auto-select based on input type
    input_type: Optional[str] = None  # "image" or "video" (auto-detect if None)
    video_start_time: Optional[float] = 0  # Start time for video clip
    video_end_time: Optional[float] = None  # End time for video clip


class GenerateVideoResponse(BaseModel):
    status: str
    task_id: str
    message: str


class TaskStatusResponse(BaseModel):
    status: str
    task_id: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output_path: Optional[str] = None
    gcs_path: Optional[str] = None  # GCS path for uploaded video
    error_message: Optional[str] = None
    queue_position: Optional[int] = None


class UploadResponse(BaseModel):
    status: str
    file_path: str
    filename: str


# Realtime generation models
class PrepareRealtimeRequest(BaseModel):
    video_path: str  # Path to video file or URL
    user_id: str
    bbox_shift: int = settings.DEFAULT_BBOX_SHIFT
    prep_name: Optional[str] = None  # Optional human-readable name


class PrepareRealtimeResponse(BaseModel):
    status: str
    prep_id: str
    prep_name: Optional[str] = None
    num_frames: Optional[int] = None
    valid_frames: Optional[int] = None
    smoothing_enabled: Optional[bool] = None
    message: Optional[str] = None


class GenerateRealtimeRequest(BaseModel):
    prep_id: str  # Preparation ID from /prepare_realtime
    audio: str  # URL or local path
    user_id: str
    fps: int = settings.DEFAULT_FPS


class GenerateRealtimeResponse(BaseModel):
    status: str
    task_id: str
    prep_id: str
    message: str


# Queue processing is now handled by queue_processor.py


@router.post("/generate", response_model=GenerateVideoResponse)
async def generate_video(request: GenerateVideoRequest):
    """Generate talking head video"""
    try:
        # Generate unique task ID
        task_id = generate_unique_id()
        endpoint_logger.info(f"🎬 Creating new generation task: {task_id}")
        endpoint_logger.info(f"  User ID: {request.user_id}")
        endpoint_logger.info(f"  Image input: {request.image}")
        endpoint_logger.info(f"  Audio input: {request.audio}")
        endpoint_logger.info(
            f"  Parameters: bbox_shift={request.bbox_shift}, fps={request.fps}, batch_size={request.batch_size}"
        )

        # Detect input type and validate
        input_type = request.input_type
        if not input_type:
            # Auto-detect based on file extension or URL
            if is_url(request.image):
                detected_type = detect_file_type_from_url(request.image)
                if detected_type == "video":
                    input_type = "video"
                elif detected_type == "image":
                    input_type = "image"
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Could not determine file type from URL: {request.image}"
                    )
            else:
                # Check local file extension
                from pathlib import Path
                ext = Path(request.image).suffix.lower().lstrip('.')
                if ext in settings.ALLOWED_VIDEO_EXTENSIONS:
                    input_type = "video"
                elif ext in settings.ALLOWED_IMAGE_EXTENSIONS:
                    input_type = "image"
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unsupported file type: {ext}"
                    )

        endpoint_logger.info(f"  Detected input type: {input_type}")
        
        # Auto-select batch size based on input type
        if request.batch_size is None:
            request.batch_size = settings.VIDEO_BATCH_SIZE if input_type == "video" else settings.DEFAULT_BATCH_SIZE
            endpoint_logger.info(f"  Auto-selected batch size: {request.batch_size}")
        
        # Validate audio input
        if is_url(request.audio):
            audio_file_type = detect_file_type_from_url(request.audio)
            if audio_file_type not in ["audio", None]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid audio input: expected audio file, got {audio_file_type}"
                )

        # Create task directory
        task_dir = create_task_directory(task_id)

        # Process input files based on type
        image_path = request.image
        audio_path = request.audio
        
        # Download image/video if URL
        if is_url(request.image):
            file_type = "video" if input_type == "video" else "image"
            endpoint_logger.info(f"📥 Downloading {file_type} from URL: {request.image}")
            downloaded_file = download_file(request.image, task_dir, file_type)
            image_path = downloaded_file
        else:
            # Check if local file exists
            if not os.path.exists(request.image):
                raise HTTPException(
                    status_code=404, detail=f"File not found: {request.image}"
                )
            image_path = request.image
        
        # Process based on input type
        if input_type == "video":
            # Validate and process video
            endpoint_logger.info(f"📊 Analyzing video: {image_path}")
            
            validation_result = validate_video_for_processing(
                image_path, 
                max_duration=settings.MAX_VIDEO_DURATION,
                max_resolution=settings.MAX_VIDEO_RESOLUTION
            )
            
            if not validation_result['valid']:
                errors = "; ".join(validation_result['errors'])
                raise HTTPException(status_code=400, detail=f"Video validation failed: {errors}")
            
            video_info = validation_result['video_info']
            endpoint_logger.info(f"  Resolution: {video_info['width']}x{video_info['height']}")
            endpoint_logger.info(f"  Duration: {video_info['duration']:.1f}s, FPS: {video_info['fps']:.1f}")
            endpoint_logger.info(f"  Frames: {video_info['frame_count']}")
            
            # Log warnings
            for warning in validation_result['warnings']:
                endpoint_logger.warning(f"⚠️ {warning}")
            
            # Resize video if needed
            if video_info['needs_resize']:
                endpoint_logger.info(f"🔄 Resizing video to {settings.MAX_VIDEO_RESOLUTION}p...")
                resized_path = os.path.join(task_dir, "resized_video.mp4")
                if resize_video(image_path, resized_path, settings.MAX_VIDEO_RESOLUTION, settings.VIDEO_RESIZE_QUALITY):
                    image_path = resized_path
                    endpoint_logger.info("✅ Video resized successfully")
                else:
                    endpoint_logger.warning("⚠️ Failed to resize video, proceeding with original")
            
            # Estimate memory requirements
            memory_estimate = estimate_video_memory(
                video_info['width'], 
                video_info['height'], 
                video_info['frame_count'],
                request.batch_size
            )
            endpoint_logger.info(f"💾 Estimated GPU memory requirement: {memory_estimate} GB")
            
            if memory_estimate > settings.VIDEO_MEMORY_LIMIT_GB:
                endpoint_logger.warning(f"⚠️ Memory estimate ({memory_estimate} GB) exceeds limit ({settings.VIDEO_MEMORY_LIMIT_GB} GB)")
                endpoint_logger.warning("⚠️ Processing may fail or be slow")
        
        else:
            # Process as image (existing logic)
            endpoint_logger.info(f"📊 Analyzing image: {image_path}")
            image_info = get_image_info(image_path)
            
            if image_info:
                endpoint_logger.info(f"  Resolution: {image_info['width']}x{image_info['height']} ({image_info['megapixels']} MP)")
                endpoint_logger.info(f"  Format: {image_info['format']}, Size: {image_info['file_size']:,} bytes")
                
                # Resize if image is larger than 1080p
                if image_info['needs_resize']:
                    endpoint_logger.info(f"🔄 Image exceeds 1080p, resizing...")
                    resized_path = resize_image_to_1080p(image_path, task_dir)
                    if resized_path:
                        image_path = resized_path
                        # Get info about resized image
                        resized_info = get_image_info(image_path)
                        if resized_info:
                            endpoint_logger.info(f"✅ Resized to: {resized_info['width']}x{resized_info['height']} ({resized_info['megapixels']} MP)")
                            
                            # Estimate processing time
                            estimated_time = estimate_processing_time(
                                resized_info['width'], 
                                resized_info['height'], 
                                30  # Default estimate for audio
                            )
                            endpoint_logger.info(f"⏱️  Estimated processing time: {estimated_time} seconds")
                    else:
                        endpoint_logger.warning("⚠️ Failed to resize image, proceeding with original")
                else:
                    endpoint_logger.info("✅ Image within 1080p bounds, no resizing needed")
            else:
                endpoint_logger.warning("⚠️ Could not analyze image, proceeding anyway")

        if is_url(request.audio):
            endpoint_logger.info(f"📥 Downloading audio from URL: {request.audio}")
            audio_path = download_file(request.audio, task_dir, "audio")
        else:
            # Check if local file exists
            if not os.path.exists(request.audio):
                raise HTTPException(
                    status_code=404, detail=f"Audio file not found: {request.audio}"
                )
            audio_path = request.audio

        # Create task in task manager with additional metadata
        task_data = {
            "task_id": task_id,
            "image_path": image_path,
            "audio_path": audio_path,
            "user_id": request.user_id,
            "bbox_shift": request.bbox_shift,
            "fps": request.fps,
            "batch_size": request.batch_size,
            "input_type": input_type,
        }
        
        # Add video-specific parameters if applicable
        if input_type == "video":
            task_data["video_start_time"] = request.video_start_time
            task_data["video_end_time"] = request.video_end_time
        
        task_manager.create_task(**task_data)

        # Add task to queue for processing
        task_manager.add_task_to_queue(task_id)

        # Update queue positions
        task_manager.update_queue_positions()
        
        # Get queue position for response
        task = task_manager.get_task(task_id)
        queue_position = task.queue_position if task else None
        
        queue_message = f"Video generation queued (position {queue_position}). Use /status/{{task_id}} to check progress."
        
        response = GenerateVideoResponse(
            status="queued",
            task_id=task_id,
            message=queue_message,
        )

        endpoint_logger.info(f"✅ Task {task_id} accepted and queued for processing")
        return response

    except HTTPException:
        raise
    except Exception as e:
        endpoint_logger.error(f"Error creating generation task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get status of a generation task"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        status=task.status.value,
        task_id=task.task_id,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        output_path=task.output_path,
        gcs_path=task.gcs_path,
        error_message=task.error_message,
        queue_position=task.queue_position,
    )


@router.get("/video/{task_id}")
async def get_video(task_id: str):
    """Download generated video"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400, detail=f"Task not completed. Status: {task.status}"
        )

    # Check if local file exists
    if task.output_path and os.path.exists(task.output_path):
        return FileResponse(
            task.output_path, media_type="video/mp4", filename=f"generated_{task_id}.mp4"
        )
    
    # If local file doesn't exist but GCS path exists, inform the user
    if task.gcs_path:
        raise HTTPException(
            status_code=410, 
            detail=f"Video file has been moved to cloud storage. GCS path: {task.gcs_path}"
        )
    
    raise HTTPException(status_code=404, detail="Video file not found")


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a file (image or audio)"""
    # Check file type
    file_type = None
    if is_allowed_file(file.filename, "image"):
        file_type = "image"
    elif is_allowed_file(file.filename, "audio"):
        file_type = "audio"
    else:
        raise HTTPException(status_code=400, detail="File type not allowed")

    # Generate unique filename and save
    upload_id = generate_unique_id()
    upload_dir = os.path.join(settings.UPLOADS_DIR, upload_id)
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)

    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    endpoint_logger.info(f"📎 File uploaded: {file.filename} -> {file_path}")

    return UploadResponse(status="success", file_path=file_path, filename=file.filename)


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check model server
        async with httpx.AsyncClient(timeout=5.0) as client:
            model_server_url = (
                f"http://{settings.MODEL_SERVER_HOST}:{settings.MODEL_SERVER_PORT}"
            )
            response = await client.get(f"{model_server_url}/health")
            model_health = response.json() if response.status_code == 200 else None
    except:
        model_health = None

    return {
        "status": "healthy",
        "service": "MuseTalk Handler Server",
        "model_server": model_health,
        "tasks_count": len(task_manager.get_all_tasks()),
        "queue_size": task_manager.get_queue_size(),
    }


# Realtime generation endpoints
@router.post("/prepare_realtime", response_model=PrepareRealtimeResponse)
async def prepare_realtime_video(request: PrepareRealtimeRequest):
    """Prepare video for realtime generation by pre-processing all materials"""
    try:
        if not settings.ENABLE_REALTIME_MODE:
            raise HTTPException(
                status_code=503,
                detail="Realtime mode is disabled"
            )
        
        endpoint_logger.info(f"🚀 Preparing realtime video for user: {request.user_id}")
        endpoint_logger.info(f"  Video: {request.video_path}")
        endpoint_logger.info(f"  Bbox shift: {request.bbox_shift}")
        
        # Generate preparation ID
        prep_id = generate_unique_id()
        endpoint_logger.info(f"  Generated prep ID: {prep_id}")
        
        # Validate and download video if URL
        video_path = request.video_path
        if is_url(request.video_path):
            endpoint_logger.info(f"📥 Downloading video from URL...")
            temp_dir = create_task_directory(prep_id)
            try:
                video_path = download_file(request.video_path, temp_dir, "video")
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to download video: {str(e)}"
                )
        else:
            # Check if local file exists
            if not os.path.exists(request.video_path):
                raise HTTPException(
                    status_code=404,
                    detail=f"Video file not found: {request.video_path}"
                )
        
        # Validate video
        endpoint_logger.info(f"📊 Validating video for realtime preparation...")
        validation_result = validate_video_for_processing(
            video_path,
            max_duration=60,  # Allow longer for realtime prep
            max_resolution=settings.MAX_VIDEO_RESOLUTION
        )
        
        if not validation_result['valid']:
            errors = "; ".join(validation_result['errors'])
            raise HTTPException(
                status_code=400,
                detail=f"Video validation failed: {errors}"
            )
        
        video_info = validation_result['video_info']
        endpoint_logger.info(f"  Resolution: {video_info['width']}x{video_info['height']}")
        endpoint_logger.info(f"  Duration: {video_info['duration']:.1f}s, FPS: {video_info['fps']:.1f}")
        
        # Call model server for preparation
        endpoint_logger.info("🌐 Calling model server for realtime preparation...")
        async with httpx.AsyncClient(timeout=300) as client:  # Longer timeout for prep
            model_server_url = f"http://{settings.MODEL_SERVER_HOST}:{settings.MODEL_SERVER_PORT}"
            
            prep_request = {
                "prep_id": prep_id,
                "video_path": video_path,
                "bbox_shift": request.bbox_shift
            }
            
            response = await client.post(
                f"{model_server_url}/prepare_realtime",
                json=prep_request,
                timeout=300
            )
            
            if response.status_code != 200:
                endpoint_logger.error(f"Model server preparation failed: {response.status_code}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Model server preparation failed: {response.text}"
                )
            
            result = response.json()
            
            if result["status"] == "success":
                endpoint_logger.info(f"✅ Realtime preparation completed: {prep_id}")
                
                return PrepareRealtimeResponse(
                    status="success",
                    prep_id=prep_id,
                    prep_name=request.prep_name,
                    num_frames=result.get("num_frames"),
                    valid_frames=result.get("valid_frames"),
                    smoothing_enabled=result.get("smoothing_enabled"),
                    message=f"Realtime preparation ready. Use prep_id '{prep_id}' for generation."
                )
            else:
                endpoint_logger.error(f"❌ Realtime preparation failed: {result.get('message')}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Preparation failed: {result.get('message')}"
                )
    
    except HTTPException:
        raise
    except Exception as e:
        endpoint_logger.error(f"Error in realtime preparation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate_realtime", response_model=GenerateRealtimeResponse)
async def generate_realtime_video(request: GenerateRealtimeRequest):
    """Generate video using pre-processed realtime preparation - ultra fast!"""
    try:
        if not settings.ENABLE_REALTIME_MODE:
            raise HTTPException(
                status_code=503,
                detail="Realtime mode is disabled"
            )
        
        # Generate unique task ID
        task_id = generate_unique_id()
        endpoint_logger.info(f"⚡ Creating realtime generation task: {task_id}")
        endpoint_logger.info(f"  User ID: {request.user_id}")
        endpoint_logger.info(f"  Prep ID: {request.prep_id}")
        endpoint_logger.info(f"  Audio input: {request.audio}")
        endpoint_logger.info(f"  FPS: {request.fps}")
        
        # Process audio input
        audio_path = request.audio
        task_dir = create_task_directory(task_id)
        
        if is_url(request.audio):
            endpoint_logger.info(f"📥 Downloading audio from URL...")
            try:
                audio_path = download_file(request.audio, task_dir, "audio")
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to download audio: {str(e)}"
                )
        else:
            # Check if local file exists
            if not os.path.exists(request.audio):
                raise HTTPException(
                    status_code=404,
                    detail=f"Audio file not found: {request.audio}"
                )
        
        # Create realtime task
        task_manager.create_task(
            task_id=task_id,
            image_path=f"realtime:{request.prep_id}",  # Special format for realtime
            audio_path=audio_path,
            user_id=request.user_id,
            fps=request.fps,
            batch_size=settings.REALTIME_BATCH_SIZE,
            input_type="realtime"
        )
        
        # Add to priority queue (realtime gets priority)
        task_manager.add_task_to_queue(task_id)
        task_manager.update_queue_positions()
        
        # Get queue position
        task = task_manager.get_task(task_id)
        queue_position = task.queue_position if task else None
        
        response_message = f"Realtime generation queued (position {queue_position}). Processing should be very fast!"
        
        endpoint_logger.info(f"✅ Realtime task {task_id} queued for ultra-fast processing")
        
        return GenerateRealtimeResponse(
            status="queued",
            task_id=task_id,
            prep_id=request.prep_id,
            message=response_message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        endpoint_logger.error(f"Error creating realtime generation task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/realtime/preparations")
async def list_realtime_preparations():
    """List available realtime preparations"""
    try:
        if not settings.ENABLE_REALTIME_MODE:
            raise HTTPException(
                status_code=503,
                detail="Realtime mode is disabled"
            )
        
        # Get preparations from model server
        async with httpx.AsyncClient(timeout=10.0) as client:
            model_server_url = f"http://{settings.MODEL_SERVER_HOST}:{settings.MODEL_SERVER_PORT}"
            response = await client.get(f"{model_server_url}/realtime/preparations")
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to get preparations from model server"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        endpoint_logger.error(f"Error listing preparations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/realtime/preparations/{prep_id}")
async def delete_realtime_preparation(prep_id: str):
    """Delete a realtime preparation"""
    try:
        if not settings.ENABLE_REALTIME_MODE:
            raise HTTPException(
                status_code=503,
                detail="Realtime mode is disabled"
            )
        
        # Delete from model server
        async with httpx.AsyncClient(timeout=10.0) as client:
            model_server_url = f"http://{settings.MODEL_SERVER_HOST}:{settings.MODEL_SERVER_PORT}"
            response = await client.delete(f"{model_server_url}/realtime/preparations/{prep_id}")
            
            if response.status_code == 200:
                endpoint_logger.info(f"🗑️ Deleted realtime preparation: {prep_id}")
                return {"status": "success", "message": f"Preparation {prep_id} deleted"}
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Preparation {prep_id} not found"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to delete preparation from model server"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        endpoint_logger.error(f"Error deleting preparation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
