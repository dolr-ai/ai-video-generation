# RunPod Serverless Deployment Guide

## Prerequisites

1. **RunPod Account**: Sign up at [RunPod.io](https://www.runpod.io)
2. **RunPod API Key**: Get from [RunPod Settings](https://www.runpod.io/console/user/settings)
3. **Google Cloud Service Account**: With access to GCS bucket containing models
4. **GitHub Repository Secrets**: Configure the following secrets

## Required GitHub Secrets

Add these secrets to your repository at `Settings > Secrets and variables > Actions`:

### 1. RUNPOD_API_KEY
- **Description**: Your RunPod API key for authentication
- **How to get**: 
  1. Go to [RunPod Settings](https://www.runpod.io/console/user/settings)
  2. Navigate to API Keys section
  3. Create a new API key or use existing one
  4. Copy the key (starts with `RP_`)

### 2. GCP_CREDENTIALS
- **Description**: Google Cloud service account JSON key
- **How to get**:
  1. Go to [GCP Console](https://console.cloud.google.com)
  2. Navigate to IAM & Admin > Service Accounts
  3. Create or select a service account
  4. Create a new JSON key
  5. Copy the entire JSON content
- **Required permissions**:
  - `storage.objects.get` (to download models from GCS)
  - Access to your GCS bucket

### 3. GCS_BUCKET (Optional)
- **Description**: Name of your GCS bucket containing models
- **Default**: `talking-head-models`
- **Example**: `my-company-models`

## Deployment Workflow

### Automatic Deployment
The deployment automatically triggers when:
1. The Docker image build workflow completes successfully on the `main` branch
2. New image is pushed to Google Artifact Registry

### Manual Deployment
You can also manually trigger deployment:

1. Go to Actions tab in your GitHub repository
2. Select "Deploy to RunPod Serverless" workflow
3. Click "Run workflow"
4. Select environment: `production`, `staging`, or `development`
5. Click "Run workflow" button

## Deployment Environments

### Production
- **Endpoint name**: `musetalk-api-production`
- **Auto-deploy**: Yes (on main branch)
- **GPU**: NVIDIA RTX A4000
- **Workers**: 0-3 (auto-scaling)

### Staging
- **Endpoint name**: `musetalk-api-staging`
- **Auto-deploy**: No (manual only)
- **GPU**: NVIDIA RTX A4000
- **Workers**: 0-2 (auto-scaling)

### Development
- **Endpoint name**: `musetalk-api-development`
- **Auto-deploy**: No (manual only)
- **GPU**: NVIDIA RTX A4000
- **Workers**: 0-1 (minimal scaling)

## API Usage

### Submit a Job

```bash
# Set your RunPod API key
export RUNPOD_API_KEY="RP_xxxxxxxxxxxxx"

# Set your endpoint ID (get from deployment output)
export ENDPOINT_ID="xxxxxxxxxx"

# Submit a video generation job
curl -X POST "https://api.runpod.ai/v2/${ENDPOINT_ID}/run" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "image": "https://example.com/image.jpg",
      "audio": "https://example.com/audio.mp3",
      "bbox_shift": 5
    }
  }'
```

### Check Job Status

```bash
# Get job ID from submission response
export JOB_ID="xxxxxxxxxxxxx"

# Check status
curl -X GET "https://api.runpod.ai/v2/${ENDPOINT_ID}/status/${JOB_ID}" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

### Get Job Result

```bash
curl -X GET "https://api.runpod.ai/v2/${ENDPOINT_ID}/status/${JOB_ID}" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

## Input Format

### Using Base64 Encoding

```json
{
  "input": {
    "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "audio": "data:audio/mpeg;base64,SUQzBAAAAAAAI1RTU0...",
    "bbox_shift": 5
  }
}
```

### Using URLs

```json
{
  "input": {
    "image": "https://example.com/portrait.jpg",
    "audio": "https://example.com/speech.mp3",
    "bbox_shift": 5
  }
}
```

## Output Format

### Success Response

```json
{
  "status": "completed",
  "video": "base64_encoded_video_data",
  "task_id": "unique_task_identifier",
  "generation_time": 45
}
```

### Error Response

```json
{
  "status": "failed",
  "error": "Error description"
}
```

## Monitoring

### RunPod Dashboard
- **Console**: https://www.runpod.io/console/serverless
- **Metrics**: Available for each endpoint
- **Logs**: Real-time logs for debugging

### GitHub Actions
- Check workflow runs in Actions tab
- Download deployment artifacts for details
- Review deployment summaries

## Cost Optimization

### Tips to Reduce Costs
1. **Set minWorkers to 0**: Only pay when processing
2. **Adjust maxWorkers**: Based on expected load
3. **Optimize worker timeout**: Balance between cold starts and idle time
4. **Use appropriate GPU**: A4000 is cost-effective for this workload

### Estimated Costs
- **Idle**: $0 (with minWorkers=0)
- **Active**: ~$0.00024/second on A4000
- **Cold start**: ~2-3 minutes (model download)
- **Warm start**: ~10-30 seconds

## Troubleshooting

### Common Issues

#### 1. Deployment Fails
- Check GitHub Actions logs
- Verify all secrets are set correctly
- Ensure Docker image exists in GAR

#### 2. Endpoint Not Responding
- Check RunPod dashboard for errors
- Verify models are downloading correctly
- Check GPU availability in your region

#### 3. Slow Cold Starts
- Models need to download from GCS (~10GB)
- Consider keeping 1 min worker during peak hours
- Pre-warm endpoint before high traffic

#### 4. Out of Memory Errors
- Ensure using GPU with ≥16GB VRAM
- Check if models are loading correctly
- Monitor memory usage in RunPod dashboard

### Debug Commands

```bash
# List all endpoints
curl -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  https://api.runpod.io/graphql \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"{ serverlessEndpoints { id name status } }"}'

# Get endpoint details
curl -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  https://api.runpod.io/graphql \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"{ serverlessEndpoint(id: \"ENDPOINT_ID\") { id name status workers { ready running } } }"}'

# Get endpoint logs
curl -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  "https://api.runpod.ai/v2/${ENDPOINT_ID}/logs"
```

## Support

- **RunPod Documentation**: https://docs.runpod.io
- **RunPod Discord**: https://discord.gg/runpod
- **GitHub Issues**: Report deployment issues in your repository