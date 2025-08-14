# MuseTalk FastAPI Server Dockerfile with Volume Support
# Following exact setup steps from docs/venv_setup.md and docs/fastapi_setup.md
#
# VOLUME USAGE:
# This image expects models to be mounted as volumes:
#   docker run -v /path/to/models:/workspace/ai-video-generation/MuseTalk/models \
#              -v /path/to/storage:/workspace/ai-video-generation/MuseTalk/fastapi_server/storage \
#              musetalk-api
#
# Models should be pre-downloaded and placed in the volume before running

FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# Set environment variables early
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0
ENV PYTHONDONTWRITEBYTECODE=1
# Support external model volumes
ENV MODELS_PATH=/workspace/ai-video-generation/MuseTalk/models

# Install system dependencies (matching docs/venv_setup.md requirements)
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

# Set Python 3.10 as default (matching exact version from docs)
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Install uv package manager (version 0.7.16 as per docs)
RUN pip install uv==0.7.16

# Create application directory
WORKDIR /workspace/ai-video-generation

# Copy MuseTalk source code first (context is ./MuseTalk so copy to MuseTalk subdirectory)
COPY . /workspace/ai-video-generation/MuseTalk/

# Create virtual environment in the exact location as docs (.venv in parent directory)
# Following Step 2 from docs/venv_setup.md: "uv venv ../.venv --python 3.10"
WORKDIR /workspace/ai-video-generation/MuseTalk
RUN uv venv ../.venv --python 3.10

# Activate virtual environment for subsequent commands
ENV VIRTUAL_ENV=/workspace/ai-video-generation/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Step 4: Install PyTorch with CUDA 11.8 Support (exact command from docs)
RUN uv pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118

# Step 5: Install Requirements from requirements.txt (exact command from docs)
# Debug: List files to see what's available
RUN pwd && ls -la && echo "Looking for requirements.txt:" && find . -name "requirements.txt" -type f
RUN uv pip install -r requirements.txt

# Step 6: Install MMLab Packages (exact commands from docs)
# Note: Installing openmim WITHOUT -U flag to avoid numpy upgrade issue (learned from errors doc)
RUN uv pip install --no-cache-dir openmim

# Install MMLab components using mim (exact versions from docs)
RUN mim install mmengine
RUN mim install "mmcv==2.0.1"
RUN mim install "mmdet==3.1.0"
RUN mim install "mmpose==1.1.0"

# Step 8: Fix NumPy Version Compatibility (CRITICAL FIX from docs)
# Force downgrade numpy to compatible version to avoid the critical error
RUN uv pip install "numpy==1.23.5" --force-reinstall

# Install FastAPI dependencies (from docs/fastapi_setup.md)
WORKDIR /workspace/ai-video-generation/MuseTalk/fastapi_server
RUN uv pip install -r requirements.txt

# Verify all installations work (matching verification from docs)
RUN python -c "import torch; import torchvision; import mmcv; import mmdet; import mmpose; print('PyTorch version:', torch.__version__); print('CUDA available:', torch.cuda.is_available())"

# Create necessary directories for FastAPI server
RUN mkdir -p /workspace/ai-video-generation/MuseTalk/fastapi_server/storage/temp
RUN mkdir -p /workspace/ai-video-generation/MuseTalk/fastapi_server/storage/videos
RUN mkdir -p /workspace/ai-video-generation/MuseTalk/fastapi_server/storage/uploads

# Create models directory structure
WORKDIR /workspace/ai-video-generation/MuseTalk
RUN mkdir -p models/musetalk models/musetalkV15 models/syncnet models/dwpose models/face-parse-bisent models/sd-vae models/whisper

# Models will be downloaded from GCS at runtime, not during build
# This reduces image size and allows dynamic model updates
# COPY models* /workspace/ai-video-generation/MuseTalk/models/

# Make startup scripts executable (from docs/fastapi_setup.md Step 10)
WORKDIR /workspace/ai-video-generation/MuseTalk/fastapi_server
RUN chmod +x start_model_server.sh start_handler_server.sh

# Install additional tools for model weight downloading (Step 10 preparation)
RUN uv pip install huggingface_hub gdown

# Install Google Cloud SDK for GCS model downloading
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    gnupg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - \
    && apt-get update && apt-get install -y google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

# Declare volumes for models and storage
# Models volume: Mount your pre-downloaded models here
VOLUME ["/workspace/ai-video-generation/MuseTalk/models"]
# Storage volume: For generated videos and temporary files
VOLUME ["/workspace/ai-video-generation/MuseTalk/fastapi_server/storage"]

# Expose FastAPI server ports (from docs - Model server: 8001, Handler server: 8000)
EXPOSE 8000 8001

# Set working directory to MuseTalk root (critical for model loading as per docs)
WORKDIR /workspace/ai-video-generation/MuseTalk

# Health check to verify both servers can start
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default command: Start both servers
# Using a startup script to handle proper sequencing
COPY docker/start-servers.sh /start-servers.sh
RUN chmod +x /start-servers.sh

CMD ["/start-servers.sh"]