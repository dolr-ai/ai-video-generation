# Failed Attempts Documentation

## Attempt 1: Basic pip installation
- Created venv with `just_uv.sh --py3.10`
- Installed requirements.txt with `uv pip install -r requirements.txt`
- Issue: Missing torchvision
- Fixed with: `uv pip install torchvision`

## Attempt 2: mmpose installation issues
- Tried: `uv pip install mmpose`
- Error: Failed to build chumpy dependency
- Tried: `uv pip install mmpose --no-deps`
- Then installed mmcv, mmengine separately

## Attempt 3: Version conflicts
- mmengine 0.10.5 had conflicts with transformers (Adafactor optimizer registration)
- Tried downgrading to mmengine==0.8.5, mmpose==1.2.0
- Still had mmcv._ext import errors

## Attempt 4: Using mim
- Installed openmim: `uv pip install openmim`
- Used `python -m mim install` for packages
- Issue: mmcv compilation failed when trying to build from source
- mmcv-full build timed out after 5 minutes

## Attempt 5: Pre-built packages
- Tried various mmcv versions (2.0.1, 2.1.0)
- Consistent issue: ModuleNotFoundError: No module named 'mmcv._ext'
- This suggests CUDA ops compilation issues

## Attempt 6: August 7, 2025 - PyTorch/CUDA Compatibility Issues

### Initial Issues
- **Problem**: `module 'torch' has no attribute 'uint64'`
- **Cause**: PyTorch 2.0.1 doesn't support uint64 attribute needed by newer safetensors
- **Solution**: Upgraded PyTorch to 2.8.0 with `uv pip install --upgrade "torch>=2.1.0" "torchvision" "torchaudio"`

### NumPy Compatibility
- **Problem**: NumPy 2.x incompatible with OpenCV (compiled with NumPy 1.x)
- **Error**: `A module that was compiled using NumPy 1.x cannot be run in NumPy 2.2.6`
- **Solution**: Downgraded NumPy to 1.x: `uv pip install "numpy<2"`

### MMCV CUDA Extensions Hell
- **Problem**: `ModuleNotFoundError: No module named 'mmcv._ext'`
- **Root Cause**: mmcv-lite doesn't include CUDA extensions, but mmdet requires them

#### Failed Attempts:
1. **mmcv-lite**: No CUDA extensions, mmdet fails
2. **mmcv from OpenMMLab index**: 404 errors for CUDA 12.8/PyTorch 2.8 combination
3. **Building from source with pip**: Compilation errors, C++ template failures
4. **Using mim**: Still tries to build from source, same compilation failures
5. **Setting CUDA_HOME and compile flags**: Still fails due to C++ compatibility issues

#### Why it's failing:
- CUDA 12.8 + PyTorch 2.8 + mmcv 2.0.1 combination has no pre-built wheels
- Source compilation fails due to C++ template compatibility issues with newer CUDA/PyTorch
- mmcv compilation requires specific compiler versions and CUDA toolkit setup

### Current Status
- ✅ Core MuseTalk models (VAE, UNet) work perfectly
- ✅ PyTorch CUDA available and working
- ❌ Face preprocessing blocked by mmcv/mmpose dependency

## Root Issues Identified:
1. mmcv requires compilation of CUDA extensions even for CPU-only usage
2. Version compatibility between mmcv, mmpose, mmdet, and mmengine is strict
3. No pre-built mmcv wheels for newer PyTorch/CUDA combinations
4. C++ compilation issues with newer toolchains
5. The dependency chain is: inference → preprocessing → mmpose → mmdet → mmcv (with CUDA ops)