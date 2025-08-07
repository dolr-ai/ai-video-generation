# MuseTalk Setup Solution - August 7, 2025

## Executive Summary
Successfully set up MuseTalk after resolving critical compatibility issues between PyTorch 2.0.1, CUDA 12.8, and the MMLab ecosystem (mmcv/mmpose/mmdet).

## Critical Issues Encountered

### 1. PyTorch uint64 Attribute Error
**Error**: `AttributeError: module 'torch' has no attribute 'uint64'`

**Root Cause**: 
- PyTorch 2.0.1 doesn't have the `torch.uint64` attribute
- Newer versions of `safetensors` (≥0.4.0) and `transformers` (≥4.30.0) expect this attribute

**Solution**:
```bash
# Downgrade to compatible versions
uv pip install "safetensors<0.4.0" "transformers<4.30.0"
```

### 2. NumPy 2.x Incompatibility
**Error**: `A module that was compiled using NumPy 1.x cannot be run in NumPy 2.2.6`

**Root Cause**:
- OpenCV-Python was compiled with NumPy 1.x
- Package installations kept upgrading to NumPy 2.x

**Solution**:
```bash
# Force NumPy 1.x after all installations
uv pip install "numpy<2"
```

### 3. MMCV CUDA Extensions Missing
**Error**: `ModuleNotFoundError: No module named 'mmcv._ext'`

**Root Cause**:
- CUDA 12.8 + PyTorch 2.8 combination has no pre-built mmcv wheels
- Building from source fails due to C++ template compatibility issues
- The project actually requires CUDA 11.8, not 12.8

**Solution**:
```bash
# Use PyTorch 2.0.1 with CUDA 11.8 (as specified in README)
uv pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118

# Use mim to install pre-built wheels for CUDA 11.8
python -m mim install "mmcv==2.0.1"  # Downloads pre-built wheel from OpenMMLab
```

### 4. HuggingFace CLI Deprecation
**Warning**: `'huggingface-cli download' is deprecated. Use 'hf download' instead`

**Solution**: Updated `download_weights_with_venv.sh` to use `hf download`

### 5. Model Directory Confusion
**Issue**: Two directories named `models/`:
- `/models/` - Downloaded weights (should be in .gitignore)
- `/musetalk/models/` - Python model definitions (should be tracked)

**Solution**: Updated `.gitignore`:
```gitignore
# Ignore weights but keep model definitions
/models/
!/musetalk/models/
```

## Working Installation Sequence

### Prerequisites
- Python 3.10 (MANDATORY)
- CUDA 11.8 (NOT 12.8!)
- System libraries: `libgl1-mesa-glx libglib2.0-0`

### Step-by-Step Solution

1. **Create Python 3.10 environment**:
```bash
bash ../just_uv.sh --py3.10
source .venv/bin/activate
```

2. **Install PyTorch 2.0.1 with CUDA 11.8**:
```bash
uv pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
```

3. **Install requirements**:
```bash
uv pip install -r requirements.txt
```

4. **Install MMLab packages with mim** (CRITICAL):
```bash
uv pip install --no-cache-dir -U openmim
python -m mim install mmengine
python -m mim install "mmcv==2.0.1"    # Downloads pre-built wheel
python -m mim install "mmdet==3.1.0"
python -m mim install "mmpose==1.1.0"
```

5. **Fix compatibility issues**:
```bash
uv pip install "numpy<2" "safetensors<0.4.0" "transformers<4.30.0"
```

6. **Download model weights**:
```bash
bash download_weights_with_venv.sh
```

## Key Insights

### Why Previous Attempts Failed

1. **Wrong CUDA Version**: Used CUDA 12.8 instead of 11.8
2. **Wrong Installation Method**: Used pip/uv directly instead of mim for mmcv
3. **Version Mismatches**: Let packages auto-upgrade to incompatible versions
4. **Compilation Attempts**: Tried to build mmcv from source instead of using pre-built wheels

### Critical Success Factors

1. **Exact Version Matching**: PyTorch 2.0.1 + CUDA 11.8 + mmcv 2.0.1
2. **mim Package Manager**: Automatically downloads correct pre-built wheels
3. **Dependency Downgrading**: Keep older compatible versions
4. **uv Speed**: Much faster than pip for large dependency trees

## Verification

Test successful installation:
```bash
python -c "
import torch
import mmcv
from mmcv.ops import nms
print('PyTorch:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())
print('MMCV:', mmcv.__version__)
print('✅ All systems operational')
"
```

## Docker Considerations

When containerizing:
1. Use `nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04` base image
2. Install Python 3.10 specifically
3. Use mim for MMLab packages
4. Apply version downgrades after main installations
5. Run weights download as part of build or mount as volume

## Lessons Learned

1. **Always follow README exactly** - Version specifications are critical
2. **Use official package managers** - mim for MMLab, not pip
3. **Check CUDA compatibility** - Not all CUDA versions have pre-built wheels
4. **Version pinning is crucial** - Auto-upgrades break compatibility
5. **uv >> pip** - Significantly faster and more reliable

This solution provides a reproducible setup that successfully runs MuseTalk inference with CUDA acceleration.