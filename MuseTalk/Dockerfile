# MuseTalk Docker Setup - Bare Minimum
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    git \
    wget \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Install uv for faster package management
RUN pip install uv

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install PyTorch 2.0.1 with CUDA 11.8
RUN uv pip install --system torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118

# Install requirements
RUN uv pip install --system -r requirements.txt

# Install MMLab packages with mim (critical for CUDA extensions)
RUN uv pip install --system --no-cache-dir -U openmim
RUN python -m mim install mmengine
RUN python -m mim install "mmcv==2.0.1"
RUN python -m mim install "mmdet==3.1.0"
RUN python -m mim install "mmpose==1.1.0"

# Fix compatibility issues
RUN uv pip install --system "numpy<2" "safetensors<0.4.0" "transformers<4.30.0"

# Copy application code
COPY . .

# Install additional tools needed for weight downloading
RUN uv pip install --system huggingface_hub gdown

# Create models directory structure
RUN mkdir -p models/musetalk models/musetalkV15 models/syncnet models/dwpose models/face-parse-bisent models/sd-vae models/whisper

# Download model weights (optional - can mount as volume instead)
# Uncomment the following line to download weights during build:
# RUN bash download_weights_with_venv.sh

# Alternative: Copy a simplified download script for Docker
COPY download_weights_docker.sh .
RUN chmod +x download_weights_docker.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0

# Default command
CMD ["python", "-m", "scripts.inference", \
     "--inference_config", "./configs/inference/test.yaml", \
     "--result_dir", "./results/test", \
     "--unet_model_path", "./models/musetalkV15/unet.pth", \
     "--unet_config", "./models/musetalkV15/musetalk.json", \
     "--version", "v15", \
     "--ffmpeg_path", "/usr/bin"]