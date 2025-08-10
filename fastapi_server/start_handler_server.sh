#!/bin/bash

# Start MuseTalk Handler Server
echo "Starting MuseTalk Handler Server..."

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source $SCRIPT_DIR/../.venv/bin/activate

# Set PYTHONPATH to include fastapi_server
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Start handler server from its directory
cd $SCRIPT_DIR
python handler_server.py