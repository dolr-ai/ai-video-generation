#!/bin/bash

# Build and run MuseTalk Docker container

set -e

# Default options
DOWNLOAD_WEIGHTS=false
RUN_INFERENCE=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --download-weights)
      DOWNLOAD_WEIGHTS=true
      shift
      ;;
    --build-only)
      RUN_INFERENCE=false
      shift
      ;;
    --help)
      echo "Usage: $0 [--download-weights] [--build-only] [--help]"
      echo ""
      echo "Options:"
      echo "  --download-weights    Download model weights inside the container during build"
      echo "  --build-only         Only build the image, don't run inference"
      echo "  --help               Show this help message"
      echo ""
      echo "Without --download-weights, weights should be mounted as volumes or downloaded separately."
      exit 0
      ;;
    *)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

echo "🐳 Building MuseTalk Docker image..."

if [ "$DOWNLOAD_WEIGHTS" = true ]; then
    echo "📥 Building with weights download enabled..."
    # Create a temporary Dockerfile with weights download uncommented
    sed 's/# RUN bash download_weights_with_venv.sh/RUN .\/download_weights_docker.sh/' Dockerfile > Dockerfile.tmp
    docker build -f Dockerfile.tmp -t musetalk:latest .
    rm Dockerfile.tmp
    echo "✅ Image built with weights included"
else
    docker build -t musetalk:latest .
    echo "✅ Image built (weights should be mounted as volumes)"
fi

if [ "$RUN_INFERENCE" = true ]; then
    echo ""
    echo "🚀 Running MuseTalk inference..."
    echo "📁 Mounting local directories as volumes:"
    echo "   • ./models -> /app/models"
    echo "   • ./data -> /app/data"
    echo "   • ./results -> /app/results"
    echo "   • ./configs -> /app/configs"
    echo ""
    
    # Create directories if they don't exist
    mkdir -p models data results configs
    
    docker run --gpus all \
      -v $(pwd)/models:/app/models \
      -v $(pwd)/data:/app/data \
      -v $(pwd)/results:/app/results \
      -v $(pwd)/configs:/app/configs \
      musetalk:latest
else
    echo "🏗️  Build complete. Use 'docker run --gpus all musetalk:latest' to run inference."
fi