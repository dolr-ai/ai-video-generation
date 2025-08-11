#!/bin/bash
set -e

echo "MuseTalk FastAPI Server - API Testing Script"
echo "============================================"

# Get app URL
if [ -z "$1" ]; then
    # Try to get from Fly.io
    if command -v flyctl &> /dev/null; then
        APP_URL=$(flyctl info --app musetalk-api -j 2>/dev/null | jq -r '.Hostname' || echo "")
        if [ ! -z "$APP_URL" ]; then
            API_URL="https://$APP_URL"
        else
            API_URL="http://localhost:8000"
        fi
    else
        API_URL="http://localhost:8000"
    fi
else
    API_URL=$1
fi

echo "Testing API at: $API_URL"
echo ""

# Test health endpoint
echo "1. Testing health endpoint..."
curl -s "$API_URL/api/v1/health" | jq . || echo "Health check failed"
echo ""

# Test video generation with sample files
echo "2. Testing video generation..."
echo "   Using sample files from multimedia directory"

# Check if sample files exist locally
IMAGE_FILE="/workspace/ai-video-generation/multimedia/image/test_image1-female.png"
AUDIO_FILE="/workspace/ai-video-generation/multimedia/audio/test_audio1-female.mp3"

if [ -f "$IMAGE_FILE" ] && [ -f "$AUDIO_FILE" ]; then
    echo "   Found local test files, starting generation..."
    
    RESPONSE=$(curl -s -X POST "$API_URL/api/v1/generate" \
        -H "Content-Type: application/json" \
        -d "{
            \"image\": \"$IMAGE_FILE\",
            \"audio\": \"$AUDIO_FILE\",
            \"bbox_shift\": 0,
            \"fps\": 25,
            \"batch_size\": 4
        }")
    
    echo "$RESPONSE" | jq .
    
    # Extract task_id
    TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
    
    if [ "$TASK_ID" != "null" ] && [ ! -z "$TASK_ID" ]; then
        echo ""
        echo "3. Checking task status..."
        echo "   Task ID: $TASK_ID"
        
        # Poll status every 10 seconds
        for i in {1..30}; do
            sleep 10
            STATUS=$(curl -s "$API_URL/api/v1/status/$TASK_ID" | jq .)
            echo "$STATUS"
            
            # Check if completed or failed
            STATUS_VALUE=$(echo "$STATUS" | jq -r '.status')
            if [ "$STATUS_VALUE" == "completed" ]; then
                echo ""
                echo "4. Video generation completed!"
                echo "   Download URL: $API_URL/api/v1/video/$TASK_ID"
                break
            elif [ "$STATUS_VALUE" == "failed" ]; then
                echo ""
                echo "Video generation failed!"
                echo "$STATUS" | jq -r '.error_message'
                break
            fi
        done
    fi
else
    echo "   Warning: Test files not found locally"
    echo "   You can test with your own files by uploading them first"
fi

echo ""
echo "============================================"
echo "API testing complete!"