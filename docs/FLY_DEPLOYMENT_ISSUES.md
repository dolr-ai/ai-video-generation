# Fly.io Deployment Issues and Solutions

## Overview
This document covers the issues encountered while deploying MuseTalk to Fly.io with GPU instances and persistent volumes.

**Last Updated:** 2025-08-18

## Major Issues Encountered

### 1. Volume Mount Limitation
**Error:**
```
Failed to update machines: failed to update machine 3d8d7e96f75398: failed to launch VM: invalid config.mounts, only 1 volume supported
panic: runtime error: invalid memory address or nil pointer dereference
```

**Cause:** Fly.io only supports 1 volume per machine, but our configuration had 2 volumes.

**Solution:** 
- Removed the second volume (`musetalk_storage`) from fly.toml
- Only kept the `musetalk_models` volume for model storage

**Files Modified:**
- `fly.toml`: Removed second mount point
- `deploy.sh`: Removed storage volume creation
- GitHub workflow: Removed storage volume creation step

---

### 2. Insufficient Resources with GPU Volume
**Error:**
```
Failed: error creating a new machine: failed to launch VM: insufficient resources to create new machine with existing volume 'vol_40lkd6m1j7nj3yk4'
Error: failed to launch VM: insufficient resources to create new machine with existing volume 'vol_40lkd6m1j7nj3yk4' (Request ID: 01K2ZBSJ047JWHHH1CV91QN40G-ord)
```

**Cause:** 
- Volume was created in a zone that doesn't have available GPU resources
- Fly.io cannot move volumes between zones
- L40S GPUs have limited availability in certain zones within the ord region

**Attempted Solutions:**
1. ✅ Created volume with GPU constraints: `--vm-gpu-kind l40s`
2. ❌ Tried to deploy with existing volume in wrong zone
3. ❌ Attempted to scale machines with stuck volume

**Working Solution:**
```bash
# Delete the stuck volume
flyctl volumes destroy vol_40lkd6m1j7nj3yk4 --app talking-head-api

# Recreate with GPU constraint (will be placed in available zone)
flyctl volumes create musetalk_models --size 100 --region ord --vm-gpu-kind l40s --app talking-head-api

# Deploy
flyctl deploy --config fly/fly.toml --dockerfile fly/Dockerfile --app talking-head-api
```

---

### 3. No Running VMs for SSH/SFTP Operations
**Error:**
```
Error: app talking-head-api has no started VMs.
It may be unhealthy or not have been deployed yet.
tar: -: Cannot write: Broken pipe
```

**Cause:** Cannot SSH into an app without running machines, even if the app and volume exist.

**Solution:**
```bash
# Ensure at least one machine is running
flyctl scale count 1 --app talking-head-api
sleep 10

# Then upload models
tar -czf - models | flyctl ssh console --app talking-head-api -C "cd /workspace/ai-video-generation/MuseTalk && tar -xzf -"
```

---

### 4. Model Download During Build vs Runtime
**Issue:** Models were being downloaded during Docker build, making the image 6.5GB+ and not utilizing persistent volumes.

**Solution:**
- Removed model download from Dockerfile
- Models are now downloaded from GCS in GitHub Actions
- Uploaded to persistent volume after deployment
- Volume persists across deployments

---

### 5. Configuration Redundancy
**Issue:** Configuration was scattered across multiple files with redundancy between fly.toml and GitHub workflow.

**Solution:**
- Centralized all deployment parameters in GitHub workflow environment variables
- Removed app name and region from fly.toml (specified via command line)
- fly.toml now only contains runtime configuration that cannot be specified via CLI

**Files Modified:**
- `fly.toml`: Stripped to minimal runtime config
- GitHub workflow: All parameters as variables at top
- Removed unnecessary scripts from fly/ directory

---

### 6. Dockerfile Path Resolution
**Issue:** 
```
Error: failed to fetch an image or build from source: dockerfile '/home/runner/work/ai-video-generation/ai-video-generation/MuseTalk/fly/fly/Dockerfile' not found
```

**Cause:** Path resolution issue when dockerfile path in fly.toml is relative to working directory.

**Solution:**
- Removed build section from fly.toml
- Specify dockerfile path explicitly in deploy command: `--dockerfile fly/Dockerfile`

---

### 7. Non-Interactive Volume Creation
**Issue:**
```
Error: yes flag must be specified when not running interactively
```

**Cause:** flyctl volumes create requires confirmation in CI/CD environments.

**Solution:**
- Added `--yes` flag to volume creation command in GitHub workflow

---

### 8. Machine Lease Already Held
**Error:**
```
Failed to acquire lease for 908064e9aded78: Unrecoverable error: failed to get lease on VM 908064e9aded78: 
machine ID 908064e9aded78 lease currently held by 08d8d99f-a5ad-5b62-8192-e63efb4698c9@tokens.fly.io, 
expires at 2025-08-18T20:31:24Z
```

**Cause:** 
- Another deployment process or operation is holding a lease on the machine
- Can happen when multiple deployments run simultaneously or previous deployment didn't release the lease properly

**Solution:**
- Wait for the lease to expire (check the expiry time in error message)
- Or destroy the machine and redeploy:
```bash
flyctl machines destroy 908064e9aded78 --app talking-head-api --force
flyctl deploy --config fly/fly.toml --dockerfile fly/Dockerfile --app talking-head-api
```

**Prevention:**
- Ensure only one deployment runs at a time
- Add proper timeouts in CI/CD pipeline
- Use `--lease-timeout` flag to adjust lease duration if needed

---

## Current Working Workflow

### Configuration Structure
```yaml
# GitHub Workflow (.github/workflows/deploy-fly.yml)
env:
  APP_NAME: talking-head-api
  ORG_NAME: yral-ds  
  REGION: ord
  VOLUME_NAME: musetalk_models
  VOLUME_SIZE: 100
  GPU_TYPE: a10  # Must match fly.toml [[vm]] size
  FLY_TOML_PATH: fly/fly.toml
  DOCKERFILE_PATH: fly/Dockerfile
```

```toml
# fly.toml (MuseTalk/fly/fly.toml) - Minimal runtime config only
[env]
  PYTHONUNBUFFERED = "1"
  NVIDIA_VISIBLE_DEVICES = "all"
  NVIDIA_DRIVER_CAPABILITIES = "compute,utility"

[[services]]
  internal_port = 8000
  protocol = "tcp"
  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

[[vm]]
  size = "a10"  # Must match workflow GPU_TYPE
  memory = "16gb"
  cpus = 4

[[mounts]]
  source = "musetalk_models"
  destination = "/workspace/ai-video-generation/MuseTalk/models"
```

### Deployment Steps
1. **Download models from GCS** (in GitHub runner)
2. **Create app if not exists**
3. **Create volume with GPU constraints if not exists**
4. **Deploy application** (creates machine)
5. **Upload models to volume** via tar pipe over SSH
6. **Run health checks**

### Key Commands

#### Create GPU-enabled volume:
```bash
flyctl volumes create musetalk_models \
  --size 100 \
  --region ord \
  --vm-gpu-kind a10 \
  --app talking-head-api \
  --yes
```

#### Deploy with specific Dockerfile:
```bash
flyctl deploy \
  --config fly/fly.toml \
  --dockerfile fly/Dockerfile \
  --app talking-head-api \
  --region ord \
  --ha=false \
  --wait-timeout 1800
```

#### Upload models to volume:
```bash
tar -czf - models | flyctl ssh console --app talking-head-api -C \
  "cd /workspace/ai-video-generation/MuseTalk && tar -xzf -"
```

---

## Important Notes

### GPU Availability
- L40S GPUs are only available in `ord` region
- A10 GPUs are also available in `ord` region (better availability than L40S)
- Within ord, not all zones have GPU availability
- Volumes must be created with `--vm-gpu-kind` flag to ensure proper placement
- If deployment fails with "insufficient resources", delete and recreate volume

### Volume Constraints
- Only 1 volume per machine supported
- Volumes cannot be moved between zones
- Stuck volumes must be deleted and recreated

### SSH/SFTP Limitations
- Requires running machine for SSH access
- SFTP has limited directory upload support
- tar pipe method is most reliable for directory uploads

### Docker Image Size
- Avoid downloading models during build
- Use persistent volumes for large files
- Keep base image under 2GB for faster deployments

---

## Troubleshooting

### Check app status:
```bash
flyctl status --app talking-head-api
flyctl machines list --app talking-head-api
```

### Check volume status:
```bash
flyctl volumes list --app talking-head-api
```

### View logs:
```bash
flyctl logs --app talking-head-api
```

### SSH into running machine:
```bash
flyctl ssh console --app talking-head-api
```

### Destroy stuck resources:
```bash
# Destroy specific volume
flyctl volumes destroy <volume-id> --app talking-head-api

# Destroy all machines
flyctl machines destroy --force --app talking-head-api

# Destroy entire app
flyctl apps destroy talking-head-api
```

---

## References
- [Fly.io GPU Documentation](https://fly.io/docs/gpus/)
- [Fly.io Volumes Documentation](https://fly.io/docs/volumes/)
- [Community Discussion: Insufficient Resources](https://community.fly.io/t/insufficient-resources-to-create-new-machine-with-existing-volume/21378)