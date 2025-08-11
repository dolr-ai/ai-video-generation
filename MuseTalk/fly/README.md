# MuseTalk FastAPI Server - Fly.io Deployment

This directory contains all necessary files to deploy the MuseTalk FastAPI server on Fly.io with GPU support.

## Prerequisites

1. **Fly.io Account**: Sign up at [fly.io](https://fly.io)
2. **Fly CLI**: Will be installed automatically by deploy script
3. **API Token**: Set in `.env` file or environment variable `FLY_API_TOKEN`

## Files Overview

- `Dockerfile` - Optimized Docker image for Fly.io GPU deployment
- `fly.toml` - Fly.io application configuration with GPU settings
- `start-servers.sh` - Bash script to start both FastAPI servers
- `download_models.sh` - Script to download model weights
- `deploy.sh` - Main deployment script
- `scale.sh` - Scale machines up/down
- `monitor.sh` - Monitor application health and logs
- `test-api.sh` - Test the deployed API

## Quick Deployment

### Option 1: Manual Deployment

1. **Set API Token**:
   ```bash
   # The token is already in /workspace/ai-video-generation/MuseTalk/.env
   # Or export directly:
   export FLY_API_TOKEN="your-token-here"
   ```

2. **Deploy Application**:
   ```bash
   cd /workspace/ai-video-generation/MuseTalk
   chmod +x fly/*.sh
   ./fly/deploy.sh
   ```

3. **Test Deployment**:
   ```bash
   ./fly/test-api.sh
   ```

### Option 2: GitHub Actions (Recommended)

For automated deployments using GitHub Actions:

1. **Set Repository Secret**:
   - Go to your GitHub repository settings
   - Navigate to Secrets and Variables > Actions
   - Add `FLY_API_TOKEN` secret with your Fly.io API token

2. **Automatic Deployment**:
   - **Production**: Push to `main` or `master` branch
   - **Staging**: Push to `develop` or `staging` branch
   - **Manual**: Use "Run workflow" button in GitHub Actions tab

3. **Workflow Features**:
   - ✅ Automatic app creation if doesn't exist
   - ✅ Persistent volume setup (models + storage)
   - ✅ Health checks after deployment
   - ✅ Staging environment support
   - ✅ Manual deployment triggers

## GPU Configuration

The deployment uses NVIDIA A100 40GB GPU by default. Available options:
- `a100-40gb` - NVIDIA A100 40GB (recommended for production)
- `a100-80gb` - NVIDIA A100 80GB (for larger models)
- `l40s` - NVIDIA L40S (cost-effective alternative)

To change GPU type:
```bash
./fly/scale.sh gpu l40s
```

## Architecture

The deployment runs both FastAPI servers on a single GPU-enabled machine:
1. **Model Server (localhost:8001)** - Handles model loading and inference (internal only)
2. **Handler Server (0.0.0.0:8000)** - Manages API requests and responses (publicly exposed)

Both servers are started by a simple bash script that handles process management, health checks, and graceful shutdown. They communicate via localhost for optimal performance.

## Persistent Storage

Two volumes are automatically created:
- `musetalk_models` (100GB) - Stores model weights
- `musetalk_storage` (50GB) - Stores generated videos

## Management Commands

### Deploy/Update
```bash
./fly/deploy.sh
```

### Scale Machines
```bash
# Scale to 2 machines
./fly/scale.sh up 2

# Scale down to 1 machine
./fly/scale.sh down 1

# Check current scale
./fly/scale.sh status
```

### Monitor Application
```bash
# Check health
./fly/monitor.sh health

# View logs
./fly/monitor.sh logs

# SSH into machine
./fly/monitor.sh ssh

# View metrics dashboard
./fly/monitor.sh metrics
```

### Test API
```bash
# Test with default samples
./fly/test-api.sh

# Test with custom URL
./fly/test-api.sh https://musetalk-api.fly.dev
```

## API Endpoints

Once deployed, your API will be available at:
- Base URL: `https://musetalk-api.fly.dev`
- Health: `https://musetalk-api.fly.dev/api/v1/health`
- Generate: `POST https://musetalk-api.fly.dev/api/v1/generate`
- Status: `GET https://musetalk-api.fly.dev/api/v1/status/{task_id}`
- Download: `GET https://musetalk-api.fly.dev/api/v1/video/{task_id}`

## Cost Considerations

- GPU machines on Fly.io are billed per second of usage
- Use `auto_stop_machines = true` in fly.toml to save costs during idle time
- Monitor usage with `flyctl dashboard` command

## Troubleshooting

1. **Deployment Fails**:
   - Check GPU availability in your region
   - Verify FLY_API_TOKEN is correct
   - Review logs: `flyctl logs --app musetalk-api`

2. **Model Loading Issues**:
   - SSH into machine: `./fly/monitor.sh ssh`
   - Check model directory: `ls -la /workspace/ai-video-generation/MuseTalk/models/`
   - Manually trigger download: `/download_models.sh`

3. **Out of Memory**:
   - Reduce batch_size in API requests
   - Scale to larger GPU: `./fly/scale.sh gpu a100-80gb`

4. **API Not Responding**:
   - Check health: `./fly/monitor.sh health`
   - Restart machine: `flyctl apps restart musetalk-api`

## Security Notes

- The API Token is sensitive - keep it secure
- Consider adding authentication to your API endpoints
- Use HTTPS for all production traffic (enabled by default)

## Support

For issues specific to:
- MuseTalk: Check `/workspace/ai-video-generation/MuseTalk/fastapi_server/README.md`
- Fly.io: Visit [fly.io/docs](https://fly.io/docs)
- GPU support: See [fly.io/docs/gpus](https://fly.io/docs/gpus)