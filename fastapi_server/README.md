# MuseTalk FastAPI Server

A FastAPI-based server architecture for generating talking head videos using MuseTalk. The system uses a two-server architecture to separate model inference from request handling for better scalability and performance.

## Architecture Overview

### Two-Server Design
1. **Model Server** (`model_server.py`) - Runs on port 8001
   - Loads and manages MuseTalk models (VAE, UNet, Whisper, etc.)
   - Handles heavy inference computations
   - Single instance to manage GPU memory efficiently
   
2. **Handler Server** (`handler_server.py`) - Runs on port 8000
   - Handles HTTP requests and responses
   - Manages file uploads and downloads
   - Tracks generation task status
   - Communicates with model server for inference

### Benefits of This Architecture
- **Scalability**: Multiple handler instances can share one model server
- **Resource Management**: Model loading is centralized and GPU memory is managed efficiently
- **Separation of Concerns**: API handling is separate from computation
- **Background Processing**: Long-running generations don't block API responses

## Project Structure

```
fastapi_server/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── start_model_server.sh     # Script to start model server
├── start_handler_server.sh   # Script to start handler server
├── model_server.py          # Model server (port 8001)
├── handler_server.py        # Handler server (port 8000)
├── api/
│   ├── __init__.py
│   └── endpoints.py         # API route definitions
├── core/
│   ├── __init__.py
│   ├── musetalk_model.py    # MuseTalk model wrapper
│   └── task_manager.py      # Task status management
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration settings
├── utils/
│   ├── __init__.py
│   └── file_utils.py        # File handling utilities
├── storage/                 # Created at runtime
│   ├── temp/               # Temporary files during processing
│   ├── videos/             # Final generated videos
│   ├── uploads/            # Uploaded files
│   └── tasks.json          # Task status persistence
└── models/                  # Placeholder for future local models
```

## Prerequisites

1. **MuseTalk Setup**: Ensure MuseTalk is properly set up with `.venv` in the root directory
2. **Model Weights**: All MuseTalk model weights should be downloaded in `MuseTalk/models/`
3. **CUDA GPU**: Required for efficient inference
4. **FFmpeg**: Required for video processing (should be available from MuseTalk setup)

## Installation and Setup

### Step 1: Navigate to FastAPI Server Directory
```bash
cd /workspace/ai-video-generation/fastapi_server
```

### Step 2: Activate Virtual Environment
```bash
source ../.venv/bin/activate
```

### Step 3: Install FastAPI Dependencies
```bash
# Install additional dependencies for FastAPI
uv pip install -r requirements.txt
```

### Step 4: Verify Environment
```bash
# Check Python and CUDA
python --version  # Should be 3.10.18
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"

# Check MuseTalk models exist
ls -la ../MuseTalk/models/
```

## Running the Servers

### Method 1: Using Startup Scripts (Recommended)

**Terminal 1 - Start Model Server:**
```bash
cd /workspace/ai-video-generation/fastapi_server
./start_model_server.sh
```

**Terminal 2 - Start Handler Server:**
```bash
cd /workspace/ai-video-generation/fastapi_server
./start_handler_server.sh
```

### Method 2: Manual Startup

**Terminal 1 - Model Server:**
```bash
cd /workspace/ai-video-generation/fastapi_server
source ../.venv/bin/activate
export PYTHONPATH="../:../MuseTalk:$PYTHONPATH"
python model_server.py
```

**Terminal 2 - Handler Server:**
```bash
cd /workspace/ai-video-generation/fastapi_server
source ../.venv/bin/activate
export PYTHONPATH=".:$PYTHONPATH"
python handler_server.py
```

### Expected Output

**Model Server:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Loading MuseTalk models...
INFO:     Models loaded successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://localhost:8001 (Press CTRL+C to quit)
```

**Handler Server:**
```
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Starting MuseTalk Handler Server...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## API Endpoints

Base URL: `http://localhost:8000/api/v1`

### 1. Generate Video (POST /api/v1/generate)

Generate a talking head video from image and audio.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "/path/to/image.jpg",
    "audio": "/path/to/audio.wav",
    "bbox_shift": 0,
    "fps": 25,
    "batch_size": 8
  }'
```

**Response:**
```json
{
  "status": "accepted",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Video generation started. Use /status/{task_id} to check progress."
}
```

**Parameters:**
- `image` (string): Local file path or URL to image
- `audio` (string): Local file path or URL to audio
- `bbox_shift` (integer, optional): Face bounding box adjustment (default: 0)
- `fps` (integer, optional): Output video frame rate (default: 25)
- `batch_size` (integer, optional): Processing batch size (default: 8)

### 2. Check Status (GET /api/v1/status/{task_id})

Check the status of a generation task.

**Request:**
```bash
curl -X GET http://localhost:8000/api/v1/status/550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```json
{
  "status": "completed",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2025-08-10T15:30:00.000Z",
  "started_at": "2025-08-10T15:30:05.000Z",
  "completed_at": "2025-08-10T15:32:30.000Z",
  "output_path": "/workspace/ai-video-generation/fastapi_server/storage/videos/550e8400-e29b-41d4-a716-446655440000/generated_550e8400-e29b-41d4-a716-446655440000.mp4",
  "error_message": null
}
```

**Status Values:**
- `pending`: Task created, waiting to start
- `processing`: Task is currently being processed
- `completed`: Task completed successfully
- `failed`: Task failed (check error_message)

### 3. Download Video (GET /api/v1/video/{task_id})

Download the generated video file.

**Request:**
```bash
curl -X GET http://localhost:8000/api/v1/video/550e8400-e29b-41d4-a716-446655440000 \
  --output generated_video.mp4
```

**Response:**
- Downloads the MP4 video file directly
- Returns 404 if task not found or not completed
- Returns 400 if task not yet completed

### 4. Upload File (POST /api/v1/upload)

Upload an image or audio file to use in generation.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@/path/to/your/image.jpg"
```

**Response:**
```json
{
  "status": "success",
  "file_path": "/workspace/ai-video-generation/fastapi_server/storage/uploads/123e4567-e89b-12d3-a456-426614174000/image.jpg",
  "filename": "image.jpg"
}
```

### 5. Health Check (GET /api/v1/health)

Check the health of both servers.

**Request:**
```bash
curl -X GET http://localhost:8000/api/v1/health
```

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
  "tasks_count": 5
}
```

## Usage Examples

### Example 1: Generate with Local Files

```bash
# 1. Start both servers (in separate terminals)
./start_model_server.sh
./start_handler_server.sh

# 2. Generate video
TASK_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "/workspace/ai-video-generation/multimedia/image/test_image1-female.png",
    "audio": "/workspace/ai-video-generation/multimedia/audio/test_audio1-female.mp3",
    "fps": 25,
    "batch_size": 8
  }')

TASK_ID=$(echo $TASK_RESPONSE | jq -r '.task_id')
echo "Task ID: $TASK_ID"

# 3. Check status
curl -X GET http://localhost:8000/api/v1/status/$TASK_ID

# 4. Download video when completed
curl -X GET http://localhost:8000/api/v1/video/$TASK_ID --output generated_video.mp4
```

### Example 2: Upload Files First

```bash
# Upload image
IMAGE_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/upload \
  -F "file=@/path/to/image.jpg")
IMAGE_PATH=$(echo $IMAGE_RESPONSE | jq -r '.file_path')

# Upload audio
AUDIO_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/upload \
  -F "file=@/path/to/audio.wav")
AUDIO_PATH=$(echo $AUDIO_RESPONSE | jq -r '.file_path')

# Generate video using uploaded files
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d "{
    \"image\": \"$IMAGE_PATH\",
    \"audio\": \"$AUDIO_PATH\"
  }"
```

### Example 3: Generate with URLs

```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "https://example.com/person.jpg",
    "audio": "https://example.com/speech.wav"
  }'
```

### Example 4: Python Client

```python
import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8000/api/v1"

def generate_video(image_path, audio_path):
    # Start generation
    response = requests.post(f"{BASE_URL}/generate", json={
        "image": image_path,
        "audio": audio_path,
        "fps": 25,
        "batch_size": 8
    })
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return None
    
    task_data = response.json()
    task_id = task_data['task_id']
    print(f"Task created: {task_id}")
    
    # Poll for completion
    while True:
        status_response = requests.get(f"{BASE_URL}/status/{task_id}")
        status_data = status_response.json()
        
        print(f"Status: {status_data['status']}")
        
        if status_data['status'] == 'completed':
            print("Generation completed!")
            break
        elif status_data['status'] == 'failed':
            print(f"Generation failed: {status_data['error_message']}")
            return None
        
        time.sleep(5)  # Wait 5 seconds before checking again
    
    # Download video
    video_response = requests.get(f"{BASE_URL}/video/{task_id}")
    with open(f"generated_{task_id}.mp4", "wb") as f:
        f.write(video_response.content)
    
    print(f"Video saved as generated_{task_id}.mp4")
    return task_id

# Usage
task_id = generate_video(
    "/path/to/image.jpg",
    "/path/to/audio.wav"
)
```

## Configuration

Edit `config/settings.py` to customize:

- **Server Ports**: Change `MODEL_SERVER_PORT` and `HANDLER_SERVER_PORT`
- **File Paths**: Modify `STORAGE_DIR`, `MUSETALK_DIR`, etc.
- **Model Settings**: Adjust `DEFAULT_FPS`, `DEFAULT_BATCH_SIZE`, `USE_FLOAT16`
- **Timeouts**: Configure `MODEL_SERVER_TIMEOUT`, `GENERATION_TIMEOUT`
- **File Limits**: Set `MAX_FILE_SIZE`, allowed extensions

## Monitoring and Logging

### View Server Logs
Both servers output detailed logs to console:
- Model loading progress
- Request processing status
- Error messages and stack traces

### Task Persistence
- Task status is saved to `storage/tasks.json`
- Tasks persist across server restarts
- Use cleanup functionality to remove old tasks

### Storage Management
- Temporary files: `storage/temp/`
- Generated videos: `storage/videos/`
- Uploaded files: `storage/uploads/`

## Troubleshooting

### Common Issues

1. **Model Server Won't Start**
   - Check if MuseTalk models are properly downloaded
   - Verify CUDA is available: `python -c "import torch; print(torch.cuda.is_available())"`
   - Check virtual environment activation

2. **Handler Server Can't Connect to Model Server**
   - Ensure model server is running on port 8001
   - Check firewall settings
   - Verify PYTHONPATH settings

3. **Generation Tasks Fail**
   - Check model server logs for detailed error messages
   - Verify input files exist and are accessible
   - Ensure sufficient GPU memory (8GB+ recommended)

4. **File Upload Issues**
   - Check file size limits (default 500MB)
   - Verify file extensions are allowed
   - Check disk space in storage directory

5. **Performance Issues**
   - First generation takes longer due to model loading
   - Adjust batch_size parameter (lower = less memory, slower)
   - Monitor GPU memory usage

### Performance Optimization

1. **Model Server Optimization**
   - Keep model server running to avoid reload overhead
   - Use float16 precision (enabled by default)
   - Monitor GPU memory and adjust batch sizes

2. **Handler Server Scaling**
   - Run multiple handler instances behind load balancer
   - All can connect to the same model server
   - Shared storage directory required

3. **Storage Optimization**
   - Regularly clean up old temporary files
   - Consider moving storage to faster disk
   - Implement file compression for uploads

## Development and Testing

### Running Tests

```bash
# Health check test
curl -X GET http://localhost:8000/api/v1/health

# Model server direct test
curl -X GET http://localhost:8001/health
```

### Development Mode

For development, you can run the servers with auto-reload:

```bash
# Model server with reload
uvicorn model_server:model_app --host localhost --port 8001 --reload

# Handler server with reload  
uvicorn handler_server:app --host 0.0.0.0 --port 8000 --reload
```

### API Documentation

Once the handler server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Production Deployment

### Recommended Setup

1. **Process Management**: Use supervisord or systemd
2. **Reverse Proxy**: Nginx for handling static files and load balancing
3. **Load Balancing**: Multiple handler servers behind load balancer
4. **Monitoring**: Prometheus + Grafana for metrics
5. **Logging**: Centralized logging with ELK stack

### Security Considerations

1. **File Validation**: Implement additional file type validation
2. **Rate Limiting**: Add rate limiting for API endpoints
3. **Authentication**: Implement API key or JWT authentication
4. **HTTPS**: Use TLS encryption for production
5. **Input Sanitization**: Validate all user inputs

### Scaling Guidelines

1. **Vertical Scaling**: More GPU memory for larger batch sizes
2. **Horizontal Scaling**: Multiple handler servers per model server
3. **Storage Scaling**: Use distributed storage for multiple instances
4. **Caching**: Implement result caching for repeated requests

---

## Summary

This FastAPI server provides a production-ready architecture for MuseTalk video generation with:

✅ **Separated model loading from request handling**  
✅ **Background task processing**  
✅ **Persistent task status tracking**  
✅ **File upload/download capabilities**  
✅ **RESTful API design**  
✅ **Comprehensive error handling**  
✅ **Scalable two-server architecture**  

The system is designed to handle multiple concurrent requests while efficiently managing GPU resources and providing real-time status updates for long-running video generation tasks.