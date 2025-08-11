#!/bin/bash
set -e

echo "🚀 Starting MuseTalk FastAPI Servers on Fly.io..."

# Ensure models directory exists
mkdir -p /workspace/ai-video-generation/MuseTalk/models

# Check if models need to be downloaded
# This is crucial for persistent volumes on Fly.io
MODELS_DIR="/workspace/ai-video-generation/MuseTalk/models"
MODEL_MARKER="$MODELS_DIR/.models_downloaded"

echo "Checking for model files in volume..."
if [ ! -f "$MODEL_MARKER" ]; then
    echo "📥 Models not found in volume. Starting download..."
    echo "This will only happen once - models will persist in volume."
    
    if [ -f "/download_models.sh" ]; then
        /download_models.sh
        if [ $? -eq 0 ]; then
            echo "✅ Models downloaded successfully!"
            touch "$MODEL_MARKER"
        else
            echo "❌ Model download failed!"
            exit 1
        fi
    else
        echo "❌ Error: Model download script not found!"
        exit 1
    fi
else
    echo "✅ Models already present in volume."
    # Verify key model files exist
    if [ ! -f "$MODELS_DIR/musetalkV15/unet.pth" ]; then
        echo "⚠️  Warning: Some model files may be missing. Removing marker and re-downloading..."
        rm "$MODEL_MARKER"
        exec "$0" "$@"  # Restart the script
    fi
fi

# Ensure storage directories exist
mkdir -p /workspace/ai-video-generation/MuseTalk/fastapi_server/storage/temp
mkdir -p /workspace/ai-video-generation/MuseTalk/fastapi_server/storage/videos
mkdir -p /workspace/ai-video-generation/MuseTalk/fastapi_server/storage/uploads

# Verify CUDA is available
python -c "import torch; print('CUDA Available:', torch.cuda.is_available())"

# Function to start model server
start_model_server() {
    echo "Starting Model Server on localhost:8001..."
    cd /workspace/ai-video-generation/MuseTalk
    python fastapi_server/model_server.py &
    MODEL_SERVER_PID=$!
    echo "Model server PID: $MODEL_SERVER_PID"
    
    # Wait for model server to be ready
    echo "Waiting for model server to load models..."
    for i in {1..60}; do
        if curl -s -f http://localhost:8001/health >/dev/null 2>&1; then
            echo "✅ Model server is ready!"
            return 0
        fi
        if [ $i -eq 60 ]; then
            echo "❌ Model server failed to start"
            exit 1
        fi
        sleep 5
        echo "Still waiting... ($i/60)"
    done
}

# Function to start handler server
start_handler_server() {
    echo "Starting Handler Server on 0.0.0.0:8000..."
    cd /workspace/ai-video-generation/MuseTalk/fastapi_server
    python handler_server.py &
    HANDLER_SERVER_PID=$!
    echo "Handler server PID: $HANDLER_SERVER_PID"
    
    # Wait for handler server to be ready
    echo "Waiting for handler server..."
    for i in {1..30}; do
        if curl -s -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
            echo "✅ Handler server is ready!"
            return 0
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Handler server failed to start"
            exit 1
        fi
        sleep 5
    done
}

# Graceful shutdown handler
cleanup() {
    echo "Shutting down servers..."
    kill $MODEL_SERVER_PID $HANDLER_SERVER_PID 2>/dev/null || true
    wait $MODEL_SERVER_PID $HANDLER_SERVER_PID 2>/dev/null || true
    echo "Servers shut down"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Start both servers
start_model_server
start_handler_server

# Health check
echo "🏥 Final health check..."
curl -s http://localhost:8000/api/v1/health | jq . || true

echo "🎉 MuseTalk FastAPI Server is running!"
echo "API available at port 8000"

# Keep running and wait for signals
wait $MODEL_SERVER_PID $HANDLER_SERVER_PID