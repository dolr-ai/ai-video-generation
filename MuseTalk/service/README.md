# MuseTalk Flask API

A Flask-based REST API for generating talking head videos using MuseTalk.

## Features

- Generate talking head videos from images and audio
- Support for both URL and local file paths
- Real-time inference mode for faster generation
- Avatar-based generation for multiple audio clips
- Configurable output handling (local path or direct download)

## Installation

### Prerequisites
1. First, ensure MuseTalk is properly set up with `.venv` following the main setup instructions
2. Ensure all model weights are downloaded in `models/` directory
3. Verify CUDA GPU is available and working

### Exact Setup Steps (Working Configuration)

**Step 1: Navigate to MuseTalk directory and activate venv**
```bash
cd /path/to/MuseTalk
source ../.venv/bin/activate  # Assuming .venv is in parent directory
```

**Step 2: Install Flask service dependencies**
```bash
# Install Flask and required packages using uv (recommended)
uv pip install Flask flask-cors Werkzeug gunicorn

# Verify installation
python -c "import flask; print('Flask version:', flask.__version__)"
```

**Step 3: Verify environment**
```bash
# Check Python and packages
which python
python --version  # Should be 3.10.18
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

## Running the API

### Method 1: Direct Python execution with PYTHONPATH (Recommended - Tested Working)
```bash
# From MuseTalk root directory
cd /path/to/MuseTalk
source ../.venv/bin/activate
PYTHONPATH=. python service/run.py
```

### Method 2: Using pip install -e (Alternative)
```bash
cd MuseTalk
pip install -e .
python service/run.py
```

**Note**: Method 1 is recommended as it has been tested and works reliably with the current setup.

The startup script supports several options:
```bash
# Use default settings (.venv, port 5000, all interfaces)
./start.sh

# Use specific virtual environment
./start.sh /path/to/venv

# Use custom port
./start.sh .venv 8080

# Use custom host (local only)
./start.sh .venv 5000 127.0.0.1
```

### 3. Direct Python execution
```bash
cd MuseTalk/service
python run.py
```

### 4. Using Flask CLI
```bash
cd MuseTalk/service
python -m flask --app app run --host=0.0.0.0 --port=5000
```

The API will start on `http://localhost:5000` by default.

**Expected Output:**
```
Loads checkpoint by local backend from path: ./models/dwpose/dw-ll_ucoco_384.pth
cuda start
Starting MuseTalk Flask API on http://0.0.0.0:5000
Health check: http://0.0.0.0:5000/api/v1/health
 * Serving Flask app 'service.app'
 * Debug mode: on
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://172.17.0.2:5000
```

## Quick Start Testing

### Test 1: Health Check
```bash
curl -X GET http://localhost:5000/api/v1/health
```

Expected response:
```json
{
  "service": "MuseTalk API",
  "status": "healthy",
  "version": "v15"
}
```

### Test 2: Generate Talking Head (Tested Working)
```bash
# Test with your own image and audio files
curl -X POST http://localhost:5000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "/path/to/your/image.png",
    "audio": "/path/to/your/audio.mp3",
    "local_dev": true,
    "bbox_shift": 0,
    "fps": 25,
    "batch_size": 8
  }'
```

Expected response:
```json
{
  "message": "Talking head generated successfully",
  "output_path": "/workspace/ai-video-generation/MuseTalk/results/api/temp/[task-id]/filename.mp4",
  "status": "success",
  "task_id": "[unique-task-id]"
}
```

**Note**: Video generation takes approximately 1-2 minutes depending on audio length and system performance.

## API Endpoints

### 1. Health Check
- **GET** `/api/v1/health`
- Returns the service status

### 2. Generate Talking Head
- **POST** `/api/v1/generate`
- Generate a talking head video from an image and audio

**Request Body:**
```json
{
    "image": "path/to/image.jpg or https://example.com/image.jpg",
    "audio": "path/to/audio.wav or https://example.com/audio.wav",
    "script": "Optional text script for the talking head",
    "local_dev": true,
    "bbox_shift": 0,
    "realtime": false,
    "fps": 25,
    "batch_size": 8
}
```

**Response (when local_dev=true):**
```json
{
    "status": "success",
    "task_id": "unique-task-id",
    "output_path": "/path/to/output/video.mp4",
    "message": "Talking head generated successfully"
}
```

**Response (when local_dev=false):**
- Direct file download of the generated video

### 3. Generate Real-time
- **POST** `/api/v1/generate_realtime`
- Generate talking heads using real-time inference with avatar caching

**Request Body:**
```json
{
    "avatar_id": "unique_avatar_id",
    "video": "path/to/video.mp4 or https://example.com/video.mp4",
    "audio_clips": [
        "path/to/audio1.wav",
        "path/to/audio2.wav"
    ],
    "preparation": true,
    "bbox_shift": 0,
    "local_dev": true
}
```

**Response:**
```json
{
    "status": "success",
    "task_id": "unique-task-id",
    "avatar_id": "unique_avatar_id",
    "outputs": [
        {
            "audio_path": "path/to/audio1.wav",
            "output_path": "/path/to/output1.mp4",
            "status": "success"
        },
        {
            "audio_path": "path/to/audio2.wav",
            "output_path": "/path/to/output2.mp4",
            "status": "success"
        }
    ],
    "message": "Real-time talking heads generated successfully"
}
```

### 4. Upload File
- **POST** `/api/v1/upload`
- Upload files directly to the server

**Request:**
- Multipart form data with file field

**Response:**
```json
{
    "status": "success",
    "upload_id": "unique-upload-id",
    "file_path": "/path/to/uploaded/file",
    "filename": "uploaded_file.ext"
}
```

## Testing the API

Run the test script to verify the API is working:

```bash
cd MuseTalk/service
python test_api.py
```

The test script will:
- Check the health endpoint
- Test file upload functionality  
- Test video generation with local sample files
- Verify all core API functionality

## Configuration

Edit `config/settings.py` to customize:

- Model paths
- FFmpeg location
- GPU settings
- Output directories
- File size limits
- Default parameters

## Usage Examples

### Python Example

```python
import requests
import json

# Generate talking head
url = "http://localhost:5000/api/v1/generate"
data = {
    "image": "https://example.com/person.jpg",
    "audio": "https://example.com/speech.wav",
    "local_dev": True,
    "bbox_shift": 0,
    "fps": 25
}

response = requests.post(url, json=data)
result = response.json()
print(f"Generated video at: {result['output_path']}")
```

### cURL Example

```bash
# Generate talking head
curl -X POST http://localhost:5000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "/path/to/local/image.jpg",
    "audio": "/path/to/local/audio.wav",
    "local_dev": true
  }'

# Upload file
curl -X POST http://localhost:5000/api/v1/upload \
  -F "file=@/path/to/file.jpg"
```

## Environment Variables

- `PORT` - API port (default: 5000)
- `FLASK_DEBUG` - Enable debug mode (default: True)
- `SECRET_KEY` - Flask secret key

## Notes

1. **First Run**: The first API call will load the models, which may take some time.
2. **GPU Memory**: Ensure sufficient GPU memory (recommended 8GB+) for model inference.
3. **FFmpeg**: Required for video processing. The API will use the bundled FFmpeg or system installation.
4. **File Formats**: 
   - Images: png, jpg, jpeg, gif, bmp
   - Audio: wav, mp3, aac, m4a, ogg
   - Video: mp4, avi, mov, mkv, webm

## Troubleshooting

### Common Issues and Solutions

1. **ModuleNotFoundError: No module named 'service'**
   - **Solution**: Use PYTHONPATH method: `PYTHONPATH=. python service/run.py`
   - **Cause**: Python can't find the service module without proper path configuration

2. **Flask/Dependencies Installation Issues**
   - **Solution**: Use uv instead of pip: `uv pip install Flask flask-cors Werkzeug gunicorn`
   - **Alternative**: Install packages individually if batch install fails

3. **Model Loading Issues**: 
   - Ensure all model weights are downloaded in `/MuseTalk/models/`
   - Check directory structure matches requirements
   - Verify CUDA memory availability (8GB+ recommended)

4. **NumPy Compatibility Warnings**: 
   - These are warnings, not errors - service will still work
   - Related to TensorFlow/NumPy version compatibility

5. **FFmpeg Errors**: 
   - Service uses system FFmpeg automatically
   - Verify installation: `ffmpeg -version`

6. **GPU/CUDA Errors**: 
   - Verify CUDA availability: `python -c "import torch; print(torch.cuda.is_available())"`
   - Check GPU memory usage during inference

7. **Service Startup Takes Long Time**:
   - First startup loads all models (~30-60 seconds)
   - Subsequent requests are much faster
   - Models remain loaded in memory

### Performance Notes
- **First Request**: ~2-3 minutes (model loading + inference)
- **Subsequent Requests**: ~30-60 seconds (inference only)
- **GPU Memory**: Requires ~6-8GB VRAM for optimal performance

## cURL Test Commands

### 1. Health Check
```bash
curl -X GET http://localhost:5000/api/v1/health
```

### 2. Upload a file
```bash
curl -X POST http://localhost:5000/api/v1/upload \
  -F "file=@/path/to/your/image.jpg"
```

### 3. Generate talking head with local files
```bash
curl -X POST http://localhost:5000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "/path/to/local/image.jpg",
    "audio": "/path/to/local/audio.wav",
    "local_dev": true,
    "bbox_shift": 0,
    "fps": 25,
    "batch_size": 8
  }'
```

### 4. Generate talking head with URLs
```bash
curl -X POST http://localhost:5000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "https://example.com/person.jpg",
    "audio": "https://example.com/speech.wav",
    "local_dev": false,
    "realtime": false
  }' \
  --output generated_video.mp4
```

### 5. Real-time generation with avatar
```bash
curl -X POST http://localhost:5000/api/v1/generate_realtime \
  -H "Content-Type: application/json" \
  -d '{
    "avatar_id": "my_avatar_001",
    "video": "/path/to/source/video.mp4",
    "audio_clips": [
      "/path/to/audio1.wav",
      "/path/to/audio2.wav"
    ],
    "preparation": true,
    "bbox_shift": 0,
    "local_dev": true
  }'
```

### 6. Test with sample data (if available)
```bash
# First upload an image
IMAGE_RESPONSE=$(curl -s -X POST http://localhost:5000/api/v1/upload \
  -F "file=@/path/to/test/image.jpg")
IMAGE_PATH=$(echo $IMAGE_RESPONSE | jq -r '.file_path')

# Then upload audio
AUDIO_RESPONSE=$(curl -s -X POST http://localhost:5000/api/v1/upload \
  -F "file=@/path/to/test/audio.wav")
AUDIO_PATH=$(echo $AUDIO_RESPONSE | jq -r '.file_path')

# Generate video using uploaded files
curl -X POST http://localhost:5000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d "{
    \"image\": \"$IMAGE_PATH\",
    \"audio\": \"$AUDIO_PATH\",
    \"local_dev\": true
  }"
```

### 7. Download generated video (when local_dev=false)
```bash
curl -X POST http://localhost:5000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "/path/to/image.jpg",
    "audio": "/path/to/audio.wav",
    "local_dev": false
  }' \
  --output talking_head_$(date +%s).mp4
```

## Tested Configuration

### Verified Working Setup
**Environment**: 
- Python 3.10.18
- CUDA 11.8
- PyTorch 2.0.1+cu118
- Flask 3.1.1
- Ubuntu Linux

**Tested Commands** (logged in `commands.log`):
```bash
# Setup
cd /workspace/ai-video-generation/MuseTalk
source ../.venv/bin/activate
uv pip install Flask flask-cors Werkzeug gunicorn

# Run service
PYTHONPATH=. python service/run.py

# Test API
curl -X GET http://localhost:5000/api/v1/health
curl -X POST http://localhost:5000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "/path/to/image.png",
    "audio": "/path/to/audio.mp3",
    "local_dev": true,
    "bbox_shift": 0,
    "fps": 25,
    "batch_size": 8
  }'
```

**Test Results**:
- ✅ Health endpoint responds correctly
- ✅ Video generation completes successfully
- ✅ Output files generated in `results/api/temp/` directory
- ✅ CUDA GPU acceleration working
- ✅ Both male and female test cases successful

**Generated Video Examples**:
- Female: 1.0MB MP4, ~3 seconds duration
- Male: 1.1MB MP4, ~3 seconds duration
- Processing time: ~60-90 seconds per video

**Last Updated**: 2025-08-10 - Tested and verified working configuration

