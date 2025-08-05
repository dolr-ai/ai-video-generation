# MuseTalk Setup Guide - Working Installation

## Prerequisites
- Python 3.10
- CUDA 11.8 (optional, for GPU support)
- uv package manager

## System Dependencies (IMPORTANT)
Before starting the Python setup, install these system libraries required by OpenCV:

```bash
# Update package list and install OpenGL libraries
apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0
```

These libraries are essential for OpenCV to work properly. Without them, you'll get:
`ImportError: libGL.so.1: cannot open shared object file: No such file or directory`

## Working Step-by-Step Installation

### 1. Create Virtual Environment
```bash
cd /home/sagx/talking-head/MuseTalk
bash ../just_uv.sh --py3.10
source .venv/bin/activate
```

### 2. Install PyTorch 2.0.1 (Critical Version)
The README specifically requires PyTorch 2.0.1, not the latest version.

```bash
# Using uv to install specific PyTorch version
uv pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
```

**Result**: Successfully installed torch-2.0.1+cu118, torchvision-0.15.2+cu118, torchaudio-2.0.2+cu118

### 3. Install Base Requirements
```bash
uv pip install -r requirements.txt
```

**Note**: This will downgrade numpy to 1.23.5 as required by requirements.txt

### 4. Install MMLab Packages with openmim
This is critical - do NOT use pip/uv directly for mm* packages:

```bash
# Install openmim first
uv pip install --no-cache-dir -U openmim

# Use mim to install specific versions - mim will download pre-built wheels
python -m mim install mmengine      # Successfully installed mmengine-0.10.7
python -m mim install "mmcv==2.0.1" # Downloaded pre-built wheel from https://download.openmmlab.com/
python -m mim install "mmdet==3.1.0" # Successfully installed mmdet-3.1.0
python -m mim install "mmpose==1.1.0" # Successfully installed mmpose-1.1.0
```

### 5. Setup FFmpeg
```bash
# Download and extract ffmpeg
wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
tar -xf ffmpeg-master-latest-linux64-gpl.tar.xz

# Set environment variable
export FFMPEG_PATH=/home/sagx/talking-head/MuseTalk/ffmpeg-master-latest-linux64-gpl
```

### 6. Model Weights
Model weights have been downloaded using the download_weights_with_venv.sh script:
- models/musetalkV15/unet.pth
- models/sd-vae/diffusion_pytorch_model.bin
- models/whisper/pytorch_model.bin
- models/dwpose/dw-ll_ucoco_384.pth
- models/syncnet/latentsync_syncnet.pt
- models/face-parse-bisent/79999_iter.pth

### 7. Fix numpy compatibility issue
After installing openmim, numpy may be upgraded to 2.x which causes compatibility issues:

```bash
source .venv/bin/activate
uv pip install "numpy<2"  # Downgrade to numpy 1.x for opencv-python compatibility
```

### 8. Test the Installation
```bash
export FFMPEG_PATH=/home/sagx/talking-head/MuseTalk/ffmpeg-master-latest-linux64-gpl
source .venv/bin/activate
python -m scripts.inference --inference_config ./configs/inference/test.yaml --result_dir ./results/test --unet_model_path ./models/musetalkV15/unet.pth --unet_config ./models/musetalkV15/musetalk.json --version v15 --ffmpeg_path $FFMPEG_PATH/bin
```

**Expected output**: Two videos generated in `./results/test/v15/`:
- `yongen_yongen.mp4` - Original video with matching audio
- `yongen_eng.mp4` - Original video with English audio (bbox_shift: -7)

## ✅ Installation Complete!

The setup is now working successfully. Key success factors:

1. **System dependencies** - Install libgl1-mesa-glx BEFORE running inference
2. **PyTorch 2.0.1 is MANDATORY** - Using 2.7.x will cause compatibility issues
3. **Use mim install** - This downloads pre-built wheels avoiding compilation issues
4. **Install order matters** - Follow the exact sequence above
5. **Pre-built wheels** - mim automatically selects compatible pre-built wheels for cu118/torch2.0.0
6. **No manual compilation** - Avoid building mmcv from source which causes the _ext module errors
7. **Numpy compatibility** - Downgrade to numpy<2 after openmim installation
8. **FFmpeg setup** - Use static build to avoid system dependency issues

## Troubleshooting

### ImportError: libGL.so.1: cannot open shared object file
**Solution**: Install system dependencies
```bash
apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0
```

### mmcv._ext module not found
**Solution**: Ensure you installed mmcv using mim, not pip:
```bash
python -m mim install "mmcv==2.0.1"
```

### Inference takes very long time
This is normal. Processing 268 frames can take 5-10 minutes depending on your hardware. The process will show progress bars and create output files in `./results/test/v15/`