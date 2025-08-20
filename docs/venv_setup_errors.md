# MuseTalk Virtual Environment Setup - Errors and Solutions

## Error 1: NumPy Version Incompatibility (CRITICAL ERROR)

### When It Occurred
After Step 6 (Installing MMLab packages with mim), when attempting first import test in Step 7.

### Exact Error Message
```
A module that was compiled using NumPy 1.x cannot be run in
NumPy 2.2.6 as it may crash. To support both 1.x and 2.x
versions of NumPy, modules must be compiled with NumPy 2.0.
Some module may need to rebuild instead e.g. with 'pybind11>=2.12'.

AttributeError: _ARRAY_API not found
ImportError: numpy.core.multiarray failed to import
```

### Sequence of Events Leading to Error
1. Step 4: PyTorch installation initially installed numpy==2.1.2
2. Step 5: requirements.txt installation downgraded to numpy==1.23.5 (correct version)
3. Step 6: `uv pip install --no-cache-dir -U openmim` UPGRADED numpy to 2.2.6 (causing the issue)
4. Step 7: Import test failed with NumPy incompatibility error

### Root Cause Analysis
- OpenCV-Python 4.9.0.80 was compiled against NumPy 1.x
- openmim installation force-upgraded NumPy to 2.2.6
- The `-U` flag in the openmim installation command caused aggressive dependency upgrades
- MMCV and other vision packages couldn't work with NumPy 2.x

### Solution Applied
```bash
# Step 8: Force downgrade to the correct NumPy version
uv pip install "numpy==1.23.5" --force-reinstall
```

### Why This Solution Worked
- `--force-reinstall` ensures complete replacement of NumPy 2.2.6
- Version 1.23.5 is compatible with all installed packages
- This version matches what's specified in requirements.txt

### Prevention for Future Setups
1. Install openmim WITHOUT the `-U` flag: `uv pip install openmim`
2. Or, install NumPy 1.23.5 again AFTER installing all MMLab packages
3. Consider pinning NumPy version in a constraints file

## Error 2: CUDA Version Mismatch when Building MMCV (CRITICAL ERROR)

### When It Occurred
Step 6: When attempting to install MMCV 2.0.1 using `mim install "mmcv==2.0.1"`

### Exact Error Message
```
RuntimeError:
The detected CUDA version (12.8) mismatches the version that was used to compile
PyTorch (11.8). Please make sure to use the same CUDA versions.

ERROR: Failed building wheel for mmcv
error: failed-wheel-build-for-install
```

### Root Cause Analysis
- System has CUDA 12.8 installed
- PyTorch was installed with CUDA 11.8 support (`torch==2.0.1+cu118`)
- `mim install` attempted to build MMCV from source
- Building from source requires matching CUDA versions between system and PyTorch
- SSL certificate issues with download.openmmlab.com prevented accessing prebuilt wheels

### Solution Applied
```bash
# Use pip directly with the prebuilt wheel URL
pip install mmcv==2.0.1 -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.0.0/index.html --trusted-host download.openmmlab.com
```

### Why This Solution Worked
- Directly accessed the prebuilt wheel for CUDA 11.8 and PyTorch 2.0
- `--trusted-host` bypassed SSL certificate verification issues
- Prebuilt wheel avoided the need to compile from source
- Downloaded correct wheel: `mmcv-2.0.1-cp310-cp310-manylinux1_x86_64.whl`

### Prevention for Future Setups
1. Always use prebuilt wheels when CUDA versions don't match
2. Check PyTorch CUDA version: `python -c "import torch; print(torch.version.cuda)"`
3. Use the correct wheel index URL for your PyTorch/CUDA combination
4. For CUDA 11.8 + PyTorch 2.0: `https://download.openmmlab.com/mmcv/dist/cu118/torch2.0.0/index.html`

## Error 3: Virtual Environment Path Issue (Non-Critical)

### When It Occurred
Step 10: When running the download_weights_with_venv.sh script

### Exact Error Message
```
download_weights_with_venv.sh: line 4: .venv/bin/activate: No such file or directory
```

### What Happened
- The script tried to activate `.venv/bin/activate` (expecting venv in current directory)
- Our venv was actually at `../.venv/bin/activate` (in parent directory)
- Script line 4 failed but execution continued

### Why It Still Worked
1. We had already activated the venv before running the script: `source ../.venv/bin/activate`
2. The script's subsequent commands (hf download, gdown, etc.) ran in the already-activated environment
3. All model weights were successfully downloaded despite the initial error

### Root Cause
- Script assumes standard venv location: `./MuseTalk/.venv/`
- We created venv in parent directory: `./ai-video-generation/.venv/`
- Script's hardcoded path on line 4: `source .venv/bin/activate`

### Solution Applied
```bash
# Pre-activate the venv before running the script
source ../.venv/bin/activate && bash download_weights_with_venv.sh
```

### Alternative Solutions
1. Modify the script to use correct path
2. Create venv in expected location
3. Use absolute path in script

## Timeline Summary of Errors

| Step | Action | Result | Error? |
|------|--------|--------|--------|
| 1-3 | Create & activate venv | ✅ Success | No |
| 4 | Install PyTorch | ✅ Success (numpy 2.1.2) | No |
| 5 | Install requirements.txt | ✅ Success (numpy 1.23.5) | No |
| 6a | Install openmim | ✅ Success (without -U flag) | No |
| 6b | Install mmengine with mim | ✅ Success | No |
| 6c | Install mmcv with mim | ❌ CUDA mismatch error | **ERROR 2** |
| 6d | Install mmcv with pip + wheel URL | ✅ Fixed | No |
| 6e | Install mmdet & mmpose | ✅ Success | No |
| 7 | Check NumPy version | ✅ Still 1.23.5 | No |
| 8 | Verify imports | ✅ Success | No |
| 9 | Download weights | ⚠️ Path error but succeeded | **ERROR 3** |
| 10 | Test inference | ✅ Success | No |

## Key Learnings

1. **NumPy Version Management**:
   - Always pin NumPy version when working with compiled packages like OpenCV
   - The `-U` flag in pip install can cause unwanted upgrades
   - MMLab packages may have different NumPy requirements than your project

2. **Path Flexibility**:
   - Be aware of relative paths in scripts
   - Pre-activating venv can work around path issues
   - Consider using absolute paths or environment variables

3. **uv Advantages**:
   - Using uv made dependency resolution and installation significantly faster
   - uv handles dependency conflicts better than regular pip
   - Installation with uv was ~3-5x faster than pip

4. **MMLab Installation Order**:
   - Install base packages (mmengine) before specialized ones (mmcv, mmdet, mmpose)
   - Use mim for MMLab packages for proper CUDA compatibility
   - Watch for dependency upgrades when using mim

## Troubleshooting Tips

1. **Check NumPy compatibility first** when encountering import errors with vision packages
2. **Use `--force-reinstall`** when downgrading packages to ensure proper replacement
3. **Verify CUDA availability** after PyTorch installation to ensure GPU support
4. **Check CUDA version compatibility** between system and PyTorch before building packages from source
5. **Use prebuilt wheels** for MMLab packages when possible to avoid compilation issues
6. **Test imports incrementally** after installing each major package group
7. **Always activate venv before running scripts** that expect venv activation
8. **Read error messages carefully** - sometimes non-critical errors don't stop execution
9. **Use `--trusted-host` flag** when SSL certificate errors occur with package repositories