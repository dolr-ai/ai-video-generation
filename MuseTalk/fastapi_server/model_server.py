import asyncio
import logging
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.musetalk_model import MuseTalkModel
from config.settings import settings

# Create separate file logger for model server
model_server_logger = logging.getLogger('model_server')
model_server_logger.propagate = False  # Prevent propagation to root logger
model_server_logger.setLevel(logging.DEBUG)

# File handler for logging to file
model_server_handler = logging.FileHandler(os.path.join(settings.FASTAPI_SERVER_DIR, 'model_server.log'))
model_server_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
model_server_logger.addHandler(model_server_handler)

# Console handler for terminal output
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - MODEL_SERVER - %(levelname)s - %(message)s'))
model_server_logger.addHandler(console_handler)

logger = model_server_logger

# Initialize model
musetalk_model = MuseTalkModel()

# FastAPI app for model server
model_app = FastAPI(title="MuseTalk Model Server", version="1.0.0")

class GenerateRequest(BaseModel):
    task_id: str
    image_path: str  # Can be image or video path
    audio_path: str
    output_path: str
    bbox_shift: int = settings.DEFAULT_BBOX_SHIFT
    fps: int = settings.DEFAULT_FPS
    batch_size: int = settings.DEFAULT_BATCH_SIZE
    input_type: str = "image"  # "image" or "video"
    video_start_time: Optional[float] = None
    video_end_time: Optional[float] = None

class GenerateResponse(BaseModel):
    status: str
    task_id: str
    output_path: Optional[str] = None
    frames_generated: Optional[int] = None
    message: Optional[str] = None
    frames_with_faces: Optional[int] = None
    total_frames: Optional[int] = None


# Realtime generation models
class PrepareRealtimeRequest(BaseModel):
    prep_id: str
    video_path: str
    bbox_shift: int = 0


class PrepareRealtimeResponse(BaseModel):
    status: str
    prep_id: str
    num_frames: Optional[int] = None
    valid_frames: Optional[int] = None
    smoothing_enabled: Optional[bool] = None
    message: Optional[str] = None


class GenerateRealtimeRequest(BaseModel):
    task_id: str
    prep_id: str
    audio_path: str
    output_path: str
    fps: int = 25


class GenerateRealtimeResponse(BaseModel):
    status: str
    task_id: str
    prep_id: str
    output_path: Optional[str] = None
    frames_generated: Optional[int] = None
    generation_time: Optional[float] = None
    fps_achieved: Optional[float] = None
    message: Optional[str] = None

@model_app.on_event("startup")
async def startup_event():
    """Load models on startup"""
    logger.info("=" * 50)
    logger.info("Starting MuseTalk Model Server...")
    logger.info(f"Server will run on {settings.MODEL_SERVER_HOST}:{settings.MODEL_SERVER_PORT}")
    logger.info(f"MuseTalk directory: {settings.MUSETALK_DIR}")
    logger.info(f"Models directory: {settings.MODELS_DIR}")
    logger.info(f"Storage directory: {settings.STORAGE_DIR}")
    logger.info("=" * 50)
    
    settings.init_dirs()
    
    # Load models in background
    asyncio.create_task(load_models_async())

async def load_models_async():
    """Load models asynchronously"""
    try:
        logger.info("Starting model loading process...")
        success = musetalk_model.load_models()
        if success:
            logger.info("🚀 Models loaded successfully! Model server ready to process requests.")
        else:
            logger.error("❌ Failed to load models")
    except Exception as e:
        import traceback
        logger.error(f"❌ Error loading models: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")

@model_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return musetalk_model.health_check()

@model_app.post("/generate", response_model=GenerateResponse)
async def generate_talking_head(request: GenerateRequest):
    """Generate talking head video"""
    try:
        logger.info(f"🎬 Received generation request for task: {request.task_id}")
        logger.info(f"  Input type: {request.input_type}")
        logger.info(f"  Image/Video: {request.image_path}")
        logger.info(f"  Audio: {request.audio_path}")
        logger.info(f"  Output: {request.output_path}")
        logger.info(f"  Parameters: bbox_shift={request.bbox_shift}, fps={request.fps}, batch_size={request.batch_size}")
        
        if request.input_type == "video":
            logger.info(f"  Video time: {request.video_start_time}s to {request.video_end_time}s")
            
            result = musetalk_model.generate_video_to_video(
                video_path=request.image_path,
                audio_path=request.audio_path,
                output_path=request.output_path,
                bbox_shift=request.bbox_shift,
                fps=request.fps,
                batch_size=request.batch_size,
                start_time=request.video_start_time or 0,
                end_time=request.video_end_time
            )
        else:
            result = musetalk_model.generate_talking_head(
                image_path=request.image_path,
                audio_path=request.audio_path,
                output_path=request.output_path,
                bbox_shift=request.bbox_shift,
                fps=request.fps,
                batch_size=request.batch_size
            )
        
        response = GenerateResponse(
            status=result['status'],
            task_id=request.task_id,
            output_path=result.get('output_path'),
            frames_generated=result.get('frames_generated'),
            message=result.get('message'),
            frames_with_faces=result.get('frames_with_faces'),
            total_frames=result.get('total_frames')
        )
        
        if result['status'] == 'success':
            logger.info(f"✅ Task {request.task_id} completed successfully")
            if request.input_type == "video":
                logger.info(f"  Frames: {result.get('frames_with_faces')}/{result.get('total_frames')} had faces")
        else:
            logger.error(f"❌ Task {request.task_id} failed: {result.get('message')}")
            
        return response
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error in generate endpoint: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@model_app.post("/prepare_realtime", response_model=PrepareRealtimeResponse)
async def prepare_realtime_video(request: PrepareRealtimeRequest):
    """Prepare video for realtime generation"""
    try:
        logger.info(f"🚀 Received realtime preparation request: {request.prep_id}")
        logger.info(f"  Video: {request.video_path}")
        logger.info(f"  Bbox shift: {request.bbox_shift}")
        
        result = musetalk_model.prepare_realtime_video(
            video_path=request.video_path,
            prep_id=request.prep_id,
            bbox_shift=request.bbox_shift
        )
        
        response = PrepareRealtimeResponse(
            status=result['status'],
            prep_id=request.prep_id,
            num_frames=result.get('num_frames'),
            valid_frames=result.get('valid_frames'),
            smoothing_enabled=result.get('smoothing_enabled'),
            message=result.get('message')
        )
        
        if result['status'] == 'success':
            logger.info(f"✅ Realtime preparation completed: {request.prep_id}")
        else:
            logger.error(f"❌ Realtime preparation failed: {result.get('message')}")
        
        return response
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error in prepare_realtime endpoint: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@model_app.post("/generate_realtime", response_model=GenerateRealtimeResponse)
async def generate_realtime_video(request: GenerateRealtimeRequest):
    """Generate video using realtime preparation - ultra fast!"""
    try:
        logger.info(f"⚡ Received realtime generation request: {request.task_id}")
        logger.info(f"  Prep ID: {request.prep_id}")
        logger.info(f"  Audio: {request.audio_path}")
        logger.info(f"  Output: {request.output_path}")
        logger.info(f"  FPS: {request.fps}")
        
        result = musetalk_model.generate_realtime_video(
            prep_id=request.prep_id,
            audio_path=request.audio_path,
            output_path=request.output_path,
            fps=request.fps
        )
        
        response = GenerateRealtimeResponse(
            status=result['status'],
            task_id=request.task_id,
            prep_id=request.prep_id,
            output_path=result.get('output_path'),
            frames_generated=result.get('frames_generated'),
            generation_time=result.get('generation_time'),
            fps_achieved=result.get('fps_achieved'),
            message=result.get('message')
        )
        
        if result['status'] == 'success':
            logger.info(f"✅ Realtime generation completed: {request.task_id}")
            logger.info(f"   FPS achieved: {result.get('fps_achieved', 'N/A')}")
        else:
            logger.error(f"❌ Realtime generation failed: {result.get('message')}")
        
        return response
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error in generate_realtime endpoint: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@model_app.get("/realtime/preparations")
async def list_realtime_preparations():
    """List available realtime preparations"""
    try:
        if not musetalk_model.realtime_cache:
            return {
                "status": "disabled",
                "message": "Realtime mode not enabled",
                "preparations": []
            }
        
        # Get statistics and preparation list
        stats = musetalk_model.realtime_cache.get_statistics()
        
        # Get preparation metadata
        preparations = []
        for prep_id, info in musetalk_model.realtime_cache.metadata.items():
            # Try to load metadata for each preparation
            try:
                prep_data = musetalk_model.realtime_cache.load_preparation(prep_id)
                if prep_data and 'metadata' in prep_data:
                    metadata = prep_data['metadata']
                    preparations.append({
                        'prep_id': prep_id,
                        'created_at': metadata.get('created_at'),
                        'video_path': metadata.get('video_path'),
                        'num_frames': metadata.get('num_frames'),
                        'valid_frames': metadata.get('valid_frames'),
                        'version': metadata.get('version'),
                        'uses': info.get('uses', 0),
                        'last_used': info.get('last_used'),
                        'size_mb': round(info.get('size', 0) / (1024*1024), 2)
                    })
            except:
                # Skip corrupted preparations
                continue
        
        return {
            "status": "success",
            "preparations": preparations,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Error listing preparations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@model_app.delete("/realtime/preparations/{prep_id}")
async def delete_realtime_preparation(prep_id: str):
    """Delete a realtime preparation"""
    try:
        if not musetalk_model.realtime_cache:
            raise HTTPException(
                status_code=503,
                detail="Realtime mode not enabled"
            )
        
        success = musetalk_model.realtime_cache.delete_preparation(prep_id)
        
        if success:
            logger.info(f"🗑️ Deleted realtime preparation: {prep_id}")
            return {
                "status": "success",
                "message": f"Preparation {prep_id} deleted successfully"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Preparation {prep_id} not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting preparation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@model_app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "MuseTalk Model Server", "status": "running"}

if __name__ == "__main__":
    logger.info(f"Starting MuseTalk Model Server on {settings.MODEL_SERVER_HOST}:{settings.MODEL_SERVER_PORT}")
    uvicorn.run(
        model_app,
        host=settings.MODEL_SERVER_HOST,
        port=settings.MODEL_SERVER_PORT,
        log_level="info"
    )