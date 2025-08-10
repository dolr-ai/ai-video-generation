#!/bin/bash

# MuseTalk FastAPI Server Startup Script for Docker
# Follows exact pattern from docs/fastapi_setup.md

set -e  # Exit on any error

echo "🚀 Starting MuseTalk FastAPI Server in Docker..."
echo "=================================================="

# Environment validation
echo "📋 Environment Validation:"
echo "  Python version: $(python --version)"
echo "  Working directory: $(pwd)"
echo "  CUDA available: $(python -c 'import torch; print(torch.cuda.is_available())')"
echo "  Virtual environment: $VIRTUAL_ENV"

# Check if models exist
echo "📂 Checking model files:"
if [ ! -d "/workspace/ai-video-generation/MuseTalk/models/musetalkV15" ]; then
    echo "❌ ERROR: Model weights not found!"
    echo "   Please mount model weights to /workspace/ai-video-generation/MuseTalk/models"
    echo "   Example: -v /path/to/your/models:/workspace/ai-video-generation/MuseTalk/models"
    exit 1
fi

# Verify required model files exist
REQUIRED_FILES=(
    "models/musetalkV15/unet.pth"
    "models/musetalkV15/musetalk.json"
    "models/sd-vae/diffusion_pytorch_model.bin"
    "models/whisper/pytorch_model.bin"
    "models/dwpose/dw-ll_ucoco_384.pth"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "/workspace/ai-video-generation/MuseTalk/$file" ]; then
        echo "❌ ERROR: Required model file missing: $file"
        exit 1
    fi
done

echo "✅ All required model files found"

# Create log directory
mkdir -p /workspace/ai-video-generation/MuseTalk/fastapi_server/logs

# Function to start model server (follows docs pattern - runs from MuseTalk directory)
start_model_server() {
    echo "🔧 Starting Model Server (Port 8001)..."
    cd /workspace/ai-video-generation/MuseTalk
    
    # Set PYTHONPATH (matching startup script from docs)
    export PYTHONPATH="/workspace/ai-video-generation/MuseTalk/fastapi_server:$PYTHONPATH"
    
    # Start model server (matching pattern from docs)
    python fastapi_server/model_server.py &
    MODEL_SERVER_PID=$!
    echo "   Model server started with PID: $MODEL_SERVER_PID"
    
    # Wait for model server to be ready
    echo "⏳ Waiting for model server to load models..."
    for i in {1..60}; do  # Wait up to 5 minutes for model loading
        if curl -s -f http://localhost:8001/health >/dev/null 2>&1; then
            echo "✅ Model server is ready!"
            break
        fi
        if [ $i -eq 60 ]; then
            echo "❌ Model server failed to start within 5 minutes"
            kill $MODEL_SERVER_PID 2>/dev/null || true
            exit 1
        fi
        sleep 5
        echo "   Still waiting... ($i/60)"
    done
}

# Function to start handler server (follows docs pattern - runs from fastapi_server directory)
start_handler_server() {
    echo "🌐 Starting Handler Server (Port 8000)..."
    cd /workspace/ai-video-generation/MuseTalk/fastapi_server
    
    # Set PYTHONPATH (matching startup script from docs)
    export PYTHONPATH="/workspace/ai-video-generation/MuseTalk/fastapi_server:$PYTHONPATH"
    
    # Start handler server (matching pattern from docs)
    python handler_server.py &
    HANDLER_SERVER_PID=$!
    echo "   Handler server started with PID: $HANDLER_SERVER_PID"
    
    # Wait for handler server to be ready
    echo "⏳ Waiting for handler server to be ready..."
    for i in {1..30}; do  # Wait up to 2.5 minutes
        if curl -s -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
            echo "✅ Handler server is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Handler server failed to start within 2.5 minutes"
            kill $HANDLER_SERVER_PID 2>/dev/null || true
            kill $MODEL_SERVER_PID 2>/dev/null || true
            exit 1
        fi
        sleep 5
        echo "   Still waiting... ($i/30)"
    done
}

# Function to handle graceful shutdown
cleanup() {
    echo "🛑 Shutting down servers..."
    kill $MODEL_SERVER_PID $HANDLER_SERVER_PID 2>/dev/null || true
    wait $MODEL_SERVER_PID $HANDLER_SERVER_PID 2>/dev/null || true
    echo "👋 Servers shut down gracefully"
    exit 0
}

# Set up signal handlers for graceful shutdown
trap cleanup SIGTERM SIGINT

# Start both servers following the exact pattern from docs
start_model_server
start_handler_server

# Final health check
echo "🏥 Final health check..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/api/v1/health)
echo "Health check response: $HEALTH_RESPONSE"

echo "🎉 MuseTalk FastAPI Server is fully operational!"
echo "=================================================="
echo "📡 API Endpoints available:"
echo "   • Health check: http://localhost:8000/api/v1/health"
echo "   • Generate video: http://localhost:8000/api/v1/generate"
echo "   • Check status: http://localhost:8000/api/v1/status/{task_id}"
echo "   • Download video: http://localhost:8000/api/v1/video/{task_id}"
echo "   • Model server: http://localhost:8001/health"
echo ""
echo "📝 Logs available at:"
echo "   • Model server: /workspace/ai-video-generation/MuseTalk/fastapi_server/model_server.log"
echo "   • Handler server: /workspace/ai-video-generation/MuseTalk/fastapi_server/handler_server.log"
echo "   • Endpoints: /workspace/ai-video-generation/MuseTalk/fastapi_server/endpoints.log"
echo "   • MuseTalk model: /workspace/ai-video-generation/MuseTalk/fastapi_server/musetalk_model.log"
echo ""
echo "💡 Example usage:"
echo '   curl -X POST http://localhost:8000/api/v1/generate \'
echo '     -H "Content-Type: application/json" \'
echo '     -d "{\"image\": \"/path/to/image.jpg\", \"audio\": \"/path/to/audio.mp3\"}"'
echo "=================================================="

# Keep the script running and wait for signals
wait $MODEL_SERVER_PID $HANDLER_SERVER_PID