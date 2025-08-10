# MuseTalk FastAPI Server

A production-ready FastAPI implementation for MuseTalk talking head video generation with scalable two-server architecture.

## Architecture

This implementation uses a **two-server design** for better scalability and resource management:

- **Model Server** (port 8001): Handles MuseTalk model loading and inference
- **Handler Server** (port 8000): Manages API requests, task queuing, and responses

### Benefits of Two-Server Architecture

- **Scalability**: Multiple handler instances can share a single model server
- **Resource Management**: Efficient GPU memory usage with single model instance
- **Separation of Concerns**: API handling separate from computation
- **Background Processing**: Long-running tasks don't block API responses
- **Better Monitoring**: Separate logging and health checks for each component

## Features

- ✅ **Production-Ready**: Robust error handling, logging, and monitoring
- ✅ **Scalable Architecture**: Two-server design for better resource utilization  
- ✅ **Async Task Processing**: Background video generation with status tracking
- ✅ **Multiple Input Methods**: Support for local files and URLs
- ✅ **File Upload/Download**: Complete file management with validation
- ✅ **Health Monitoring**: Comprehensive health checks for both servers
- ✅ **Detailed Logging**: Separate log files for debugging and monitoring
- ✅ **Task Persistence**: Task status survives server restarts

## Prerequisites

1. **MuseTalk Setup**: Ensure MuseTalk is properly installed with `pip install -e .`
2. **Model Weights**: All model weights downloaded in `models/` directory
3. **CUDA GPU**: Available and working for inference
4. **Virtual Environment**: Python 3.10+ environment activated

## Installation

### Step 1: Navigate to MuseTalk and activate environment

```bash
cd /workspace/ai-video-generation/MuseTalk
source ../.venv/bin/activate
```

### Step 2: Install FastAPI dependencies

```bash
cd fastapi_server
pip install -r requirements.txt
```

### Step 3: Verify model files exist

```bash
ls models/
# Should show: dwpose  musetalkV15  sd-vae  whisper
```

## Quick Start

### Start Both Servers

**Terminal 1 - Model Server (port 8001):**
```bash
cd /workspace/ai-video-generation/MuseTalk/fastapi_server
./start_model_server.sh
```
Wait for "Models loaded successfully" message.

**Terminal 2 - Handler Server (port 8000):**
```bash
cd /workspace/ai-video-generation/MuseTalk/fastapi_server  
./start_handler_server.sh
```

### Test the API

**Health Check:**
```bash
curl http://localhost:8000/api/v1/health
```

**Generate Video:**
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "/path/to/image.jpg",
    "audio": "/path/to/audio.mp3"
  }'
```

**Check Status:**
```bash
curl http://localhost:8000/api/v1/status/{task_id}
```

**Download Video:**
```bash
curl -O http://localhost:8000/api/v1/video/{task_id}
```

## API Endpoints

### POST /api/v1/generate
Generate a talking head video.

**Request Body:**
```json
{
  "image": "/path/to/image.jpg",
  "audio": "/path/to/audio.mp3", 
  "bbox_shift": 0,
  "fps": 25,
  "batch_size": 8
}
```

**Response:**
```json
{
  "status": "accepted",
  "task_id": "uuid-here",
  "message": "Video generation started..."
}
```

### GET /api/v1/status/{task_id}
Check task status.

**Response:**
```json
{
  "status": "completed",
  "task_id": "uuid-here", 
  "created_at": "2025-08-10T16:00:00",
  "started_at": "2025-08-10T16:00:01",
  "completed_at": "2025-08-10T16:02:30",
  "output_path": "/path/to/output.mp4"
}
```

### GET /api/v1/video/{task_id}
Download generated video.

**Response:** Video file download

### POST /api/v1/upload
Upload image/audio files.

**Request:** Multipart form data with files

**Response:**
```json
{
  "message": "Files uploaded successfully",
  "files": {
    "image": "/path/to/uploaded/image.jpg",
    "audio": "/path/to/uploaded/audio.mp3"
  }
}
```

### GET /api/v1/health
Health check for both servers.

**Response:**
```json
{
  "status": "healthy",
  "service": "MuseTalk Handler Server",
  "model_server": {
    "status": "healthy",
    "models_loaded": true,
    "device": "cuda:0"
  },
  "tasks_count": 0
}
```

## Configuration

Edit `config/settings.py` to customize:

```python
class Settings:
    # Server ports
    MODEL_SERVER_PORT: int = 8001
    HANDLER_SERVER_PORT: int = 8000
    
    # Model settings
    GPU_ID: int = 0
    USE_FLOAT16: bool = True
    DEFAULT_FPS: int = 25
    DEFAULT_BATCH_SIZE: int = 8
    
    # File limits
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
```

## Troubleshooting

### Common Issues

**1. Import Errors**
```bash
# Ensure MuseTalk is pip installed
cd /workspace/ai-video-generation/MuseTalk
pip install -e .
```

**2. Model Loading Fails**
```bash
# Check model files exist
ls models/
# Verify CUDA availability
python -c "import torch; print(torch.cuda.is_available())"
```

**3. Port Already in Use**
```bash
# Kill existing processes
lsof -i :8000
lsof -i :8001
kill -9 <PID>
```

Choose FastAPI for production deployments requiring scalability and reliability.