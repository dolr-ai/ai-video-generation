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

### Step 6: Install MMLab Packages (Careful with versions!)
```bash
# Install openmim first (WITHOUT -U flag to avoid numpy upgrade)
uv pip install openmim

# Install MMLab components
mim install mmengine

# Install MMCV - May fail with CUDA mismatch error if building from source
# If mim install fails, use pip with prebuilt wheel instead:
pip install mmcv==2.0.1 -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.0.0/index.html --trusted-host download.openmmlab.com

# Install detection and pose packages
mim install "mmdet==3.1.0"
mim install "mmpose==1.1.0"
```

### Step 7: Check NumPy Version (Important!)
```bash
python -c "import numpy; print(f'NumPy version: {numpy.__version__}')"
# Should output: NumPy version: 1.23.5
# If it shows 2.x, downgrade with: uv pip install "numpy==1.23.5" --force-reinstall
```

### Step 8: Comprehensive Verification
```bash
# Test all ML packages
python -c "
import torch
import torchvision
import mmcv
import mmdet
import mmpose

print('✓ PyTorch version:', torch.__version__)
print('✓ CUDA available:', torch.cuda.is_available())
print('✓ MMCV version:', mmcv.__version__)
print('✓ MMDetection version:', mmdet.__version__)
print('✓ MMPose version:', mmpose.__version__)
print('✓ All imports successful!')
"

# Expected output:
# ✓ PyTorch version: 2.0.1+cu118
# ✓ CUDA available: True
# ✓ MMCV version: 2.0.1
# ✓ MMDetection version: 3.1.0
# ✓ MMPose version: 1.1.0
# ✓ All imports successful!
```

### Step 9: Verify MuseTalk Dependencies
```bash
# Test MuseTalk-specific packages
python -c "
import cv2
import tensorflow as tf
import jax
import diffusers
import transformers
import gradio
import librosa

print('✓ OpenCV version:', cv2.__version__)
print('✓ TensorFlow version:', tf.__version__)
print('✓ JAX version:', jax.__version__)
print('✓ Diffusers version:', diffusers.__version__)
print('✓ Transformers version:', transformers.__version__)
print('✓ Gradio version:', gradio.__version__)
print('✓ Librosa version:', librosa.__version__)
print('✓ All MuseTalk dependencies verified!')
"

# Expected output:
# ✓ OpenCV version: 4.9.0
# ✓ TensorFlow version: 2.12.0
# ✓ JAX version: 0.4.30
# ✓ Diffusers version: 0.30.2
# ✓ Transformers version: 4.39.2
# ✓ Gradio version: 5.24.0
# ✓ Librosa version: 0.11.0
# ✓ All MuseTalk dependencies verified!
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

## Common Issues and Solutions

### CUDA Version Mismatch Error
If you see `The detected CUDA version (X.X) mismatches the version that was used to compile PyTorch (11.8)`:
```bash
# Use prebuilt wheel instead of building from source
pip install mmcv==2.0.1 -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.0.0/index.html --trusted-host download.openmmlab.com
```

### NumPy Version Conflict
If imports fail with NumPy compatibility errors:
```bash
# Force reinstall NumPy 1.23.5
uv pip install "numpy==1.23.5" --force-reinstall
```

### SSL Certificate Errors
If you encounter SSL certificate verification errors:
- Add `--trusted-host download.openmmlab.com` to pip commands
- Or use system certificates: `export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt`

## Next Steps
The environment is ready for running MuseTalk inference. Use the inference scripts:
- For MuseTalk 1.5: `sh inference.sh v1.5 normal`
- For real-time inference: `sh inference.sh v1.5 realtime`