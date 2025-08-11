# GitHub Actions Deployment Guide

This guide explains how to set up automated deployment of MuseTalk to Fly.io using GitHub Actions.

## Setup Steps

### 1. Get Fly.io API Token

1. Log in to [Fly.io Dashboard](https://fly.io/dashboard)
2. Go to Account Settings > Access Tokens
3. Create a new token with deployment permissions
4. Copy the token (starts with `FlyV1`)

### 2. Add GitHub Repository Secret

1. Go to your GitHub repository
2. Click **Settings** tab
3. Navigate to **Secrets and Variables** > **Actions**
4. Click **New repository secret**
5. Name: `FLY_API_TOKEN`
6. Value: Your Fly.io API token
7. Click **Add secret**

### 3. Deployment Workflows

Two workflows are available:

#### Production Deployment (`deploy.yml`)
- **Triggers**: 
  - Push to `main` or `master` branch
  - Manual trigger via GitHub Actions tab
- **App**: `musetalk-api`
- **Volumes**: 100GB (models) + 50GB (storage)

#### Staging Deployment (`deploy-staging.yml`)
- **Triggers**:
  - Push to `develop` or `staging` branch
  - Manual trigger via GitHub Actions tab
- **App**: `musetalk-api-staging`
- **Volumes**: 50GB (models) + 25GB (storage)

### 4. First Deployment

1. **Push to main branch**:
   ```bash
   git add .
   git commit -m "Deploy MuseTalk to Fly.io"
   git push origin main
   ```

2. **Or trigger manually**:
   - Go to **Actions** tab in GitHub
   - Click **Deploy MuseTalk to Fly.io**
   - Click **Run workflow**
   - Select branch and click **Run workflow**

### 5. Monitor Deployment

1. **GitHub Actions**: Watch the workflow progress in the Actions tab
2. **Fly.io Logs**: Check logs with `flyctl logs --app musetalk-api`
3. **Health Check**: The workflow automatically tests the deployed API

## Workflow Features

### Automatic Setup
- ✅ Creates Fly.io app if it doesn't exist
- ✅ Sets up persistent volumes automatically
- ✅ Handles authentication with your API token

### Deployment Process
- ✅ Builds Docker image with all dependencies
- ✅ Downloads models to persistent volume (first time only)
- ✅ Deploys to A10 GPU machine with 16GB RAM
- ✅ Performs health checks after deployment

### Error Handling
- ✅ Retries health checks up to 5 times
- ✅ Provides detailed error messages
- ✅ Shows deployment status and URLs

## Troubleshooting

### Common Issues

1. **Secret not found**:
   - Verify `FLY_API_TOKEN` is set in repository secrets
   - Check the token is valid and has deployment permissions

2. **App creation fails**:
   - Ensure your Fly.io account has sufficient credits
   - Check if app name is already taken

3. **Volume creation fails**:
   - Verify region availability (default: `ord`)
   - Check account limits for volume storage

4. **Health check fails**:
   - First deployment takes 5-10 minutes (model download)
   - Check logs: `flyctl logs --app musetalk-api`
   - Verify GPU availability in region

### Manual Commands

If deployment fails, you can run manual commands:

```bash
# Check app status
flyctl status --app musetalk-api

# View logs
flyctl logs --app musetalk-api

# SSH into machine
flyctl ssh console --app musetalk-api

# Restart deployment
flyctl deploy --config fly/fly.toml --app musetalk-api
```

## Cost Optimization

- **Auto-stop**: Set to `false` for production (models stay loaded)
- **Staging**: Smaller volumes and can use auto-stop
- **Monitoring**: Use `flyctl dashboard` to track usage

## Security

- ✅ API token stored as encrypted GitHub secret
- ✅ HTTPS enabled by default
- ✅ No secrets exposed in workflow logs
- ✅ Minimal permissions required