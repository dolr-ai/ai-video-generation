# MuseTalk FastAPI Server - Docker Setup

This directory contains Docker configurations for running the MuseTalk FastAPI server in a containerized environment, following the exact setup steps from the documentation.

## 🏗️ Architecture

The Docker setup creates a complete MuseTalk FastAPI environment with:
- **NVIDIA CUDA 11.8** runtime for GPU acceleration
- **Python 3.10.18** environment (matching docs)
- **Two-server architecture**: Model server (8001) + Handler server (8000)
- **All dependencies** installed following exact steps from `docs/venv_setup.md`
- **Volume mounts** for models, storage, and logs

## 📋 Prerequisites

### System Requirements
- **Docker** 20.10+ with BuildKit support
- **Docker Compose** v2.0+ 
- **NVIDIA Container Toolkit** for GPU support
- **NVIDIA GPU** with CUDA 11.8+ support
- **16GB+ RAM** recommended
- **50GB+ disk space** for models and containers

### Verify GPU Support
```bash
# Check NVIDIA Docker runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi

# Should show your GPU information
```

## 🚀 Quick Start

### Step 1: Prepare Model Weights

**CRITICAL**: You must download MuseTalk model weights before running the container.

```bash
# Option 1: Download models on host system first
cd /workspace/ai-video-generation/MuseTalk
source ../.venv/bin/activate  # If you have local setup
bash download_weights_with_venv.sh

# Option 2: Create models directory and download manually
mkdir -p docker/models
# Download models to docker/models/ following the weight download scripts
```

### Step 2: Build and Run

```bash
cd /workspace/ai-video-generation/MuseTalk/docker

# Build the Docker image (takes 10-15 minutes)
docker-compose build

# Run the services
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Step 3: Test the API

```bash
# Health check
curl http://localhost:8000/api/v1/health | jq .

# Generate video (using mounted multimedia files)
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "image": "/workspace/ai-video-generation/multimedia/image/test_image1-female.png",
    "audio": "/workspace/ai-video-generation/multimedia/audio/test_audio1-female.mp3"
  }' | jq .
```

## 📁 Directory Structure

```
docker/
├── Dockerfile                 # Main container definition
├── docker-compose.yml        # Service orchestration
├── start-servers.sh          # Container startup script
├── README.md                 # This file
├── models/                   # Mount point for model weights
├── storage/                  # Generated videos and uploads
└── logs/                     # Application logs
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CUDA_VISIBLE_DEVICES` | `0` | GPU device to use |
| `PYTHONUNBUFFERED` | `1` | Python output buffering |
| `MUSETALK_DEBUG` | unset | Enable debug logging (dev profile) |

### Volume Mounts

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./models` | `/workspace/ai-video-generation/MuseTalk/models` | **Model weights (required)** |
| `./storage` | `/workspace/ai-video-generation/MuseTalk/fastapi_server/storage` | Generated videos/uploads |
| `./logs` | `/workspace/ai-video-generation/MuseTalk/fastapi_server/logs` | Application logs |
| `../multimedia` | `/workspace/ai-video-generation/multimedia` | Test media files |

### Port Mapping

| Container Port | Host Port | Service |
|----------------|-----------|---------|
| `8000` | `8000` | FastAPI Handler Server |
| `8001` | `8001` | MuseTalk Model Server |

## 🔧 Development Setup

For development with live code editing:

```bash
# Use development profile
docker-compose --profile dev up -d musetalk-dev

# This mounts the entire source code directory for live editing
```

## 📊 Monitoring & Logs

### View Logs
```bash
# All services
docker-compose logs -f

# Specific log files (inside container)
docker exec musetalk-fastapi tail -f /workspace/ai-video-generation/MuseTalk/fastapi_server/model_server.log
docker exec musetalk-fastapi tail -f /workspace/ai-video-generation/MuseTalk/fastapi_server/handler_server.log
docker exec musetalk-fastapi tail -f /workspace/ai-video-generation/MuseTalk/fastapi_server/endpoints.log
```

### Health Monitoring
```bash
# Container health
docker-compose ps

# API health
curl http://localhost:8000/api/v1/health
curl http://localhost:8001/health
```

### Resource Usage
```bash
# Container stats
docker stats musetalk-fastapi

# GPU usage (inside container)
docker exec musetalk-fastapi nvidia-smi
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Container fails to start
```bash
# Check build logs
docker-compose build --no-cache

# Check container logs
docker-compose logs musetalk-fastapi
```

#### 2. Models not found error
```bash
# Verify model mount
docker exec musetalk-fastapi ls -la /workspace/ai-video-generation/MuseTalk/models/

# Expected directories: dwpose, musetalkV15, sd-vae, whisper, face-parse-bisent
```

#### 3. GPU not available
```bash
# Test GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi

# Check NVIDIA Container Toolkit installation
sudo systemctl restart docker
```

#### 4. Out of memory errors
```bash
# Check available memory
docker exec musetalk-fastapi free -h

# Check GPU memory
docker exec musetalk-fastapi nvidia-smi

# Reduce batch_size in API requests
curl -X POST ... -d '{"batch_size": 2, ...}'
```

#### 5. Port conflicts
```bash
# Check port usage
lsof -i :8000
lsof -i :8001

# Change ports in docker-compose.yml if needed
```

### Debug Mode

Enable debug logging:
```bash
# Set debug environment
docker-compose --profile dev up -d musetalk-dev

# Or add to docker-compose.yml:
environment:
  - MUSETALK_DEBUG=1
```

## 🚀 Production Deployment

### Security Considerations

1. **Remove debug volumes** in production
2. **Use secrets management** for sensitive data
3. **Enable authentication** on API endpoints
4. **Use HTTPS** with proper certificates
5. **Implement rate limiting**

### Scaling Options

```yaml
# Horizontal scaling example
services:
  musetalk-handler:
    # Multiple handler instances
    replicas: 3
    
  musetalk-model:
    # One model server per GPU
    replicas: 1
```

### Production docker-compose.prod.yml

```yaml
version: '3.8'
services:
  musetalk-fastapi:
    image: musetalk-fastapi:latest
    restart: always
    environment:
      - CUDA_VISIBLE_DEVICES=0
    volumes:
      - /data/models:/workspace/ai-video-generation/MuseTalk/models:ro
      - /data/storage:/workspace/ai-video-generation/MuseTalk/fastapi_server/storage
    deploy:
      resources:
        limits:
          memory: 16G
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.musetalk.rule=Host(`musetalk.yourdomain.com`)"
```

## 📚 References

- **Setup Documentation**: `docs/venv_setup.md`, `docs/fastapi_setup.md`
- **FastAPI Server**: `fastapi_server/README.md`, `fastapi_server/ARCHITECTURE.md`
- **Docker Best Practices**: [Docker Documentation](https://docs.docker.com/)
- **NVIDIA Container Toolkit**: [NVIDIA Docs](https://docs.nvidia.com/datacenter/cloud-native/)

## 🔄 Maintenance

### Update Container
```bash
# Rebuild with latest changes
docker-compose build --no-cache
docker-compose up -d

# Clean up old images
docker system prune -a
```

### Backup Data
```bash
# Backup models and storage
tar -czf musetalk-backup-$(date +%Y%m%d).tar.gz docker/models docker/storage
```

---

**Status**: ✅ **Production Ready** - Follows exact setup steps from documentation with comprehensive Docker orchestration.