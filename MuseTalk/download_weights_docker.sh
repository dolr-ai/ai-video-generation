#!/bin/bash

# Docker-compatible weights download script
# No virtual environment needed - packages installed system-wide

set -e

# Check if hf command is available
if ! command -v hf &> /dev/null; then
    echo "Error: hf command not found. Please ensure huggingface_hub is installed." >&2
    exit 1
fi

# Check if gdown is available
if ! command -v gdown &> /dev/null; then
    echo "Error: gdown command not found. Please ensure gdown is installed." >&2
    exit 1
fi

echo "📥 Downloading MuseTalk model weights..."

# Set the checkpoints directory
CheckpointsDir="models"

# Create necessary directories (should already exist from Dockerfile)
mkdir -p models/musetalk models/musetalkV15 models/syncnet models/dwpose models/face-parse-bisent models/sd-vae models/whisper

# Download MuseTalk V1.0 weights
echo "⬇️ Downloading MuseTalk V1.0..."
hf download TMElyralab/MuseTalk \
  --local-dir $CheckpointsDir \
  --include "musetalk/musetalk.json" "musetalk/pytorch_model.bin"

# Download MuseTalk V1.5 weights (unet.pth)
echo "⬇️ Downloading MuseTalk V1.5..."
hf download TMElyralab/MuseTalk \
  --local-dir $CheckpointsDir \
  --include "musetalkV15/musetalk.json" "musetalkV15/unet.pth"

# Download SD VAE weights
echo "⬇️ Downloading SD VAE..."
hf download stabilityai/sd-vae-ft-mse \
  --local-dir $CheckpointsDir/sd-vae \
  --include "config.json" "diffusion_pytorch_model.bin"

# Download Whisper weights
echo "⬇️ Downloading Whisper..."
hf download openai/whisper-tiny \
  --local-dir $CheckpointsDir/whisper \
  --include "config.json" "pytorch_model.bin" "preprocessor_config.json"

# Download DWPose weights
echo "⬇️ Downloading DWPose..."
hf download yzd-v/DWPose \
  --local-dir $CheckpointsDir/dwpose \
  --include "dw-ll_ucoco_384.pth"

# Download SyncNet weights
echo "⬇️ Downloading SyncNet..."
hf download ByteDance/LatentSync \
  --local-dir $CheckpointsDir/syncnet \
  --include "latentsync_syncnet.pt"

# Download Face Parse Bisent weights
echo "⬇️ Downloading Face Parse Bisent..."
gdown --id 154JgKpzCPW82qINcVieuPH3fZ2e0P812 -O $CheckpointsDir/face-parse-bisent/79999_iter.pth

# Download ResNet18 weights if not present
if [ ! -f "$CheckpointsDir/face-parse-bisent/resnet18-5c106cde.pth" ]; then
    echo "⬇️ Downloading ResNet18..."
    curl -L https://download.pytorch.org/models/resnet18-5c106cde.pth \
      -o $CheckpointsDir/face-parse-bisent/resnet18-5c106cde.pth
fi

echo "✅ All weights have been downloaded successfully!"
echo "📁 Weights are stored in: $CheckpointsDir/"
echo "🚀 Ready to run MuseTalk inference!"