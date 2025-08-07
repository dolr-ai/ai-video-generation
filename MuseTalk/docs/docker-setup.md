# MuseTalk Docker Setup Guide

## Overview

This guide provides multiple approaches for running MuseTalk in Docker containers, with special consideration for the model weights downloading process.

## Quick Start

### Option 1: Build with Weights Download (Recommended for Production)

```bash
# Build image with weights included (takes longer but self-contained)
./docker-build.sh --download-weights
```

### Option 2: Build without Weights (Mount as Volumes)

```bash
# Build lightweight image, mount weights from host
./docker-build.sh

# Or using docker-compose
docker-compose up
```

### Option 3: Build Only (No Inference)

```bash
# Just build the image
./docker-build.sh --build-only
```

## Weight Management Strategies

### Strategy 1: Weights Inside Container (Self-Contained)

**Pros:**
- Fully self-contained image
- No external dependencies at runtime
- Easy deployment and sharing

**Cons:**
- Large image size (~10-15GB)
- Longer build time
- Weights baked into image

**Usage:**
```bash
./docker-build.sh --download-weights
```

### Strategy 2: Weights as Volumes (Flexible)

**Pros:**
- Lightweight image (~3-5GB)
- Faster builds
- Can update weights independently
- Share weights between containers

**Cons:**
- Requires external weight management
- Additional setup step

**Usage:**
```bash
# First download weights locally
bash download_weights_with_venv.sh

# Then build and run with volume mounts
./docker-build.sh
```

### Strategy 3: Init Container Pattern

**Pros:**
- Best of both worlds
- Separate concerns
- Can use different base images

**Usage:**
```bash
# Use docker-compose with init container
docker-compose -f docker-compose.init.yml up
```

## Files Overview

### Docker Files

- `Dockerfile` - Main container definition
- `download_weights_docker.sh` - Docker-optimized weight download script  
- `docker-build.sh` - Enhanced build script with options
- `docker-compose.yml` - Multi-container setup with volume mounts
- `.dockerignore` - Excludes unnecessary files from build context

### Key Features

1. **CUDA 11.8 Support** - Uses `nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04`
2. **Python 3.10** - Exact version required by MuseTalk
3. **UV Package Manager** - Faster than pip for dependency installation
4. **MMLab Integration** - Uses mim for proper mmcv installation
5. **Version Pinning** - All critical versions locked for compatibility

## Manual Docker Commands

### Build Image

```bash
# Basic build
docker build -t musetalk:latest .

# Build with weights (modify Dockerfile temporarily)
sed 's/# RUN .\/download_weights_docker.sh/RUN .\/download_weights_docker.sh/' Dockerfile > Dockerfile.tmp
docker build -f Dockerfile.tmp -t musetalk:latest .
rm Dockerfile.tmp
```

### Run Container

```bash
# Run with GPU support and volume mounts
docker run --gpus all \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/results:/app/results \
  -v $(pwd)/configs:/app/configs \
  musetalk:latest

# Run interactively for debugging
docker run -it --gpus all \
  -v $(pwd)/models:/app/models \
  musetalk:latest bash
```

### Download Weights in Running Container

```bash
# If you built without weights, download them in the container
docker exec -it <container_name> ./download_weights_docker.sh
```

## Troubleshooting

### GPU Not Available

```bash
# Check NVIDIA Docker runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi
```

### CUDA Version Mismatch

```bash
# Verify CUDA version in container
docker run --rm musetalk:latest python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}, Version: {torch.version.cuda}')"
```

### Large Image Size

Use multi-stage builds to reduce size:
- Base image: ~2GB
- With dependencies: ~5GB  
- With weights: ~15GB

### Memory Issues During Build

```bash
# Build with limited memory
docker build --memory=8g --memory-swap=16g -t musetalk:latest .
```

## Best Practices

### For Development
- Use volume mounts for code and weights
- Enable interactive mode for debugging
- Mount source code as volume for live editing

### For Production  
- Include weights in image
- Use specific version tags
- Minimize image layers
- Use health checks

### For CI/CD
- Use multi-stage builds
- Cache pip/uv dependencies
- Build separate images for different use cases

## Environment Variables

```bash
# CUDA configuration
CUDA_VISIBLE_DEVICES=0
NVIDIA_VISIBLE_DEVICES=all

# Python configuration  
PYTHONUNBUFFERED=1
PYTHONPATH=/app

# HuggingFace configuration (optional)
HF_ENDPOINT=https://hf-mirror.com
HF_HOME=/app/.cache/huggingface
```

## Resource Requirements

### Minimum
- GPU: 8GB VRAM
- RAM: 16GB
- Storage: 20GB

### Recommended
- GPU: 12GB+ VRAM (RTX 3080/4080 or better)
- RAM: 32GB
- Storage: 50GB (includes weights and outputs)

### Build Resources
- RAM: 8GB+ (during mmcv compilation)
- Storage: 15GB+ (during build)

This setup provides a robust, flexible Docker environment for MuseTalk that handles the complex dependency requirements and weight management challenges identified during the August 7, 2025 setup process.