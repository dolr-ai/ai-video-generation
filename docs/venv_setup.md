# MuseTalk Virtual Environment Setup - Successful Steps

## Environment Details
- Python Version: 3.10.18
- Package Manager: uv (version 0.7.16)
- CUDA Support: 11.8
- Date: 2025-08-10

## Successful Setup Steps - EXACT ORDER

### Step 1: Navigate to MuseTalk Directory
```bash
cd /workspace/ai-video-generation/MuseTalk
pwd  # Output: /workspace/ai-video-generation/MuseTalk
```

### Step 2: Create Virtual Environment in Parent Directory
```bash
uv venv ../.venv --python 3.10
# Output: Using CPython 3.10.18
# Creating virtual environment at: ../.venv
```

### Step 3: Activate Virtual Environment
```bash
source ../.venv/bin/activate
which python  # Verify: /workspace/ai-video-generation/.venv/bin/python
python --version  # Output: Python 3.10.18
```

### Step 4: Install PyTorch with CUDA 11.8 Support
```bash
uv pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
# This installed torch==2.0.1+cu118 and numpy==2.1.2 initially
```

### Step 5: Install Requirements from requirements.txt
```bash
uv pip install -r requirements.txt
# This installed numpy==1.23.5 as specified in requirements.txt
# Also installed all other dependencies like diffusers, transformers, etc.
```

### Step 6: Install MMLab Packages (This caused NumPy upgrade issue)
```bash
# Install openmim first
uv pip install --no-cache-dir -U openmim
# WARNING: This upgraded numpy from 1.23.5 to 2.2.6!

# Install MMLab components using mim
mim install mmengine
mim install "mmcv==2.0.1"
mim install "mmdet==3.1.0"
mim install "mmpose==1.1.0"
```

### Step 7: First Import Test (FAILED)
```bash
python -c "import torch; import torchvision; import mmcv"
# ERROR: NumPy version incompatibility error occurred here
```

### Step 8: Fix NumPy Version Compatibility (CRITICAL FIX)
```bash
# Force downgrade numpy back to compatible version
uv pip install "numpy==1.23.5" --force-reinstall
# This resolved the compatibility issue
```

### Step 9: Verify Installation
```bash
python -c "import torch; import torchvision; import mmcv; import mmdet; import mmpose; print('PyTorch version:', torch.__version__); print('CUDA available:', torch.cuda.is_available())"
# Output: PyTorch version: 2.0.1+cu118
# Output: CUDA available: True
```

### Step 10: Download Model Weights
```bash
# Note: The script expects .venv in current directory but ours is in parent
source ../.venv/bin/activate && bash download_weights_with_venv.sh
# Script showed error about .venv/bin/activate not found but continued successfully
# Downloaded all model weights to models/ directory
```

### Step 11: Test Inference
```bash
source ../.venv/bin/activate
python -m scripts.inference \
    --inference_config configs/inference/test.yaml \
    --result_dir results/test \
    --unet_model_path models/musetalkV15/unet.pth \
    --unet_config models/musetalkV15/musetalk.json \
    --version v15 \
    --ffmpeg_path /usr/bin/ffmpeg
# Successfully generated video: results/test/v15/yongen_yongen.mp4
```

## Verification

### Test Package Imports
```python
import torch
import torchvision
import mmcv
import mmdet
import mmpose

print('PyTorch version:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())
```

Expected output:
- PyTorch version: 2.0.1+cu118
- CUDA available: True

### Verify Model Weights
```bash
ls -la models/
```

Should show directories:
- musetalk/
- musetalkV15/
- sd-vae/
- whisper/
- dwpose/
- syncnet/
- face-parse-bisent/

## Dependencies Successfully Installed

### Core ML Frameworks
- PyTorch 2.0.1 with CUDA 11.8
- TensorFlow 2.12.0
- JAX/JAXlib 0.4.30

### Computer Vision
- OpenCV 4.9.0.80
- MMCV 2.0.1
- MMDetection 3.1.0
- MMPose 1.1.0

### Audio/Video Processing
- FFmpeg (system installed: 6.1.1)
- librosa 0.11.0
- soundfile 0.12.1
- moviepy 1.0.3

### Deep Learning Components
- Diffusers 0.30.2
- Transformers 4.39.2
- Accelerate 0.28.0

### Web Interface
- Gradio 5.24.0

## System Requirements Met
✅ Python 3.10
✅ CUDA 11.8 compatible GPU detected
✅ FFmpeg installed
✅ All model weights downloaded
✅ All dependencies installed via uv

## Next Steps
The environment is ready for running MuseTalk inference. Use the inference scripts:
- For MuseTalk 1.5: `sh inference.sh v1.5 normal`
- For real-time inference: `sh inference.sh v1.5 realtime`