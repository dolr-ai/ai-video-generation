#!/bin/bash

# MuseTalk FastAPI Docker - Validation Script
# Run this on your host system to validate the Docker setup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🐳 MuseTalk FastAPI Docker - Validation Script"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() { echo -e "${BLUE}📋 $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Test 1: Basic Docker functionality
print_step "Test 1: Basic Docker functionality"
if docker --version >/dev/null 2>&1; then
    print_success "Docker is installed: $(docker --version)"
else
    print_error "Docker is not installed or not accessible"
    exit 1
fi

if docker info >/dev/null 2>&1; then
    print_success "Docker daemon is running"
else
    print_error "Docker daemon is not running"
    print_warning "Try: sudo systemctl start docker"
    exit 1
fi

# Test 2: Docker Compose functionality
print_step "Test 2: Docker Compose functionality"
if docker compose version >/dev/null 2>&1; then
    print_success "Docker Compose is available: $(docker compose version)"
elif docker-compose --version >/dev/null 2>&1; then
    print_success "Docker Compose is available: $(docker-compose --version)"
else
    print_error "Docker Compose is not installed"
    exit 1
fi

# Test 3: NVIDIA GPU availability
print_step "Test 3: NVIDIA GPU availability"
if nvidia-smi >/dev/null 2>&1; then
    print_success "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
else
    print_error "NVIDIA GPU or drivers not available"
    print_warning "MuseTalk requires NVIDIA GPU with CUDA support"
    exit 1
fi

# Test 4: NVIDIA Container Toolkit
print_step "Test 4: NVIDIA Container Toolkit"
if docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
    print_success "NVIDIA Container Toolkit is working"
    echo "GPU info from container:"
    docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi --query-gpu=name --format=csv,noheader
else
    print_error "NVIDIA Container Toolkit not working"
    print_warning "Install with: sudo apt-get install nvidia-container-toolkit"
    exit 1
fi

# Test 5: Model weights availability
print_step "Test 5: Model weights availability"
if [ -d "./models/musetalkV15" ] && [ -f "./models/musetalkV15/unet.pth" ]; then
    print_success "MuseTalk model weights found"
    ls -la ./models/
elif [ -d "../models/musetalkV15" ] && [ -f "../models/musetalkV15/unet.pth" ]; then
    print_success "MuseTalk model weights found in parent directory"
    print_warning "Creating symbolic link: ./models -> ../models"
    ln -sf ../models ./models
else
    print_warning "MuseTalk model weights not found"
    echo "You need to download model weights before running the container:"
    echo "1. From MuseTalk directory: bash download_weights_with_venv.sh"
    echo "2. Or copy models to docker/models/ directory"
    echo "3. Or create symbolic link: ln -s /path/to/models ./models"
fi

# Test 6: Dockerfile validation
print_step "Test 6: Dockerfile validation"
if [ -f "./Dockerfile" ]; then
    print_success "Dockerfile exists"
    
    # Check for key instructions
    if grep -q "FROM nvidia/cuda:11.8.0" Dockerfile; then
        print_success "Uses correct NVIDIA CUDA base image"
    else
        print_warning "Dockerfile doesn't use expected CUDA base image"
    fi
    
    if grep -q "uv pip install torch==2.0.1" Dockerfile; then
        print_success "Installs correct PyTorch version"
    else
        print_warning "Dockerfile doesn't install expected PyTorch version"
    fi
    
    if grep -q 'numpy==1.23.5.*--force-reinstall' Dockerfile; then
        print_success "Includes critical NumPy fix"
    else
        print_warning "Dockerfile missing critical NumPy compatibility fix"
    fi
else
    print_error "Dockerfile not found"
    exit 1
fi

# Test 7: Docker Compose configuration
print_step "Test 7: Docker Compose configuration"
if [ -f "./docker-compose.yml" ]; then
    print_success "docker-compose.yml exists"
    
    if grep -q "runtime: nvidia" docker-compose.yml; then
        print_success "Configured for NVIDIA runtime"
    else
        print_warning "docker-compose.yml not configured for NVIDIA runtime"
    fi
    
    if grep -q "8000:8000" docker-compose.yml && grep -q "8001:8001" docker-compose.yml; then
        print_success "Port mapping configured correctly"
    else
        print_warning "Port mapping may be incorrect"
    fi
else
    print_error "docker-compose.yml not found"
    exit 1
fi

# Test 8: Required files check
print_step "Test 8: Required files check"
REQUIRED_FILES=(
    "Dockerfile"
    "docker-compose.yml"
    "start-servers.sh"
    "README.md"
    ".dockerignore"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "$file exists"
    else
        print_warning "$file missing"
    fi
done

# Summary
echo ""
echo "🎯 Validation Summary"
echo "===================="

print_success "System Requirements:"
echo "   ✅ Docker installed and running"
echo "   ✅ Docker Compose available"
echo "   ✅ NVIDIA GPU detected"
echo "   ✅ NVIDIA Container Toolkit working"

if [ -f "./models/musetalkV15/unet.pth" ]; then
    echo "   ✅ Model weights available"
else
    echo "   ⚠️  Model weights need to be downloaded"
fi

echo ""
echo "🚀 Next Steps"
echo "============"
echo "1. If model weights are missing, download them:"
echo "   cd /workspace/ai-video-generation/MuseTalk"
echo "   bash download_weights_with_venv.sh"
echo ""
echo "2. Build and run the Docker container:"
echo "   cd /workspace/ai-video-generation/MuseTalk/docker"
echo "   docker-compose build"
echo "   docker-compose up -d"
echo ""
echo "3. Test the API:"
echo "   curl http://localhost:8000/api/v1/health | jq ."
echo ""
echo "4. Monitor logs:"
echo "   docker-compose logs -f"
echo ""

print_success "Validation completed! Your system is ready for MuseTalk Docker deployment."