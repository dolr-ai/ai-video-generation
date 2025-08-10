#!/bin/bash

# Start MuseTalk Model Server
echo "Starting MuseTalk Model Server..."

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source $SCRIPT_DIR/../.venv/bin/activate

# Change to MuseTalk directory (required for relative paths in MuseTalk)
cd $SCRIPT_DIR/../MuseTalk

# Set PYTHONPATH to include fastapi_server
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Start model server
python $SCRIPT_DIR/model_server.py