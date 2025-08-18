#!/bin/bash
set -e

echo "MuseTalk FastAPI Server - Fly.io Deployment Script"
echo "=================================================="

# Check if FLY_API_TOKEN is set
if [ -z "$FLY_API_TOKEN" ]; then
    # Try to load from .env file
    if [ -f "../.env" ]; then
        export $(grep FLY_API_TOKEN ../.env | xargs)
    fi
    
    if [ -z "$FLY_API_TOKEN" ]; then
        echo "Error: FLY_API_TOKEN not set. Please set it or add to .env file."
        exit 1
    fi
fi

# Change to MuseTalk directory
cd /workspace/ai-video-generation/MuseTalk

# Check if fly CLI is installed
if ! command -v flyctl &> /dev/null; then
    echo "Installing Fly CLI..."
    curl -L https://fly.io/install.sh | sh
    export PATH="$HOME/.fly/bin:$PATH"
fi

# Authenticate with Fly.io
echo "Authenticating with Fly.io..."
flyctl auth token $FLY_API_TOKEN

# Check if app already exists
if flyctl apps list | grep -q "musetalk-api"; then
    echo "App 'musetalk-api' already exists."
    read -p "Do you want to deploy to existing app? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 1
    fi
else
    echo "Creating new Fly app 'musetalk-api'..."
    flyctl apps create musetalk-api --org personal
fi

# Create volume if it doesn't exist (WITH GPU CONSTRAINT - only 1 volume supported)
echo "Setting up persistent volume with GPU constraint..."
if ! flyctl volumes list --app musetalk-api | grep -q "musetalk_models"; then
    echo "Creating models volume (100GB) with L40S GPU constraint..."
    flyctl volumes create musetalk_models \
        --size 100 \
        --region ord \
        --vm-gpu-kind l40s \
        --app musetalk-api
else
    echo "Models volume already exists"
fi

# Environment variables are set in fly.toml
# No need for secrets since both servers run on same machine
echo "Environment configured in fly.toml..."

# Deploy the application
echo "Deploying MuseTalk to Fly.io..."
flyctl deploy --config fly/fly.toml --app musetalk-api --ha=false

# Show deployment status
echo ""
echo "Deployment complete! Checking status..."
flyctl status --app musetalk-api

# Get the app URL
APP_URL=$(flyctl info --app musetalk-api -j | jq -r '.Hostname')
echo ""
echo "=================================================="
echo "MuseTalk API deployed successfully!"
echo "API URL: https://$APP_URL"
echo "Health check: https://$APP_URL/api/v1/health"
echo ""
echo "To view logs: flyctl logs --app musetalk-api"
echo "To SSH into machine: flyctl ssh console --app musetalk-api"
echo "=================================================="