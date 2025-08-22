import asyncio
import logging
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.musetalk_model import MuseTalkModel
from config.settings import settings

# Setup comprehensive logging for model server
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create separate file logger for model server
model_server_logger = logging.getLogger('model_server')
model_server_handler = logging.FileHandler(os.path.join(settings.FASTAPI_SERVER_DIR, 'model_server.log'))
model_server_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
model_server_logger.addHandler(model_server_handler)
model_server_logger.setLevel(logging.DEBUG)

# Also create a console handler
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
    image_path: str
    audio_path: str
    output_path: str
    bbox_shift: int = settings.DEFAULT_BBOX_SHIFT
    fps: int = settings.DEFAULT_FPS
    batch_size: int = settings.DEFAULT_BATCH_SIZE

class GenerateResponse(BaseModel):
    status: str
    task_id: str
    output_path: Optional[str] = None
    frames_generated: Optional[int] = None
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
        logger.info(f"  Image: {request.image_path}")
        logger.info(f"  Audio: {request.audio_path}")
        logger.info(f"  Output: {request.output_path}")
        logger.info(f"  Parameters: bbox_shift={request.bbox_shift}, fps={request.fps}, batch_size={request.batch_size}")
        
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
            message=result.get('message')
        )
        
        if result['status'] == 'success':
            logger.info(f"✅ Task {request.task_id} completed successfully")
        else:
            logger.error(f"❌ Task {request.task_id} failed: {result.get('message')}")
            
        return response
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error in generate endpoint: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
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