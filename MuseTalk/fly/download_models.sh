#!/bin/bash
set -e

echo "=========================================="
echo "MuseTalk Model Downloader for Fly.io"
echo "=========================================="

cd /workspace/ai-video-generation/MuseTalk

# Ensure huggingface_hub CLI is installed
if ! command -v hf &> /dev/null; then
    echo "Installing huggingface_hub CLI..."
    pip install --upgrade huggingface_hub
fi

# Ensure gdown is installed
if ! command -v gdown &> /dev/null; then
    echo "Installing gdown..."
    pip install --upgrade gdown
fi

# Set the checkpoints directory to the persistent volume mount point
# This matches the mount point in fly.toml
CheckpointsDir="/workspace/ai-video-generation/MuseTalk/models"

# Create necessary directories in the persistent volume
mkdir -p $CheckpointsDir/musetalk $CheckpointsDir/musetalkV15 $CheckpointsDir/syncnet $CheckpointsDir/dwpose $CheckpointsDir/face-parse-bisent $CheckpointsDir/sd-vae $CheckpointsDir/whisper

echo ""
echo "📦 Downloading MuseTalk V1.0 weights..."
# Download MuseTalk V1.0 weights
hf download TMElyralab/MuseTalk \
  --local-dir $CheckpointsDir \
  --include "musetalk/musetalk.json" "musetalk/pytorch_model.bin"

echo ""
echo "📦 Downloading MuseTalk V1.5 weights (unet.pth)..."
# Download MuseTalk V1.5 weights (unet.pth)
hf download TMElyralab/MuseTalk \
  --local-dir $CheckpointsDir \
  --include "musetalkV15/musetalk.json" "musetalkV15/unet.pth"

echo ""
echo "📦 Downloading SD VAE weights..."
# Download SD VAE weights
hf download stabilityai/sd-vae-ft-mse \
  --local-dir $CheckpointsDir/sd-vae \
  --include "config.json" "diffusion_pytorch_model.bin"

echo ""
echo "📦 Downloading Whisper weights..."
# Download Whisper weights
hf download openai/whisper-tiny \
  --local-dir $CheckpointsDir/whisper \
  --include "config.json" "pytorch_model.bin" "preprocessor_config.json"

echo ""
echo "📦 Downloading DWPose weights..."
# Download DWPose weights
hf download yzd-v/DWPose \
  --local-dir $CheckpointsDir/dwpose \
  --include "dw-ll_ucoco_384.pth"

echo ""
echo "📦 Downloading SyncNet weights..."
# Download SyncNet weights
hf download ByteDance/LatentSync \
  --local-dir $CheckpointsDir/syncnet \
  --include "latentsync_syncnet.pt"

echo ""
echo "📦 Downloading Face Parse Bisent weights..."
# Download Face Parse Bisent weights
gdown --id 154JgKpzCPW82qINcVieuPH3fZ2e0P812 -O $CheckpointsDir/face-parse-bisent/79999_iter.pth

# Download resnet18 if not already present
if [ ! -f "$CheckpointsDir/face-parse-bisent/resnet18-5c106cde.pth" ]; then
    echo "📦 Downloading ResNet18 weights..."
    curl -L https://download.pytorch.org/models/resnet18-5c106cde.pth \
      -o $CheckpointsDir/face-parse-bisent/resnet18-5c106cde.pth
fi

# Verify critical files exist
echo ""
echo "🔍 Verifying downloaded models..."
CRITICAL_FILES=(
    "$CheckpointsDir/musetalk/musetalk.json"
    "$CheckpointsDir/musetalk/pytorch_model.bin"
    "$CheckpointsDir/musetalkV15/musetalk.json"
    "$CheckpointsDir/musetalkV15/unet.pth"
    "$CheckpointsDir/sd-vae/diffusion_pytorch_model.bin"
    "$CheckpointsDir/whisper/pytorch_model.bin"
    "$CheckpointsDir/dwpose/dw-ll_ucoco_384.pth"
    "$CheckpointsDir/syncnet/latentsync_syncnet.pt"
    "$CheckpointsDir/face-parse-bisent/79999_iter.pth"
)

ALL_GOOD=true
for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ Missing: $file"
        ALL_GOOD=false
    fi
done

if [ "$ALL_GOOD" = true ]; then
    # Create marker file to indicate successful download
    touch $CheckpointsDir/.models_downloaded
    echo ""
    echo "=========================================="
    echo "✅ All weights have been downloaded successfully!"
    echo "=========================================="
    exit 0
else
    echo ""
    echo "=========================================="
    echo "❌ Some models failed to download!"
    echo "=========================================="
    exit 1
fi