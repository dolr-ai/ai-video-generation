# MuseTalk Installation Guide

## Quick Setup

1. **Setup MuseTalk environment** (if not already done):
   ```bash
   cd MuseTalk
   source .venv/bin/activate  # or create venv if needed
   ```

2. **Install MuseTalk package in development mode**:
   ```bash
   uv pip install -e .
   ```
   This installs both MuseTalk core and the Flask API service with proper imports.

3. **Run the API**:
   ```bash
   # Option 1: Use console script (easiest)
   musetalk-api
   
   # Option 2: Use startup script with health checks
   cd service && ./start.sh
   
   # Option 3: Direct Python execution
   cd service && python app.py
   ```

## What gets installed

- **MuseTalk core package** with all dependencies from `requirements.txt`
- **Flask API service** with dependencies from `service/requirements.txt`
- **Console scripts**:
  - `musetalk-api` - Start the Flask API server
  - `musetalk-inference` - Run inference directly
  - `musetalk-realtime` - Run real-time inference

## Directory Structure

```
MuseTalk/
├── setup.py              # Package setup
├── pyproject.toml         # Modern Python packaging
├── musetalk/             # Core MuseTalk package
│   ├── __init__.py
│   ├── utils/
│   ├── models/
│   └── ...
├── service/              # Flask API service
│   ├── __init__.py
│   ├── app.py           # Main Flask app
│   ├── api/             # API routes
│   ├── core/            # Business logic
│   ├── config/          # Configuration
│   └── utils/           # Utilities
└── scripts/             # CLI scripts
```

## Benefits of this setup

✅ **No more import issues** - Clean absolute imports everywhere  
✅ **No sys.path manipulation** - Proper Python packaging  
✅ **Development mode** - Changes reflected immediately  
✅ **Console scripts** - Easy command-line access  
✅ **Virtual environment support** - Works with any venv  
✅ **Cross-platform** - Works on different systems

## Troubleshooting

If you get import errors:
1. Make sure you're in the activated virtual environment
2. Run `uv pip install -e .` from the MuseTalk root directory
3. Test imports: `python -c "import musetalk; import service"`

If the API won't start:
1. Check that models are downloaded: `ls models/musetalkV15/`
2. Verify FFmpeg: `ffmpeg -version`
3. Use the startup script for detailed health checks: `./service/start.sh`