# MuseTalk FastAPI Server

A production-ready FastAPI implementation for MuseTalk talking head video generation with scalable two-server architecture.

## 🏗️ Architecture

This implementation uses a **two-server design** for better scalability and resource management:

- **Model Server** (port 8001): Handles MuseTalk model loading and inference
- **Handler Server** (port 8000): Manages API requests, task queuing, and responses

### 🎯 Benefits of Two-Server Architecture

- **Scalability**: Multiple handler instances can share a single model server
- **Resource Management**: Efficient GPU memory usage with single model instance
- **Queue Management**: Built-in task queuing prevents GPU memory conflicts
- **Separation of Concerns**: API handling separate from computation
- **Background Processing**: Long-running tasks don't block API responses
- **Better Monitoring**: Separate logging and health checks for each component

## ✨ Features

- ✅ **Production-Ready**: Robust error handling, logging, and monitoring
- ✅ **Scalable Architecture**: Two-server design for better resource utilization  
- ✅ **Queue Management**: Configurable concurrent request limiting (default: 1)
- ✅ **Async Task Processing**: Background video generation with status tracking
- ✅ **Multiple Input Methods**: Support for local files and URLs
- ✅ **File Upload/Download**: Complete file management with validation
- ✅ **Health Monitoring**: Comprehensive health checks for both servers
- ✅ **Detailed Logging**: Separate log files for debugging and monitoring
- ✅ **Task Persistence**: Task status survives server restarts
- ✅ **Working Directory Management**: Proper handling of MuseTalk's relative paths
- ✅ **Flask Architecture Compliance**: Follows proven patterns from working Flask service
- ✅ **Google Cloud Storage Integration**: Automatic upload to GCS bucket with path tracking

## 📋 Prerequisites

1. **MuseTalk Setup**: Ensure MuseTalk is properly installed with `pip install -e .`
2. **Model Weights**: All model weights downloaded in `models/` directory
3. **CUDA GPU**: Available and working for inference
4. **Virtual Environment**: Python 3.10+ environment activated

## 🚀 Installation

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

## 🎬 Quick Start

### Start Both Servers

**Terminal 1 - Model Server (port 8001):**
```bash
cd /workspace/ai-video-generation/MuseTalk/fastapi_server
./start_model_server.sh
```
Wait for "🚀 Models loaded successfully! Model server ready to process requests." message.

**Terminal 2 - Handler Server (port 8000):**
```bash
cd /workspace/ai-video-generation/MuseTalk/fastapi_server  
./start_handler_server.sh
```

### Test the API

**Health Check:**
```bash
curl http://localhost:8000/api/v1/health | jq .
```

**Generate Video:**
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "/workspace/ai-video-generation/multimedia/image/test_image1-female.png",
    "audio": "/workspace/ai-video-generation/multimedia/audio/test_audio1-female.mp3",
    "user_id": "user123",
    "bbox_shift": 0,
    "fps": 25,
    "batch_size": 4
  }' | jq .
```

**Check Status:**
```bash
curl http://localhost:8000/api/v1/status/{task_id} | jq .
```

**Download Video:**
```bash
curl -o generated_video.mp4 http://localhost:8000/api/v1/video/{task_id}
```

## 📡 API Endpoints

### POST /api/v1/generate
Generate a talking head video.

**Request Body:**
```json
{
  "image": "/path/to/image.jpg or http://url.to/image.jpg",
  "audio": "/path/to/audio.mp3 or http://url.to/audio.mp3",
  "user_id": "unique_user_identifier",
  "bbox_shift": 0,
  "fps": 25,
  "batch_size": 8
}
```

**Parameter Details:**
- `image`: Local file path or URL to an image file (PNG, JPG, JPEG, GIF, BMP)
- `audio`: Local file path or URL to an audio file (WAV, MP3, AAC, M4A, OGG)
- `user_id`: **Required** - Unique identifier for the user making the request
- `bbox_shift`: Face bounding box shift value (default: 0)
- `fps`: Video frames per second (default: 25)
- `batch_size`: Processing batch size (default: 8)

**Important Notes:**
- ❌ **Video URLs are NOT supported** - The API will reject requests with video file URLs
- ✅ **URL downloads** - Image and audio files will be automatically downloaded from URLs
- ✅ **Local files** - Direct paths to files on the server are supported
- 📁 **Temp storage** - Downloaded files are stored temporarily per task

**Success Response:**
```json
{
  "status": "queued",
  "task_id": "c1b7134f-3798-4dce-8b0c-8505eb7c039f",
  "message": "Video generation queued (position 1). Use /status/{task_id} to check progress."
}
```

**Error Responses:**
```json
// Video URL provided (HTTP 400)
{
  "detail": "Invalid request: video not supported for image input. Please provide image URL or local path."
}

// Video URL provided for audio (HTTP 400)  
{
  "detail": "Invalid request: video not supported for audio input. Please provide audio URL or local path."
}

// File not found (HTTP 404)
{
  "detail": "Image file not found: /path/to/missing/file.jpg"
}
```

### GET /api/v1/status/{task_id}
Check task status.

**Response:**
```json
{
  "status": "completed",
  "task_id": "c1b7134f-3798-4dce-8b0c-8505eb7c039f",
  "created_at": "2025-08-10T18:09:59.228631",
  "started_at": "2025-08-10T18:09:59.232820",
  "completed_at": "2025-08-10T18:11:01.249045",
  "output_path": "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/videos/c1b7134f-3798-4dce-8b0c-8505eb7c039f/generated_c1b7134f-3798-4dce-8b0c-8505eb7c039f.mp4",
  "gcs_path": "gs://yral_ai_generated_videos/talking-head/c1b7134f-3798-4dce-8b0c-8505eb7c039f/output-100825.mp4",
  "error_message": null,
  "queue_position": null
}
```

**Status Values:**
- `pending`: Task created but not started
- `queued`: Task is waiting in queue for processing
- `processing`: Video generation in progress  
- `completed`: Video generation successful
- `failed`: Error occurred during processing

**Queue Management:**
- `queue_position`: Shows position in queue (1 = next to process, null when not queued)

### GET /api/v1/video/{task_id}
Download generated video.

**Response:** Video file download (MP4 format)

### POST /api/v1/upload
Upload image/audio files.

**Request:** Multipart form data with files

**Response:**
```json
{
  "status": "success",
  "file_path": "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/uploads/uuid/filename.jpg",
  "filename": "filename.jpg"
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
    "device": "cuda:0",
    "cuda_available": true
  },
  "tasks_count": 14
}
```

## ⚙️ Configuration

Edit `config/settings.py` to customize:

```python
class Settings:
    # Server ports
    MODEL_SERVER_HOST: str = "localhost"
    MODEL_SERVER_PORT: int = 8001
    HANDLER_SERVER_HOST: str = "0.0.0.0"
    HANDLER_SERVER_PORT: int = 8000
    
    # Model settings
    GPU_ID: int = 0
    USE_FLOAT16: bool = True
    MUSETALK_VERSION: str = "v15"
    
    # Generation settings
    DEFAULT_FPS: int = 25
    DEFAULT_BATCH_SIZE: int = 8
    DEFAULT_BBOX_SHIFT: int = 0
    
    # File limits
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    
    # Timeouts
    MODEL_SERVER_TIMEOUT: int = 300  # 5 minutes
    GENERATION_TIMEOUT: int = 600    # 10 minutes
    
    # Queue settings
    MAX_CONCURRENT_MODEL_REQUESTS: int = 1  # Only 1 request to model server at a time
    
    # Google Cloud Storage settings
    GCS_ENABLED: bool = True  # Enable/disable GCS upload
    GCS_BUCKET_NAME: str = "yral_ai_generated_videos"
    GCS_BASE_PATH: str = "talking-head"  # Base path in bucket
    GCP_CREDENTIALS: str = os.environ.get("GCP_CREDENTIALS", "")  # GCP credentials from environment
```

### 🌐 Google Cloud Storage Integration

The server now automatically uploads generated videos to Google Cloud Storage:

**Configuration:**
1. Set the `GCP_CREDENTIALS` environment variable with your service account JSON credentials
2. Videos are uploaded to: `gs://yral_ai_generated_videos/talking-head/<task_id>/output-ddmmyy.mp4`
3. The GCS path is returned in the status endpoint response

**Environment Setup:**
```bash
export GCP_CREDENTIALS='{"type": "service_account", "project_id": "...", ...}'
```

**Response with GCS path:**
- The `/api/v1/status/{task_id}` endpoint returns both local and GCS paths
- `output_path`: Local file path on the server
- `gcs_path`: Google Cloud Storage URI (gs://...)

### ⚙️ Queue Configuration

The system includes intelligent queue management to prevent GPU memory conflicts:

**Default Configuration:**
- **`MAX_CONCURRENT_MODEL_REQUESTS = 1`** - Only one request processes at a time
- **Queue Status**: Tasks show their position in queue
- **Sequential Processing**: Prevents GPU memory overload

**To modify concurrency** (only if you have multiple GPUs or sufficient memory):
```python
# In config/settings.py
MAX_CONCURRENT_MODEL_REQUESTS: int = 2  # Allow 2 concurrent requests
```

**Queue Behavior:**
1. Request submitted → Status: `queued` (with position)
2. Processing starts → Status: `processing` 
3. Video generated → Status: `completed`

## 📊 Monitoring & Logging

The system provides comprehensive logging across multiple files:

- **`model_server.log`**: Model server startup, inference, and errors
- **`handler_server.log`**: Handler server requests and responses
- **`endpoints.log`**: API endpoint activity and debugging
- **`musetalk_model.log`**: Detailed MuseTalk model processing
- **`queue_processor.log`**: Queue management and task processing

**Log Locations:**
```bash
# View real-time logs
tail -f /workspace/ai-video-generation/MuseTalk/fastapi_server/model_server.log
tail -f /workspace/ai-video-generation/MuseTalk/fastapi_server/handler_server.log
tail -f /workspace/ai-video-generation/MuseTalk/fastapi_server/endpoints.log
tail -f /workspace/ai-video-generation/MuseTalk/fastapi_server/musetalk_model.log
tail -f /workspace/ai-video-generation/MuseTalk/fastapi_server/queue_processor.log
```

## 🔧 Troubleshooting

### Common Issues

**1. Import Errors**
```bash
# Ensure MuseTalk is pip installed
cd /workspace/ai-video-generation/MuseTalk
pip install -e .

# Verify installation
python -c "from musetalk.utils.utils import load_all_model; print('OK')"
```

**2. Model Loading Fails**
```bash
# Check model files exist
ls models/
# Expected: dwpose  musetalkV15  sd-vae  whisper

# Verify CUDA availability
python -c "import torch; print('CUDA Available:', torch.cuda.is_available())"

# Check working directory issue
cd /workspace/ai-video-generation/MuseTalk && python -c "import os; print('MuseTalk dir:', os.getcwd())"
```

**3. Port Already in Use**
```bash
# Kill existing processes
lsof -i :8000
lsof -i :8001
kill -9 <PID>

# Or use different ports in config/settings.py
```

**4. File Not Found Errors**
```bash
# Check file paths are absolute
ls -la /workspace/ai-video-generation/multimedia/image/
ls -la /workspace/ai-video-generation/multimedia/audio/

# Verify file permissions
chmod 644 /path/to/your/files/*
```

**5. Video Generation Fails**
```bash
# Check GPU memory
nvidia-smi

# Reduce batch size in request
curl -X POST ... -d '{"batch_size": 2, ...}'

# Check detailed logs
tail -f musetalk_model.log
```

**6. Video URL Rejected**
```bash
# Error: "video not supported for image input"
# Solution: Use image URL instead
curl -X POST ... -d '{
  "image": "https://example.com/photo.jpg",  # ✅ Use image URL
  "audio": "https://example.com/audio.mp3", # ✅ Use audio URL
  "user_id": "user123"
}'

# ❌ This will be rejected:
curl -X POST ... -d '{
  "image": "https://example.com/video.mp4",  # ❌ Video URL not allowed
  "audio": "https://example.com/speech.wav",
  "user_id": "user123" 
}'
```

### Architecture-Specific Fixes

**Working Directory Issues:**
The FastAPI server now properly handles MuseTalk's relative path requirements by changing to the MuseTalk directory during model loading, exactly like the working Flask service.

**Model Loading Pattern:**
Uses the same pattern as Flask service - passes file paths (not numpy arrays) to `get_landmark_and_bbox()`.

## 📈 Performance Tips

- **GPU Memory**: Use `USE_FLOAT16=True` to reduce memory usage
- **Batch Size**: Adjust `batch_size` parameter based on GPU memory (2-8 recommended)
- **Concurrent Requests**: Handler server can process multiple requests, but model server processes one at a time
- **File Storage**: Videos are stored locally, consider implementing cloud storage for production

## 🚀 Production Deployment

For production deployments:

1. **Use Production ASGI Server**: Replace uvicorn with gunicorn + uvicorn workers
2. **Load Balancing**: Deploy multiple handler servers behind a load balancer
3. **Model Server Scaling**: Use one model server per GPU
4. **Persistent Storage**: Implement Redis/database for task persistence
5. **Monitoring**: Add Prometheus metrics and health checks
6. **Security**: Add authentication, rate limiting, and input validation

## 📚 Documentation

- **Architecture Details**: See `ARCHITECTURE.md` for system design and data flow diagrams
- **API Testing Guide**: See `/workspace/ai-video-generation/docs/talking-head-api-testing.md` for testing deployed services

---

**Status**: ✅ **Working and Tested** - Successfully generates talking head videos using proven Flask service patterns.

Choose FastAPI for production deployments requiring scalability, async processing, and comprehensive monitoring.