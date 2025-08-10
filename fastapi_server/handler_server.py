import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.endpoints import router as api_router
from config.settings import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    logger.info("Starting MuseTalk Handler Server...")
    settings.init_dirs()

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