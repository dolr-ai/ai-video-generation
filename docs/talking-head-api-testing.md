# MuseTalk Talking Head API Testing Guide

## Configuration

```bash
# Base URL - Get this from your service owner/administrator
BASE_URL="BASE_URL"  # Replace with your deployment URL

# For local testing, you might use:
# BASE_URL="http://localhost:8000"
```

**Note:** Contact your service administrator for the correct BASE_URL for your deployment.

## 1. Health Check

Check if the service is running and healthy:

```bash
curl -X GET ${BASE_URL}/api/v1/health | jq .
```

Expected response:
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
  "tasks_count": 0
}
```

## 2. Upload Files First (RECOMMENDED for local files)

Since local file paths don't exist on the remote server, you need to upload your files first:

### Step 1: Upload your image
```bash
# Upload a local image file
IMAGE_RESPONSE=$(curl -X POST ${BASE_URL}/api/v1/upload \
  -F "file=@./multimedia/image/test_image1-female.png")
echo "Image upload response: $IMAGE_RESPONSE"
IMAGE_PATH=$(echo $IMAGE_RESPONSE | jq -r '.file_path')
```

Expected response:
```json
{
  "status": "success",
  "file_path": "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/uploads/{uuid}/test_image1-female.png",
  "filename": "test_image1-female.png"
}
```

### Step 2: Upload your audio
```bash
# Upload a local audio file
AUDIO_RESPONSE=$(curl -X POST ${BASE_URL}/api/v1/upload \
  -F "file=@./multimedia/audio/test_audio1-female.mp3")
echo "Audio upload response: $AUDIO_RESPONSE"
AUDIO_PATH=$(echo $AUDIO_RESPONSE | jq -r '.file_path')
```

Expected response:
```json
{
  "status": "success",
  "file_path": "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/uploads/{uuid}/test_audio1-female.mp3",
  "filename": "test_audio1-female.mp3"
}
```

### Step 3: Generate video with uploaded files
```bash
# Use the file paths returned from upload responses
curl -X POST ${BASE_URL}/api/v1/generate \
  -H "Content-Type: application/json" \
  -d "{
    \"image\": \"$IMAGE_PATH\",
    \"audio\": \"$AUDIO_PATH\",
    \"bbox_shift\": 0,
    \"fps\": 25,
    \"batch_size\": 4
  }" | jq .
```

## 3. Generate Video with URLs

If your files are hosted online, you can use URLs directly:

```bash
curl -X POST ${BASE_URL}/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "https://example.com/path/to/image.jpg",
    "audio": "https://example.com/path/to/audio.mp3",
    "bbox_shift": 0,
    "fps": 25,
    "batch_size": 4
  }' | jq .
```

Expected response:
```json
{
  "status": "accepted",
  "task_id": "c1b7134f-3798-4dce-8b0c-8505eb7c039f",
  "message": "Video generation started. Use /status/{task_id} to check progress."
}
```

## 4. Check Task Status

Check the status of a video generation task:

```bash
# Save the task_id from the generation response
TASK_ID="c1b7134f-3798-4dce-8b0c-8505eb7c039f"  # Replace with actual task ID

curl -X GET ${BASE_URL}/api/v1/status/${TASK_ID} | jq .
```

Expected responses:

### Processing
```json
{
  "status": "processing",
  "task_id": "c1b7134f-3798-4dce-8b0c-8505eb7c039f",
  "created_at": "2025-08-10T18:09:59.228631",
  "started_at": "2025-08-10T18:09:59.232820",
  "completed_at": null,
  "output_path": null,
  "error_message": null
}
```

### Completed
```json
{
  "status": "completed",
  "task_id": "c1b7134f-3798-4dce-8b0c-8505eb7c039f",
  "created_at": "2025-08-10T18:09:59.228631",
  "started_at": "2025-08-10T18:09:59.232820",
  "completed_at": "2025-08-10T18:11:01.249045",
  "output_path": "/workspace/ai-video-generation/MuseTalk/fastapi_server/storage/videos/c1b7134f-3798-4dce-8b0c-8505eb7c039f/generated_c1b7134f-3798-4dce-8b0c-8505eb7c039f.mp4",
  "error_message": null
}
```

## 5. Download Generated Video

Download the generated video:

```bash
# Use the task_id from previous steps
curl -o generated_video.mp4 ${BASE_URL}/api/v1/video/${TASK_ID}
echo "Video saved as generated_video.mp4"
```

## Complete Workflow Example with Local Files

Here's a complete workflow script to generate a video using your local files:

```bash
#!/bin/bash

# Configuration
BASE_URL="BASE_URL"  # Update with your deployment URL
IMAGE_FILE="./multimedia/image/test_image1-female.png"
AUDIO_FILE="./multimedia/audio/test_audio1-female.mp3"

# 1. Upload image
echo "📤 Uploading image..."
IMAGE_RESPONSE=$(curl -s -X POST ${BASE_URL}/api/v1/upload \
  -F "file=@${IMAGE_FILE}")
IMAGE_PATH=$(echo $IMAGE_RESPONSE | jq -r '.file_path')
echo "✅ Image uploaded: $IMAGE_PATH"

# 2. Upload audio
echo "📤 Uploading audio..."
AUDIO_RESPONSE=$(curl -s -X POST ${BASE_URL}/api/v1/upload \
  -F "file=@${AUDIO_FILE}")
AUDIO_PATH=$(echo $AUDIO_RESPONSE | jq -r '.file_path')
echo "✅ Audio uploaded: $AUDIO_PATH"

# 3. Generate video
echo "🎬 Starting video generation..."
GENERATE_RESPONSE=$(curl -s -X POST ${BASE_URL}/api/v1/generate \
  -H "Content-Type: application/json" \
  -d "{
    \"image\": \"$IMAGE_PATH\",
    \"audio\": \"$AUDIO_PATH\",
    \"bbox_shift\": 0,
    \"fps\": 25,
    \"batch_size\": 4
  }")
TASK_ID=$(echo $GENERATE_RESPONSE | jq -r '.task_id')
echo "✅ Task created: $TASK_ID"

# 4. Check status (poll until completed)
echo "⏳ Waiting for video generation..."
while true; do
  STATUS_RESPONSE=$(curl -s ${BASE_URL}/api/v1/status/${TASK_ID})
  STATUS=$(echo $STATUS_RESPONSE | jq -r '.status')

  if [ "$STATUS" = "completed" ]; then
    echo "✅ Video generation completed!"
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "❌ Task failed!"
    echo $STATUS_RESPONSE | jq .
    exit 1
  fi

  echo "   Status: $STATUS (waiting 5 seconds...)"
  sleep 5
done

# 5. Download video
echo "📥 Downloading video..."
curl -s -o generated_video.mp4 ${BASE_URL}/api/v1/video/${TASK_ID}
echo "✅ Video saved as generated_video.mp4"
echo "🎉 Done!"
```

## Test with Public Sample Files

You can test with publicly available sample files:

```bash
curl -X POST ${BASE_URL}/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "https://raw.githubusercontent.com/username/repo/main/sample_image.jpg",
    "audio": "https://raw.githubusercontent.com/username/repo/main/sample_audio.mp3",
    "bbox_shift": 0,
    "fps": 25,
    "batch_size": 4
  }' | jq .
```

## API Parameters

### Generate Video Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `image` | string | Image file path (after upload) or URL | Required |
| `audio` | string | Audio file path (after upload) or URL | Required |
| `bbox_shift` | int | Bounding box shift | 0 |
| `fps` | int | Frames per second (15-30) | 25 |
| `batch_size` | int | Processing batch size (2-8) | 4 |

### Supported File Formats

- **Images**: JPG, JPEG, PNG
- **Audio**: MP3, WAV

## Notes

- **Service URL**: Always get the correct BASE_URL from your service administrator
- **Task IDs**: Save the task_id from the generation response to check status and download the video
- **Batch Size**: Adjust batch_size (2-8) based on video length and available GPU memory
- **Processing Time**: Video generation typically takes 2-10 minutes depending on audio length
- **File Size Limits**: Maximum file size is 500MB by default
- **Timeouts**: Generation timeout is 10 minutes by default

## Troubleshooting

### Common Issues

1. **"Image file not found" error**: You're trying to use a local file path. Upload the file first using the `/api/v1/upload` endpoint.

2. **Connection refused**: Check that you have the correct BASE_URL from your service administrator.

3. **Task taking too long**: Video generation can take several minutes. Keep polling the status endpoint.

4. **Upload fails**: Ensure your file is in a supported format and under the size limit (500MB).

## Contact

For deployment-specific issues or to get your BASE_URL, contact your service administrator.