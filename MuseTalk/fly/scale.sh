#!/bin/bash
set -e

echo "MuseTalk FastAPI Server - Fly.io Scaling Script"
echo "==============================================="

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

# Parse arguments
ACTION=${1:-status}
COUNT=${2:-1}

case $ACTION in
    up)
        echo "Scaling up to $COUNT machines..."
        flyctl scale count $COUNT --app musetalk-api
        ;;
    down)
        echo "Scaling down to $COUNT machines..."
        flyctl scale count $COUNT --app musetalk-api
        ;;
    gpu)
        echo "Changing GPU type to $COUNT..."
        flyctl scale vm $COUNT --app musetalk-api
        ;;
    status)
        echo "Current scaling status:"
        flyctl scale show --app musetalk-api
        ;;
    *)
        echo "Usage: ./scale.sh [up|down|gpu|status] [count/type]"
        echo "Examples:"
        echo "  ./scale.sh up 2       # Scale to 2 machines"
        echo "  ./scale.sh down 1     # Scale to 1 machine"
        echo "  ./scale.sh gpu l40s   # Change to L40S GPU"
        echo "  ./scale.sh status     # Show current status"
        ;;
esac