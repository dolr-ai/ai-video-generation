#!/bin/bash
set -e

echo "MuseTalk FastAPI Server - Fly.io Monitoring"
echo "==========================================="

# Check if FLY_API_TOKEN is set
if [ -z "$FLY_API_TOKEN" ]; then
    if [ -f "../.env" ]; then
        export $(grep FLY_API_TOKEN ../.env | xargs)
    fi
    
    if [ -z "$FLY_API_TOKEN" ]; then
        echo "Error: FLY_API_TOKEN not set."
        exit 1
    fi
fi

# Authenticate
flyctl auth token $FLY_API_TOKEN

ACTION=${1:-health}

case $ACTION in
    health)
        echo "Checking health status..."
        APP_URL=$(flyctl info --app musetalk-api -j | jq -r '.Hostname')
        curl -s "https://$APP_URL/api/v1/health" | jq .
        ;;
    logs)
        echo "Streaming logs (Ctrl+C to stop)..."
        flyctl logs --app musetalk-api
        ;;
    ssh)
        echo "Connecting to machine via SSH..."
        flyctl ssh console --app musetalk-api
        ;;
    status)
        echo "Application status:"
        flyctl status --app musetalk-api
        ;;
    metrics)
        echo "Opening metrics dashboard..."
        flyctl dashboard metrics --app musetalk-api
        ;;
    *)
        echo "Usage: ./monitor.sh [health|logs|ssh|status|metrics]"
        echo "  health  - Check API health endpoint"
        echo "  logs    - Stream application logs"
        echo "  ssh     - SSH into the machine"
        echo "  status  - Show machine status"
        echo "  metrics - Open metrics dashboard"
        ;;
esac