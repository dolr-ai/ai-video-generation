#!/bin/bash
# MuseTalk Flask API startup script
# Usage: ./start.sh [venv_path] [port] [host]
#
# Examples:
#   ./start.sh                                    # Use default .venv, port 5000, host 0.0.0.0
#   ./start.sh .venv                             # Use .venv in current directory
#   ./start.sh /path/to/venv 8080                # Use custom venv and port 8080
#   ./start.sh .venv 5000 127.0.0.1             # Use local host only

# Parse arguments
VENV_PATH=${1:-".venv"}              # Default to .venv in parent directory
PORT=${2:-5000}                      # Default port 5000
HOST=${3:-"0.0.0.0"}                # Default to all interfaces

# Get the directory of this script (should be MuseTalk/service)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MUSETALK_DIR="$(dirname "$SCRIPT_DIR")"

# Convert relative venv path to absolute if needed
if [[ "$VENV_PATH" != /* ]]; then
    # If it doesn't start with /, it's relative
    if [[ "$VENV_PATH" == ".venv" ]]; then
        # Default case - look in parent directory (MuseTalk root)
        VENV_PATH="${MUSETALK_DIR}/.venv"
    else
        # Other relative paths are relative to script directory
        VENV_PATH="${SCRIPT_DIR}/${VENV_PATH}"
    fi
fi

echo "MuseTalk Flask API Startup"
echo "=========================="
echo "Virtual Environment: $VENV_PATH"
echo "Port: $PORT"
echo "Host: $HOST"
echo "=========================="

# Function to check if virtual environment exists and activate it
activate_venv() {
    local venv_path=$1
    
    if [ -d "$venv_path" ]; then
        if [ -f "$venv_path/bin/activate" ]; then
            echo "✓ Activating virtual environment: $venv_path"
            source "$venv_path/bin/activate"
            echo "✓ Python: $(which python)"
            echo "✓ Python version: $(python --version)"
            return 0
        else
            echo "✗ Virtual environment found but activation script missing: $venv_path/bin/activate"
            return 1
        fi
    else
        echo "✗ Virtual environment not found: $venv_path"
        echo "  You can specify a custom path: ./start.sh /path/to/your/venv"
        return 1
    fi
}

# Try to activate virtual environment
if ! activate_venv "$VENV_PATH"; then
    echo ""
    echo "Continuing without virtual environment activation..."
    echo "Make sure required packages are installed in your current Python environment."
fi

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:${MUSETALK_DIR}"
export FFMPEG_PATH="${MUSETALK_DIR}/ffmpeg-master-latest-linux64-gpl/bin"

echo ""
echo "Environment Setup:"
echo "  MUSETALK_DIR: $MUSETALK_DIR"
echo "  FFMPEG_PATH: $FFMPEG_PATH"
echo "  PYTHONPATH: $PYTHONPATH"

# Check if models exist
if [ ! -d "${MUSETALK_DIR}/models/musetalkV15" ]; then
    echo ""
    echo "⚠️  Warning: MuseTalk models not found!"
    echo "   Expected: ${MUSETALK_DIR}/models/musetalkV15"
    echo "   Please download models first:"
    echo "   cd ${MUSETALK_DIR} && bash download_weights.sh"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
else
    echo "✓ MuseTalk models found"
fi

# Check if FFmpeg exists
if [ -f "${FFMPEG_PATH}/ffmpeg" ]; then
    echo "✓ FFmpeg found: ${FFMPEG_PATH}/ffmpeg"
elif command -v ffmpeg &> /dev/null; then
    echo "✓ FFmpeg found in system PATH"
else
    echo "⚠️  Warning: FFmpeg not found. Video processing may fail."
fi

# Check if MuseTalk package is installed
echo ""
echo "Checking MuseTalk package installation..."
python -c "import musetalk, service" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ MuseTalk package is installed"
else
    echo "✗ MuseTalk package not installed. Installing in development mode..."
    cd "${MUSETALK_DIR}"
    pip install -e .
    if [ $? -eq 0 ]; then
        echo "✓ MuseTalk package installed successfully"
        cd "${SCRIPT_DIR}"
    else
        echo "✗ Failed to install MuseTalk package"
        echo "Please run manually: cd ${MUSETALK_DIR} && pip install -e ."
        exit 1
    fi
fi

# Check Python dependencies
echo ""
echo "Checking core dependencies..."
python -c "import flask, torch, transformers, cv2" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Core dependencies available"
else
    echo "✗ Missing core dependencies. This should have been resolved by 'pip install -e .'"
    echo "  Try: pip install -r ${MUSETALK_DIR}/requirements.txt"
fi

# Set Flask environment variables
export FLASK_APP=app.py
export FLASK_ENV=development
export PORT=$PORT

echo ""
echo "Starting MuseTalk Flask API..."
echo "  URL: http://$HOST:$PORT"
echo "  Health check: http://$HOST:$PORT/api/v1/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo "================================"

# Start Flask app with specified host and port
python -m flask run --host="$HOST" --port="$PORT"