# MuseTalk Flask API

A Flask-based REST API for generating talking head videos using MuseTalk.

## Features

- Generate talking head videos from images and audio
- Support for both URL and local file paths
- Real-time inference mode for faster generation
- Avatar-based generation for multiple audio clips
- Configurable output handling (local path or direct download)

## Installation

1. First, ensure MuseTalk is properly set up following the instructions in `docs/setup.md`

2. Install the MuseTalk package in development mode (this handles all imports properly):
```bash
cd MuseTalk
pip install -e .
```

This will install:
- MuseTalk core package with all dependencies
- Flask API service with all its dependencies  
- Console scripts for easy access

Alternatively, if you want to install just the service dependencies:
```bash
cd MuseTalk/service  
pip install -r requirements.txt
# But you'll still need: pip install -e .. from MuseTalk root
```

## Running the API

After installing with `pip install -e .`, you have multiple options:

### 1. Using console script (easiest)
```bash
musetalk-api
```

### 2. Using the startup script (with environment checks)
```bash
cd MuseTalk/service
./start.sh
```

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

1. **Model Loading Issues**: Ensure all model weights are downloaded in `/MuseTalk/models/`
2. **FFmpeg Errors**: Check FFmpeg installation and path configuration
3. **GPU Errors**: Verify CUDA installation and GPU availability
4. **Memory Issues**: Reduce batch_size or use float16 precision