# MuseTalk FastAPI Server for Fly.io GPU Deployment
# Based on existing docker/Dockerfile with Fly.io optimizations

FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3.10-venv \
    python3-pip \
    git \
    wget \
    curl \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Install uv package manager
RUN pip install uv==0.7.16

# Create application directory
WORKDIR /workspace/ai-video-generation

# Copy only necessary files first for better caching
COPY requirements.txt /workspace/ai-video-generation/MuseTalk/
COPY fastapi_server/requirements.txt /workspace/ai-video-generation/MuseTalk/fastapi_server/

# Create virtual environment
WORKDIR /workspace/ai-video-generation/MuseTalk
RUN uv venv ../.venv --python 3.10

# Activate virtual environment
ENV VIRTUAL_ENV=/workspace/ai-video-generation/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install PyTorch with CUDA 11.8
RUN uv pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118

# Install base requirements
RUN uv pip install -r requirements.txt

# Install MMLab packages
RUN uv pip install --no-cache-dir openmim
RUN mim install mmengine
RUN mim install "mmcv==2.0.1"
RUN mim install "mmdet==3.1.0"
RUN mim install "mmpose==1.1.0"

# Fix NumPy version
RUN uv pip install "numpy==1.23.5" --force-reinstall

# Install FastAPI dependencies
WORKDIR /workspace/ai-video-generation/MuseTalk/fastapi_server
RUN uv pip install -r requirements.txt

# Now copy the entire MuseTalk application
COPY . /workspace/ai-video-generation/MuseTalk/

# Create necessary directories
RUN mkdir -p /workspace/ai-video-generation/MuseTalk/persistent/models \
    /workspace/ai-video-generation/MuseTalk/persistent/storage/temp \
    /workspace/ai-video-generation/MuseTalk/persistent/storage/videos \
    /workspace/ai-video-generation/MuseTalk/persistent/storage/uploads

# Create symlinks to persistent volume
RUN ln -sf /workspace/ai-video-generation/MuseTalk/persistent/models /workspace/ai-video-generation/MuseTalk/models && \
    ln -sf /workspace/ai-video-generation/MuseTalk/persistent/storage /workspace/ai-video-generation/MuseTalk/fastapi_server/storage

# Install tools for model downloading (including hf CLI)
RUN uv pip install --upgrade huggingface_hub[cli] gdown

# Download model weights script
COPY fly/download_models.sh /download_models.sh
RUN chmod +x /download_models.sh

# Copy startup script
COPY fly/start-servers.sh /start-servers.sh
RUN chmod +x /start-servers.sh

# Create volume mount point for persistent data
VOLUME ["/workspace/ai-video-generation/MuseTalk/persistent"]

# Make FastAPI scripts executable
WORKDIR /workspace/ai-video-generation/MuseTalk/fastapi_server
RUN chmod +x start_model_server.sh start_handler_server.sh || true

# Expose only handler server port (model server runs internally on localhost:8001)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Set working directory
WORKDIR /workspace/ai-video-generation/MuseTalk

# Start both servers with bash script
CMD ["/start-servers.sh"]