#!/bin/bash

# MuseTalk FastAPI Docker - Build and Test Script

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🐳 MuseTalk FastAPI Docker Build and Test"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}📋 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Step 1: Prerequisites check
print_step "Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed!"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed!"
    exit 1
fi

# Check NVIDIA Docker
if ! docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi &> /dev/null; then
    print_error "NVIDIA Docker runtime not available!"
    print_warning "Make sure NVIDIA Container Toolkit is installed"
    exit 1
fi

print_success "All prerequisites met"

# Step 2: Check for model weights
print_step "Checking for model weights..."

if [ ! -d "./models/musetalkV15" ] || [ ! -f "./models/musetalkV15/unet.pth" ]; then
    print_warning "Model weights not found in docker/models/"
    echo "You need to download MuseTalk model weights before building."
    echo ""
    echo "Options:"
    echo "1. Run from MuseTalk directory: bash download_weights_with_venv.sh"
    echo "2. Copy models to docker/models/ directory"
    echo "3. Create symbolic link: ln -s ../models ./models"
    echo ""
    read -p "Do you want to continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    print_success "Model weights found"
fi

# Step 3: Clean up previous containers
print_step "Cleaning up previous containers..."
docker-compose down --remove-orphans || true
docker system prune -f || true
print_success "Cleanup completed"

# Step 4: Build the Docker image
print_step "Building Docker image..."
echo "This will take 10-15 minutes..."

if docker-compose build --no-cache; then
    print_success "Docker image built successfully"
else
    print_error "Docker build failed!"
    exit 1
fi

# Step 5: Start the services
print_step "Starting services..."
docker-compose up -d

# Step 6: Wait for services to be ready
print_step "Waiting for services to start..."

# Wait for model server (can take up to 5 minutes for model loading)
echo "⏳ Waiting for model server to load models (this may take several minutes)..."
for i in {1..60}; do
    if curl -s -f http://localhost:8001/health >/dev/null 2>&1; then
        print_success "Model server is ready!"
        break
    fi
    if [ $i -eq 60 ]; then
        print_error "Model server failed to start within 5 minutes"
        print_warning "Check logs: docker-compose logs musetalk-fastapi"
        exit 1
    fi
    sleep 5
    echo "   Still waiting for model server... ($i/60)"
done

# Wait for handler server
echo "⏳ Waiting for handler server..."
for i in {1..30}; do
    if curl -s -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
        print_success "Handler server is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Handler server failed to start within 2.5 minutes"
        exit 1
    fi
    sleep 5
    echo "   Still waiting for handler server... ($i/30)"
done

# Step 7: Run health checks
print_step "Running health checks..."

# Test model server health
MODEL_HEALTH=$(curl -s http://localhost:8001/health || echo "FAILED")
if [[ "$MODEL_HEALTH" == *"healthy"* ]]; then
    print_success "Model server health check passed"
else
    print_error "Model server health check failed"
    echo "Response: $MODEL_HEALTH"
fi

# Test handler server health  
HANDLER_HEALTH=$(curl -s http://localhost:8000/api/v1/health || echo "FAILED")
if [[ "$HANDLER_HEALTH" == *"healthy"* ]]; then
    print_success "Handler server health check passed"
    echo "Full response: $HANDLER_HEALTH"
else
    print_error "Handler server health check failed"
    echo "Response: $HANDLER_HEALTH"
fi

# Step 8: Optional API test
print_step "Testing API endpoints..."

if [ -f "../multimedia/image/test_image1-female.png" ] && [ -f "../multimedia/audio/test_audio1-female.mp3" ]; then
    print_step "Running video generation test..."
    
    TEST_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/generate \
        -H "Content-Type: application/json" \
        -d '{
            "image": "/workspace/ai-video-generation/multimedia/image/test_image1-female.png",
            "audio": "/workspace/ai-video-generation/multimedia/audio/test_audio1-female.mp3",
            "batch_size": 2
        }' || echo "FAILED")
    
    if [[ "$TEST_RESPONSE" == *"accepted"* ]]; then
        print_success "API test request accepted"
        TASK_ID=$(echo "$TEST_RESPONSE" | grep -o '"task_id":"[^"]*' | cut -d'"' -f4)
        echo "Task ID: $TASK_ID"
        echo "Check status: curl http://localhost:8000/api/v1/status/$TASK_ID"
    else
        print_warning "API test failed - but this might be expected without test media files"
        echo "Response: $TEST_RESPONSE"
    fi
else
    print_warning "Test media files not found - skipping API test"
fi

# Final status
print_step "Build and test completed!"
echo ""
echo "🎉 MuseTalk FastAPI Server is running in Docker!"
echo "================================================"
echo "📡 Services:"
echo "   • Handler Server: http://localhost:8000"
echo "   • Model Server:   http://localhost:8001"
echo "   • Health Check:   http://localhost:8000/api/v1/health"
echo ""
echo "📝 Management Commands:"
echo "   • View logs:      docker-compose logs -f"
echo "   • Stop services:  docker-compose down"
echo "   • Restart:        docker-compose restart"
echo ""
echo "💡 Example API usage:"
echo '   curl -X POST http://localhost:8000/api/v1/generate \'
echo '     -H "Content-Type: application/json" \'
echo '     -d "{\"image\": \"/path/to/image.jpg\", \"audio\": \"/path/to/audio.mp3\"}"'
echo ""
echo "📚 Documentation: docker/README.md"
echo "================================================"