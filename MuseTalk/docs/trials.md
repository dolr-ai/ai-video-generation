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

## Root Issues Identified:
1. mmcv requires compilation of CUDA extensions even for CPU-only usage
2. Version compatibility between mmcv, mmpose, mmdet, and mmengine is strict
3. The README suggests specific versions that should be used with mim
4. Need to follow README installation steps exactly rather than using pip/uv directly for mm* packages