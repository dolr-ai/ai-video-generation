import asyncio
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.musetalk_model import MuseTalkModel
from config.settings import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize model
musetalk_model = MuseTalkModel()

# FastAPI app for model server
model_app = FastAPI(title="MuseTalk Model Server", version="1.0.0")

class GenerateRequest(BaseModel):
    task_id: str
    image_path: str
    audio_path: str
    output_path: str
    bbox_shift: int = 0
    fps: int = 25
    batch_size: int = 8

class GenerateResponse(BaseModel):
    status: str
    task_id: str
    output_path: Optional[str] = None
    frames_generated: Optional[int] = None
    message: Optional[str] = None

@model_app.on_event("startup")
async def startup_event():
    """Load models on startup"""
    logger.info("Starting MuseTalk Model Server...")
    settings.init_dirs()
    
    # Load models in background
    asyncio.create_task(load_models_async())

async def load_models_async():
    """Load models asynchronously"""
    try:
        logger.info("Loading MuseTalk models...")
        success = musetalk_model.load_models()
        if success:
            logger.info("Models loaded successfully")
        else:
            logger.error("Failed to load models")
    except Exception as e:
        logger.error(f"Error loading models: {str(e)}")

@model_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return musetalk_model.health_check()

@model_app.post("/generate", response_model=GenerateResponse)
async def generate_talking_head(request: GenerateRequest):
    """Generate talking head video"""
    try:
        logger.info(f"Received generation request for task: {request.task_id}")
        
        result = musetalk_model.generate_talking_head(
            image_path=request.image_path,
            audio_path=request.audio_path,
            output_path=request.output_path,
            bbox_shift=request.bbox_shift,
            fps=request.fps,
            batch_size=request.batch_size
        )
        
        return GenerateResponse(
            status=result['status'],
            task_id=request.task_id,
            output_path=result.get('output_path'),
            frames_generated=result.get('frames_generated'),
            message=result.get('message')
        )
        
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}")
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