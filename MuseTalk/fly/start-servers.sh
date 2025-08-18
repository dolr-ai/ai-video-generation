#!/bin/bash
set -e

echo "Starting MuseTalk FastAPI Servers on Fly.io..."
echo "Current directory: $(pwd)"
echo "Script path: $0"
echo "Environment:"
env | grep -E "(PORT|HOST|PYTHONPATH|NVIDIA)" || true

# Check GPU availability
echo "==========================================="
echo "GPU STATUS CHECK"
echo "==========================================="
nvidia-smi || echo "WARNING: nvidia-smi not available, GPU may not be accessible"
python -c "import torch; print(f'PyTorch CUDA available: {torch.cuda.is_available()}'); print(f'CUDA device count: {torch.cuda.device_count() if torch.cuda.is_available() else 0}')" || true

# Use persistent volume for models (mounted at /workspace/ai-video-generation/MuseTalk/models)
# This is the mount point defined in fly.toml
MODELS_DIR="/workspace/ai-video-generation/MuseTalk/models"
mkdir -p "$MODELS_DIR"

# Check if models need to be downloaded
# This is crucial for persistent volumes on Fly.io
MODEL_MARKER="$MODELS_DIR/.models_downloaded"

echo "=========================================="
echo "VOLUME STATUS CHECK"
echo "=========================================="
echo "Checking persistent volume at: $MODELS_DIR"
ls -la "$MODELS_DIR" 2>/dev/null || echo "Volume directory not accessible yet"
echo "------------------------------------------"

if [ ! -f "$MODEL_MARKER" ]; then
    echo "WARNING: Models not found in volume!"
    echo "Models should have been pre-loaded from GCS during deployment."
    echo "=========================================="
    
    # Show what's in the models directory
    echo "Current models directory contents:"
    ls -la "$MODELS_DIR" 2>/dev/null || echo "Models directory does not exist"
    
    # Try to download models as fallback
    if [ -f "/download_models.sh" ]; then
        echo "Attempting fallback model download..."
        /download_models.sh
        if [ $? -eq 0 ]; then
            echo "Models downloaded successfully!"
        else
            echo "Model download failed. Cannot start servers without models."
            exit 1
        fi
    else
        echo "No download script available. Cannot start servers without models."
        exit 1
    fi
else
    echo "MODELS ALREADY PRESENT IN VOLUME"
    echo "Using pre-loaded models from GCS"
    # Verify all critical model files exist
    MISSING_FILES=()
    [ ! -f "$MODELS_DIR/musetalk/pytorch_model.bin" ] && MISSING_FILES+=("musetalk/pytorch_model.bin")
    [ ! -f "$MODELS_DIR/musetalkV15/unet.pth" ] && MISSING_FILES+=("musetalkV15/unet.pth")
    [ ! -f "$MODELS_DIR/sd-vae/diffusion_pytorch_model.bin" ] && MISSING_FILES+=("sd-vae/diffusion_pytorch_model.bin")
    [ ! -f "$MODELS_DIR/whisper/pytorch_model.bin" ] && MISSING_FILES+=("whisper/pytorch_model.bin")
    [ ! -f "$MODELS_DIR/dwpose/dw-ll_ucoco_384.pth" ] && MISSING_FILES+=("dwpose/dw-ll_ucoco_384.pth")
    [ ! -f "$MODELS_DIR/syncnet/latentsync_syncnet.pt" ] && MISSING_FILES+=("syncnet/latentsync_syncnet.pt")
    [ ! -f "$MODELS_DIR/face-parse-bisent/79999_iter.pth" ] && MISSING_FILES+=("face-parse-bisent/79999_iter.pth")
    
    if [ ${#MISSING_FILES[@]} -gt 0 ]; then
        echo "Warning: Some model files are missing:"
        for file in "${MISSING_FILES[@]}"; do
            echo "  - $file"
        done
        echo "Removing marker and re-downloading..."
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
echo "Final health check..."
curl -s http://localhost:8000/api/v1/health | jq . || true

echo "MuseTalk FastAPI Server is running!"
echo "API available at port 8000"

# Keep running and wait for signals
wait $MODEL_SERVER_PID $HANDLER_SERVER_PID