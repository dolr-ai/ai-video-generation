#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Ensure huggingface_hub CLI is installed
if ! command -v hf &> /dev/null; then
    echo "hf command not found. Installing huggingface_hub..."
    uv pip install --upgrade huggingface_hub
    if ! command -v hf &> /dev/null; then
        echo "hf command installation failed." >&2
        exit 1
    fi
fi

# Ensure gdown is installed
if ! command -v gdown &> /dev/null; then
    echo "gdown not found. Installing gdown..."
    uv pip install --upgrade gdown
    if ! command -v gdown &> /dev/null; then
        echo "gdown installation failed." >&2
        exit 1
    fi
fi


# Set the checkpoints directory
CheckpointsDir="models"

# Create necessary directories
mkdir -p models/musetalk models/musetalkV15 models/syncnet models/dwpose models/face-parse-bisent models/sd-vae models/whisper

# Set HuggingFace mirror endpoint (optional, remove if not needed)
# export HF_ENDPOINT=https://hf-mirror.com

# Download MuseTalk V1.0 weights
hf download TMElyralab/MuseTalk \
  --local-dir $CheckpointsDir \
  --include "musetalk/musetalk.json" "musetalk/pytorch_model.bin"

# Download MuseTalk V1.5 weights (unet.pth)
hf download TMElyralab/MuseTalk \
  --local-dir $CheckpointsDir \
  --include "musetalkV15/musetalk.json" "musetalkV15/unet.pth"

# Download SD VAE weights
hf download stabilityai/sd-vae-ft-mse \
  --local-dir $CheckpointsDir/sd-vae \
  --include "config.json" "diffusion_pytorch_model.bin"

# Download Whisper weights
hf download openai/whisper-tiny \
  --local-dir $CheckpointsDir/whisper \
  --include "config.json" "pytorch_model.bin" "preprocessor_config.json"

# Download DWPose weights
hf download yzd-v/DWPose \
  --local-dir $CheckpointsDir/dwpose \
  --include "dw-ll_ucoco_384.pth"

# Download SyncNet weights
hf download ByteDance/LatentSync \
  --local-dir $CheckpointsDir/syncnet \
  --include "latentsync_syncnet.pt"

# Download Face Parse Bisent weights
gdown --id 154JgKpzCPW82qINcVieuPH3fZ2e0P812 -O $CheckpointsDir/face-parse-bisent/79999_iter.pth
# The resnet18 file was already downloaded, but let's check
if [ ! -f "$CheckpointsDir/face-parse-bisent/resnet18-5c106cde.pth" ]; then
    curl -L https://download.pytorch.org/models/resnet18-5c106cde.pth \
      -o $CheckpointsDir/face-parse-bisent/resnet18-5c106cde.pth
fi

echo "✅ All weights have been downloaded successfully!"