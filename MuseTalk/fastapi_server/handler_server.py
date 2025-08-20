import logging
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.endpoints import router as api_router
from config.settings import settings
from core.queue_processor import queue_processor

# Setup comprehensive logging for handler server
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create separate file logger for handler server
handler_server_logger = logging.getLogger('handler_server')
handler_server_handler = logging.FileHandler(os.path.join(settings.FASTAPI_SERVER_DIR, 'handler_server.log'))
handler_server_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
handler_server_logger.addHandler(handler_server_handler)
handler_server_logger.setLevel(logging.DEBUG)

# Also create a console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - HANDLER_SERVER - %(levelname)s - %(message)s'))
handler_server_logger.addHandler(console_handler)

logger = handler_server_logger

# Create FastAPI app
app = FastAPI(
    title="MuseTalk Handler Server",
    description="FastAPI server for handling MuseTalk video generation requests",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("=" * 50)
    logger.info("🚀 Starting MuseTalk Handler Server...")
    logger.info(f"Server will run on {settings.HANDLER_SERVER_HOST}:{settings.HANDLER_SERVER_PORT}")
    logger.info(f"Model server endpoint: http://{settings.MODEL_SERVER_HOST}:{settings.MODEL_SERVER_PORT}")
    logger.info(f"Max concurrent model requests: {settings.MAX_CONCURRENT_MODEL_REQUESTS}")
    logger.info(f"FastAPI server directory: {settings.FASTAPI_SERVER_DIR}")
    logger.info(f"Storage directory: {settings.STORAGE_DIR}")
    logger.info("=" * 50)
    settings.init_dirs()
    
    # Start queue processor
    await queue_processor.start()
    logger.info("✅ Queue processor started")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down MuseTalk Handler Server...")
    await queue_processor.stop()
    logger.info("✅ Queue processor stopped")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "MuseTalk Handler Server",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    logger.info(f"Starting MuseTalk Handler Server on {settings.HANDLER_SERVER_HOST}:{settings.HANDLER_SERVER_PORT}")
    uvicorn.run(
        app,
        host=settings.HANDLER_SERVER_HOST,
        port=settings.HANDLER_SERVER_PORT,
        log_level="info"
    )