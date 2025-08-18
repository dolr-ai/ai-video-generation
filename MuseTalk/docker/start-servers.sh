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

# Check if models exist - warn but don't fail (models might be downloaded later)
echo "📂 Checking model files:"
MODELS_DIR="${MODELS_PATH:-/workspace/ai-video-generation/MuseTalk/models}"

if [ ! -d "$MODELS_DIR" ]; then
    echo "⚠️  WARNING: Models directory not found at $MODELS_DIR"
    echo "   Creating directory structure..."
    mkdir -p "$MODELS_DIR"/{musetalk,musetalkV15,syncnet,dwpose,face-parse-bisent,sd-vae,whisper}
fi

# Function to download models from GCS
download_models_from_gcs() {
    local bucket_name="${GCS_BUCKET:-talking-head-models}"
    
    echo "📥 Downloading models from GCS bucket: gs://$bucket_name/models/"
    
    # Authenticate with GCS using service account
    if [ ! -z "$GCP_CREDENTIALS" ]; then
        echo "🔐 Authenticating with GCP using service account..."
        echo "$GCP_CREDENTIALS" > /tmp/gcp-key.json
        gcloud auth activate-service-account --key-file=/tmp/gcp-key.json
        rm /tmp/gcp-key.json
    else
        echo "⚠️  GCP_CREDENTIALS not set, assuming workload identity or default credentials"
    fi
    
    # Download all models with parallel transfers for speed
    echo "📦 Downloading model files..."
    gsutil -m -o "GSUtil:parallel_thread_count=10" \
           -o "GSUtil:parallel_process_count=4" \
           cp -r "gs://$bucket_name/models/*" "$MODELS_DIR/" || {
        echo "❌ Failed to download models from GCS"
        return 1
    }
    
    echo "✅ Models downloaded successfully from GCS"
    return 0
}

# Check if models are in volume or need to be downloaded
MODEL_MARKER="$MODELS_DIR/.models_downloaded"

echo "📂 Checking for models in RunPod volume 'talking-head-models'..."
if [ ! -f "$MODEL_MARKER" ] || [ ! -f "$MODELS_DIR/musetalkV15/unet.pth" ]; then
    echo "📥 Models not found in volume. Starting download..."
    echo "This will only happen once - models will persist in volume."
    
    # Try to download from GCS
    if command -v gsutil &> /dev/null; then
        download_models_from_gcs || {
            echo "❌ Failed to download models from GCS"
            echo "   Please ensure:"
            echo "   1. GCP_CREDENTIALS environment variable is set with service account JSON"
            echo "   2. GCS_BUCKET is set (default: talking-head-models)"
            echo "   3. Service account has access to the bucket"
            exit 1
        }
        
        # Mark models as downloaded
        echo "✅ Models downloaded successfully to volume!"
        touch "$MODEL_MARKER"
        echo "$(date): Models downloaded from GCS" >> "$MODEL_MARKER"
    else
        echo "❌ gsutil not available for GCS download"
        exit 1
    fi
else
    echo "✅ Models already present in RunPod volume."
    echo "📅 Volume marker: $(cat $MODEL_MARKER 2>/dev/null || echo 'No timestamp')"
fi

# Verify required model files exist
REQUIRED_FILES=(
    "musetalk/musetalk.json"
    "musetalk/pytorch_model.bin"
    "musetalkV15/musetalk.json"
    "musetalkV15/unet.pth"
    "syncnet/latentsync_syncnet.pt"
    "dwpose/dw-ll_ucoco_384.pth"
    "face-parse-bisent/79999_iter.pth"
    "face-parse-bisent/resnet18-5c106cde.pth"
    "sd-vae/config.json"
    "sd-vae/diffusion_pytorch_model.bin"
    "whisper/config.json"
    "whisper/pytorch_model.bin"
    "whisper/preprocessor_config.json"
)

MISSING_FILES=()
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$MODELS_DIR/$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo "❌ ERROR: Required model files missing:"
    for file in "${MISSING_FILES[@]}"; do
        echo "   - $file"
    done
    exit 1
fi

echo "✅ All required model files found"
ls -lh "$MODELS_DIR/" | head -20

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