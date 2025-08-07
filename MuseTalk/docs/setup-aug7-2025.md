# MuseTalk Setup - August 7, 2025

## Environment
- NVIDIA L40S GPU 
- CUDA 12.8
- Python 3.10
- Ubuntu Linux

## What We Fixed

### 1. Deprecated HuggingFace CLI Warning
**Problem**: `⚠️ Warning: 'huggingface-cli download' is deprecated. Use 'hf download' instead.`

**Solution**: Updated `download_weights_with_venv.sh`
```bash
# Changed from:
huggingface-cli download TMElyralab/MuseTalk --local-dir $CheckpointsDir --include "musetalk/musetalk.json" "musetalk/pytorch_model.bin"

# To:
hf download TMElyralab/MuseTalk --local-dir $CheckpointsDir --include "musetalk/musetalk.json" "musetalk/pytorch_model.bin"
```

### 2. PyTorch uint64 Compatibility
**Problem**: `AttributeError: module 'torch' has no attribute 'uint64'`

**Solution**: Upgraded PyTorch from 2.0.1 to 2.8.0
```bash
source .venv/bin/activate
uv pip install --upgrade "torch>=2.1.0" "torchvision" "torchaudio"
# Result: torch==2.8.0+cu128, torchvision==0.23.0, torchaudio==2.8.0
```

### 3. NumPy 2.x/OpenCV Incompatibility  
**Problem**: `A module that was compiled using NumPy 1.x cannot be run in NumPy 2.2.6`

**Solution**: Downgrade NumPy to 1.x
```bash
source .venv/bin/activate
uv pip install "numpy<2"
# Result: numpy==1.26.4
```

### 4. Fixed .gitignore for Model Directories
**Problem**: Confusion between two `models` directories (weights vs code)

**Solution**: Updated `.gitignore`
```gitignore
# Model weights and artifacts (but keep model definitions)
/models/
!/musetalk/models/

# Virtual environment
.venv/
venv/
env/
```

### 5. Flask Service Dependencies
```bash
source .venv/bin/activate
uv pip install flask flask-cors
```

## Current Status

### ✅ What Works
- Core MuseTalk models import successfully: `from musetalk.models.vae import VAE; from musetalk.models.unet import UNet`
- PyTorch CUDA detection: `torch.cuda.is_available() == True` with NVIDIA L40S
- Model weight downloads with updated script
- Flask service starts (blocked at preprocessing)

### ❌ What's Blocked
**Face Preprocessing**: `ModuleNotFoundError: No module named 'mmcv._ext'`

**Root Cause**: mmcv CUDA extensions compilation issues
- No pre-built wheels for CUDA 12.8 + PyTorch 2.8 combination  
- Source compilation fails with C++ template errors
- Dependency chain: inference → preprocessing → mmpose → mmdet → mmcv (with CUDA ops)

## Installation Commands That Work

```bash
# 1. Setup environment
source .venv/bin/activate

# 2. Upgrade PyTorch for compatibility
uv pip install --upgrade "torch>=2.1.0" "torchvision" "torchaudio"

# 3. Fix NumPy compatibility
uv pip install "numpy<2"

# 4. Download weights (fixed script)
bash download_weights_with_venv.sh

# 5. Install service dependencies
uv pip install flask flask-cors

# 6. Test core models (works)
python -c "from musetalk.models.vae import VAE; from musetalk.models.unet import UNet; print('Core models work!')"
```

## Failed Attempts (see trials.md for details)

1. **mmcv-lite**: No CUDA extensions, mmdet fails
2. **mmcv from OpenMMLab index**: 404 errors for CUDA 12.8/PyTorch 2.8 
3. **Building from source**: C++ compilation failures
4. **Using mim/openmim**: Still tries to build from source
5. **Setting CUDA_HOME**: Compilation still fails

## Next Steps Needed

To complete the setup, need to resolve mmcv CUDA extensions:
- Either downgrade PyTorch/CUDA to supported combination
- Or find alternative face preprocessing without mmpose
- Or wait for mmcv pre-built wheels for newer versions

**Current Blocker**: mmcv compilation incompatibility with CUDA 12.8 + PyTorch 2.8