import os
import logging
import httpx
from fastapi import APIRouter, HTTPException, File, UploadFile, BackgroundTasks
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
    image: str  # URL or local path
    audio: str  # URL or local path
    user_id: str  # User identifier
    bbox_shift: int = 0
    fps: int = 25
    batch_size: int = 8


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
    error_message: Optional[str] = None


class UploadResponse(BaseModel):
    status: str
    file_path: str
    filename: str


async def process_generation_task(
    task_id: str,
    image_path: str,
    audio_path: str,
    bbox_shift: int = -5,
    fps: int = 30,
    batch_size: int = 8,
):
    """Background task to process video generation"""
    try:
        endpoint_logger.info(f"🔄 Starting background processing for task {task_id}")
        endpoint_logger.info(f"  Image: {image_path}")
        endpoint_logger.info(f"  Audio: {audio_path}")

        # Update status to processing
        task_manager.update_task_status(task_id, TaskStatus.PROCESSING)

        # Prepare output path
        output_filename = f"generated_{task_id}.mp4"
        temp_output_path = os.path.join(create_task_directory(task_id), output_filename)

        # Call model server
        endpoint_logger.info(f"🌐 Calling model server for task {task_id}")
        async with httpx.AsyncClient(timeout=settings.MODEL_SERVER_TIMEOUT) as client:
            model_server_url = (
                f"http://{settings.MODEL_SERVER_HOST}:{settings.MODEL_SERVER_PORT}"
            )
            endpoint_logger.info(f"Model server URL: {model_server_url}")

            generation_request = {
                "task_id": task_id,
                "image_path": image_path,
                "audio_path": audio_path,
                "output_path": temp_output_path,
                "bbox_shift": bbox_shift,
                "fps": fps,
                "batch_size": batch_size,
            }

            response = await client.post(
                f"{model_server_url}/generate",
                json=generation_request,
                timeout=settings.GENERATION_TIMEOUT,
            )

            if response.status_code == 200:
                result = response.json()
                if result["status"] == "success":
                    # Save video to permanent storage
                    final_video_path = save_video_file(
                        task_id, temp_output_path, output_filename
                    )

                    # Update task status
                    task_manager.update_task_status(
                        task_id, TaskStatus.COMPLETED, output_path=final_video_path
                    )

                    endpoint_logger.info(
                        f"✅ Task {task_id} completed successfully - Video saved to: {final_video_path}"
                    )
                else:
                    # Generation failed
                    task_manager.update_task_status(
                        task_id,
                        TaskStatus.FAILED,
                        error_message=result.get("message", "Unknown error"),
                    )
                    endpoint_logger.error(
                        f"❌ Task {task_id} generation failed: {result.get('message')}"
                    )
            else:
                # HTTP error
                error_msg = f"Model server error: {response.status_code}"
                task_manager.update_task_status(
                    task_id, TaskStatus.FAILED, error_message=error_msg
                )
                endpoint_logger.error(f"❌ Task {task_id} HTTP error: {error_msg}")

    except Exception as e:
        import traceback

        error_msg = f"Error processing task: {str(e)}"
        task_manager.update_task_status(
            task_id, TaskStatus.FAILED, error_message=error_msg
        )
        endpoint_logger.error(f"❌ Task {task_id} exception: {error_msg}")
        endpoint_logger.error(f"Full traceback:\n{traceback.format_exc()}")


@router.post("/generate", response_model=GenerateVideoResponse)
async def generate_video(
    request: GenerateVideoRequest, background_tasks: BackgroundTasks
):
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

        # Validate inputs - reject video URLs
        if is_url(request.image):
            image_file_type = detect_file_type_from_url(request.image)
            if image_file_type == "video":
                raise HTTPException(
                    status_code=400,
                    detail="Invalid request: video not supported for image input. Please provide image URL or local path.",
                )
            elif image_file_type != "image" and image_file_type is not None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid request: expected image URL, got {image_file_type} type.",
                )

        if is_url(request.audio):
            audio_file_type = detect_file_type_from_url(request.audio)
            if audio_file_type == "video":
                raise HTTPException(
                    status_code=400,
                    detail="Invalid request: video not supported for audio input. Please provide audio URL or local path.",
                )
            elif audio_file_type != "audio" and audio_file_type is not None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid request: expected audio URL, got {audio_file_type} type.",
                )

        # Create task directory
        task_dir = create_task_directory(task_id)

        # Process input files
        image_path = request.image
        audio_path = request.audio

        # Download files if they are URLs
        if is_url(request.image):
            endpoint_logger.info(f"📥 Downloading image from URL: {request.image}")
            image_path = download_file(request.image, task_dir, "image")
        else:
            # Check if local file exists
            if not os.path.exists(request.image):
                raise HTTPException(
                    status_code=404, detail=f"Image file not found: {request.image}"
                )
            image_path = request.image

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

        # Create task in task manager
        task_manager.create_task(
            task_id=task_id,
            image_path=image_path,
            audio_path=audio_path,
            user_id=request.user_id,
            bbox_shift=request.bbox_shift,
            fps=request.fps,
            batch_size=request.batch_size,
        )

        # Start background processing
        background_tasks.add_task(
            process_generation_task,
            task_id=task_id,
            image_path=image_path,
            audio_path=audio_path,
            bbox_shift=request.bbox_shift,
            fps=request.fps,
            batch_size=request.batch_size,
        )

        response = GenerateVideoResponse(
            status="accepted",
            task_id=task_id,
            message="Video generation started. Use /status/{task_id} to check progress.",
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
        error_message=task.error_message,
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

    if not task.output_path or not os.path.exists(task.output_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        task.output_path, media_type="video/mp4", filename=f"generated_{task_id}.mp4"
    )


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
    }
