# MuseTalk FastAPI Server Architecture

## Overview

This document provides comprehensive technical documentation for the MuseTalk FastAPI server implementation, including system architecture, data flows, and design decisions based on the proven Flask service patterns.

## 🏗️ System Architecture

### Two-Server Design

The FastAPI implementation uses a **distributed two-server architecture** for optimal scalability and resource management:

```mermaid
graph TB
    subgraph "Client Layer"
        CLI[CLI Client]
        WEB[Web Client]
        API[API Client]
    end
    
    subgraph "FastAPI Handler Server (Port 8000)"
        HR[HTTP Router]
        EP[API Endpoints]
        TM[Task Manager]
        BG[Background Tasks]
        FL[File Handler]
    end
    
    subgraph "Model Server (Port 8001)"
        MS[Model Service]
        MM[MuseTalk Model]
        GPU[GPU Processing]
    end
    
    subgraph "Storage Layer"
        TEMP[Temp Storage]
        VIDEOS[Video Storage]
        LOGS[Log Files]
    end
    
    CLI --> HR
    WEB --> HR
    API --> HR
    
    HR --> EP
    EP --> TM
    EP --> BG
    EP --> FL
    
    BG --> MS
    MS --> MM
    MM --> GPU
    
    TM --> TEMP
    FL --> VIDEOS
    MS --> LOGS
```

### Component Breakdown

#### Handler Server (Port 8000)
- **Purpose**: API request handling, task management, file operations
- **Technology**: FastAPI with async support
- **Responsibilities**:
  - Accept and validate requests
  - Manage task lifecycle and status
  - Handle file uploads/downloads
  - Communicate with model server
  - Background task processing

#### Model Server (Port 8001)  
- **Purpose**: MuseTalk model hosting and inference
- **Technology**: FastAPI with synchronous model processing
- **Responsibilities**:
  - Load and manage MuseTalk models
  - Process video generation requests
  - Handle GPU memory management
  - Execute inference pipeline

## 🔄 Request Flow Diagram

```mermaid
sequenceDiagram
    participant C as Client
    participant H as Handler Server
    participant M as Model Server
    participant S as Storage
    
    Note over C,S: Video Generation Request Flow
    
    C->>H: POST /api/v1/generate
    H->>H: Validate request
    H->>H: Create task ID
    H->>S: Store task metadata
    H->>C: Return task_id (202 Accepted)
    
    Note over H,M: Background Processing
    
    H->>H: Start background task
    H->>S: Update status: processing
    H->>M: POST /generate (with files)
    
    Note over M: Model Inference
    
    M->>M: Load models (if not loaded)
    M->>M: Change to MuseTalk directory
    M->>M: Process image/audio
    M->>M: Generate video
    M->>M: Restore working directory
    M->>H: Return result
    
    H->>S: Store video file
    H->>S: Update status: completed
    
    Note over C,S: Status Check & Download
    
    C->>H: GET /api/v1/status/{task_id}
    H->>S: Get task status
    H->>C: Return status info
    
    C->>H: GET /api/v1/video/{task_id}
    H->>S: Get video file
    H->>C: Stream video file
```

## 📁 Directory Structure

```
fastapi_server/
├── 📄 README.md                    # Main documentation
├── 📄 ARCHITECTURE.md              # This file
├── 📄 requirements.txt             # Python dependencies
├── 📄 model_server.py              # Model server entry point
├── 📄 handler_server.py            # Handler server entry point
├── 🔧 start_model_server.sh        # Model server startup script
├── 🔧 start_handler_server.sh      # Handler server startup script
├── 
├── 📁 api/                         # API layer
│   ├── __init__.py
│   └── endpoints.py                # FastAPI route handlers
├── 
├── 📁 config/                      # Configuration
│   ├── __init__.py
│   └── settings.py                 # Centralized configuration
├── 
├── 📁 core/                        # Business logic
│   ├── __init__.py
│   ├── musetalk_model.py          # MuseTalk model wrapper
│   └── task_manager.py            # Task lifecycle management
├── 
├── 📁 utils/                       # Utility functions
│   ├── __init__.py
│   └── file_utils.py              # File operations
├── 
├── 📁 storage/                     # Data storage
│   ├── temp/                      # Temporary processing files
│   ├── videos/                    # Final video outputs
│   ├── uploads/                   # User uploaded files
│   └── tasks.json                 # Task persistence
├── 
└── 📁 logs/                        # Log files (generated)
    ├── model_server.log           # Model server logs
    ├── handler_server.log         # Handler server logs
    ├── endpoints.log              # API endpoint logs
    └── musetalk_model.log         # MuseTalk processing logs
```

## 🔧 Core Components

### 1. Model Server (`model_server.py`)

```mermaid
graph LR
    subgraph "Model Server Process"
        START[Server Startup]
        LOAD[Load Models]
        LISTEN[Listen for Requests]
        PROCESS[Process Generation]
        RESPOND[Return Result]
    end
    
    START --> LOAD
    LOAD --> LISTEN
    LISTEN --> PROCESS
    PROCESS --> RESPOND
    RESPOND --> LISTEN
    
    subgraph "Model Loading"
        CWD[Change Working Dir]
        MODELS[Load MuseTalk Models]
        RESTORE[Restore Working Dir]
    end
    
    LOAD --> CWD
    CWD --> MODELS
    MODELS --> RESTORE
```

**Key Features:**
- **Singleton Pattern**: Single model instance shared across requests
- **Working Directory Management**: Changes to MuseTalk directory during loading
- **GPU Memory Optimization**: Float16 support and device management
- **Health Monitoring**: Endpoint for checking model status

### 2. Handler Server (`handler_server.py`)

```mermaid
graph LR
    subgraph "Handler Server Process"
        REQUEST[Receive Request]
        VALIDATE[Validate Input]
        TASK[Create Task]
        BACKGROUND[Start Background]
        RESPONSE[Return Response]
    end
    
    REQUEST --> VALIDATE
    VALIDATE --> TASK
    TASK --> BACKGROUND
    BACKGROUND --> RESPONSE
    
    subgraph "Background Processing"
        CALL[Call Model Server]
        WAIT[Wait for Completion]
        STORE[Store Result]
        UPDATE[Update Status]
    end
    
    BACKGROUND --> CALL
    CALL --> WAIT
    WAIT --> STORE
    STORE --> UPDATE
```

**Key Features:**
- **Async Processing**: Non-blocking request handling
- **Task Management**: Persistent task tracking with status updates
- **File Handling**: Upload/download with validation
- **Error Recovery**: Comprehensive error handling and logging

### 3. MuseTalk Model (`core/musetalk_model.py`)

This component implements the **exact same pattern** as the working Flask service:

```mermaid
flowchart TD
    A[Generate Request] --> B[Load Models if Needed]
    B --> C[Change to MuseTalk Directory]
    C --> D[Get Landmarks from File Paths]
    D --> E[Process Audio Features]
    E --> F[Generate VAE Latents]
    F --> G[Generate Frames]
    G --> H[Save Frames]
    H --> I[Create Video with FFmpeg]
    I --> J[Restore Working Directory]
    J --> K[Return Result]
    
    style C fill:#ff6b6b
    style D fill:#4ecdc4
    style J fill:#ff6b6b
    
    classDef critical fill:#ff6b6b,stroke:#333,stroke-width:2px
    classDef success fill:#4ecdc4,stroke:#333,stroke-width:2px
```

**Critical Implementation Details:**
- **File Path Pattern**: Passes file paths (not numpy arrays) to `get_landmark_and_bbox()`
- **Working Directory**: Changes to MuseTalk directory before model operations
- **Device Management**: Proper CUDA/CPU handling with string device parameters
- **Memory Optimization**: Float16 conversion for reduced GPU memory usage

## 📊 Data Flow Architecture

### Video Generation Pipeline

```mermaid
flowchart LR
    subgraph "Input Processing"
        IMG[Image File]
        AUD[Audio File]
        PARAMS[Parameters]
    end
    
    subgraph "Handler Server"
        VALIDATE[Validate Inputs]
        TASK[Create Task]
        DOWNLOAD[Download URLs]
    end
    
    subgraph "Model Server"
        LANDMARKS[Face Landmarks]
        AUDIO_FEAT[Audio Features]
        LATENTS[VAE Latents]
        INFERENCE[UNet Inference]
        DECODE[VAE Decode]
        BLEND[Face Blending]
    end
    
    subgraph "Output Generation"
        FRAMES[Individual Frames]
        FFMPEG[FFmpeg Assembly]
        VIDEO[Final Video]
    end
    
    IMG --> VALIDATE
    AUD --> VALIDATE
    PARAMS --> VALIDATE
    
    VALIDATE --> TASK
    TASK --> DOWNLOAD
    
    DOWNLOAD --> LANDMARKS
    LANDMARKS --> AUDIO_FEAT
    AUDIO_FEAT --> LATENTS
    LATENTS --> INFERENCE
    INFERENCE --> DECODE
    DECODE --> BLEND
    
    BLEND --> FRAMES
    FRAMES --> FFMPEG
    FFMPEG --> VIDEO
```

### Task Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending: Task Created
    pending --> processing: Background Task Started
    processing --> completed: Video Generated Successfully
    processing --> failed: Error Occurred
    completed --> [*]: Task Complete
    failed --> [*]: Task Failed
    
    note right of processing
        - Model server processing
        - Frame generation
        - Video assembly
    end note
    
    note right of completed
        - Video file saved
        - Ready for download
    end note
    
    note right of failed
        - Error logged
        - Task marked failed
    end note
```

## 🔄 Communication Protocol

### Handler ↔ Model Server

```mermaid
sequenceDiagram
    participant H as Handler Server
    participant M as Model Server
    
    Note over H,M: Generation Request
    
    H->>M: POST /generate
    Note right of H: {<br/>task_id: "uuid",<br/>image_path: "/path/to/image",<br/>audio_path: "/path/to/audio",<br/>output_path: "/path/to/output",<br/>bbox_shift: 0,<br/>fps: 25,<br/>batch_size: 8<br/>}
    
    M->>M: Validate inputs
    M->>M: Load models if needed
    M->>M: Generate video
    
    M->>H: Response
    Note left of M: {<br/>status: "success",<br/>task_id: "uuid",<br/>output_path: "/path/to/video",<br/>frames_generated: 499<br/>}
    
    Note over H,M: Health Check
    
    H->>M: GET /health
    M->>H: {<br/>status: "healthy",<br/>models_loaded: true,<br/>device: "cuda:0"<br/>}
```

## 🏛️ Comparison with Flask Service

### Architecture Differences

| Aspect | Flask Service | FastAPI Service |
|--------|---------------|-----------------|
| **Server Architecture** | Single server | Two-server (Handler + Model) |
| **Request Processing** | Synchronous | Asynchronous with background tasks |
| **Task Management** | Immediate response | Status tracking with polling |
| **Scalability** | Single instance | Multiple handlers, shared model |
| **Monitoring** | Basic logging | Comprehensive multi-file logging |

### Shared Critical Patterns

Both services implement these **essential patterns**:

```python
# ✅ CORRECT: File paths to get_landmark_and_bbox()
coord_list, frame_list = get_landmark_and_bbox([image_path], bbox_shift)

# ✅ CORRECT: Working directory management
original_cwd = os.getcwd()
os.chdir(settings.MUSETALK_DIR)
try:
    # Load models and process
finally:
    os.chdir(original_cwd)

# ✅ CORRECT: Device handling
device = torch.device(f"cuda:{gpu_id}" if torch.cuda.is_available() else "cpu")
```

## 🚀 Deployment Architecture

### Development Setup

```mermaid
graph TB
    subgraph "Developer Machine"
        DEV[Development Environment]
        PORT1[":8001 Model Server"]
        PORT2[":8000 Handler Server"]
    end
    
    subgraph "Local Testing"
        CURL[curl commands]
        BROWSER[Browser/Postman]
    end
    
    DEV --> PORT1
    DEV --> PORT2
    CURL --> PORT2
    BROWSER --> PORT2
    PORT2 --> PORT1
```

### Production Deployment

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx/HAProxy]
    end
    
    subgraph "Handler Tier"
        H1[Handler Server 1]
        H2[Handler Server 2]
        H3[Handler Server N]
    end
    
    subgraph "Model Tier"
        M1[Model Server GPU-1]
        M2[Model Server GPU-2]
        MN[Model Server GPU-N]
    end
    
    subgraph "Storage"
        REDIS[Redis Cache]
        DB[PostgreSQL]
        FILES[File Storage]
    end
    
    LB --> H1
    LB --> H2  
    LB --> H3
    
    H1 --> M1
    H2 --> M2
    H3 --> MN
    
    H1 --> REDIS
    H2 --> REDIS
    H3 --> REDIS
    
    H1 --> DB
    H2 --> DB
    H3 --> DB
    
    M1 --> FILES
    M2 --> FILES
    MN --> FILES
```

## 📈 Performance Characteristics

### Resource Usage

```mermaid
graph LR
    subgraph "Handler Server"
        CPU_H[CPU: Low]
        RAM_H[RAM: ~512MB]
        GPU_H[GPU: None]
    end
    
    subgraph "Model Server"
        CPU_M[CPU: Medium]
        RAM_M[RAM: ~8GB]
        GPU_M[GPU: ~6GB VRAM]
    end
    
    subgraph "Processing"
        BATCH[Batch Size: 2-8]
        TIME[~2min for 20s video]
        CONCURRENT[1 model / multiple handlers]
    end
```

### Scaling Patterns

1. **Horizontal Scaling**: Deploy multiple handler servers
2. **GPU Scaling**: One model server per GPU
3. **Load Distribution**: Round-robin or least-connections
4. **Caching**: Redis for task status, file metadata

## 🔐 Security Considerations

### Input Validation

```mermaid
flowchart TD
    REQUEST[Incoming Request] --> VALIDATE[Input Validation]
    VALIDATE --> SANITIZE[Path Sanitization]
    SANITIZE --> SIZE[File Size Check]
    SIZE --> TYPE[File Type Check]
    TYPE --> VIRUS[Virus Scan]
    VIRUS --> PROCEED[Process Request]
    
    VALIDATE -->|Invalid| REJECT[Reject Request]
    SANITIZE -->|Unsafe| REJECT
    SIZE -->|Too Large| REJECT
    TYPE -->|Not Allowed| REJECT
    VIRUS -->|Infected| REJECT
```

### Production Security

- **Authentication**: JWT tokens or API keys
- **Rate Limiting**: Request throttling per client
- **Input Sanitization**: Path traversal prevention
- **File Validation**: Type checking and virus scanning
- **Network Security**: Firewall rules and VPN access
- **Logging**: Security event monitoring

## 🔍 Monitoring and Observability

### Log Architecture

```mermaid
graph TD
    subgraph "Application Logs"
        MODEL[model_server.log]
        HANDLER[handler_server.log]
        ENDPOINTS[endpoints.log]
        MUSETALK[musetalk_model.log]
    end
    
    subgraph "System Logs"
        SYSTEM[System Logs]
        GPU[GPU Monitoring]
        DISK[Disk Usage]
    end
    
    subgraph "Aggregation"
        FILEBEAT[Filebeat]
        LOGSTASH[Logstash]
        ELASTIC[Elasticsearch]
    end
    
    subgraph "Visualization"
        KIBANA[Kibana Dashboards]
        GRAFANA[Grafana Metrics]
        ALERTS[Alert Manager]
    end
    
    MODEL --> FILEBEAT
    HANDLER --> FILEBEAT
    ENDPOINTS --> FILEBEAT
    MUSETALK --> FILEBEAT
    
    SYSTEM --> FILEBEAT
    GPU --> FILEBEAT
    DISK --> FILEBEAT
    
    FILEBEAT --> LOGSTASH
    LOGSTASH --> ELASTIC
    
    ELASTIC --> KIBANA
    ELASTIC --> GRAFANA
    ELASTIC --> ALERTS
```

### Health Check Hierarchy

```mermaid
graph TB
    CLIENT[Client Request] --> HANDLER_HEALTH[Handler Health Check]
    HANDLER_HEALTH --> MODEL_HEALTH[Model Server Health]
    MODEL_HEALTH --> GPU_CHECK[GPU Availability]
    GPU_CHECK --> MODEL_STATUS[Models Loaded]
    MODEL_STATUS --> DISK_SPACE[Disk Space]
    DISK_SPACE --> ALL_GOOD[All Systems Healthy]
    
    HANDLER_HEALTH -->|Failed| HANDLER_DOWN[Handler Server Down]
    MODEL_HEALTH -->|Failed| MODEL_DOWN[Model Server Down]
    GPU_CHECK -->|Failed| GPU_ISSUE[GPU Not Available]
    MODEL_STATUS -->|Failed| MODELS_NOT_LOADED[Models Not Loaded]
    DISK_SPACE -->|Failed| DISK_FULL[Disk Space Critical]
```

## 🐛 Troubleshooting Guide

### Common Issues and Solutions

#### 1. Model Loading Failures

```mermaid
flowchart TD
    ERROR[Model Loading Error] --> CHECK_CUDA[Check CUDA Available?]
    CHECK_CUDA -->|No| INSTALL_CUDA[Install CUDA Drivers]
    CHECK_CUDA -->|Yes| CHECK_MODELS[Models Directory Exists?]
    CHECK_MODELS -->|No| DOWNLOAD_MODELS[Download Model Weights]
    CHECK_MODELS -->|Yes| CHECK_PERMISSIONS[File Permissions OK?]
    CHECK_PERMISSIONS -->|No| FIX_PERMS[chmod 644 models/*]
    CHECK_PERMISSIONS -->|Yes| CHECK_MEMORY[GPU Memory Available?]
    CHECK_MEMORY -->|No| REDUCE_BATCH[Reduce Batch Size/Enable Float16]
    CHECK_MEMORY -->|Yes| CHECK_WORKING_DIR[Working Directory Issue?]
    CHECK_WORKING_DIR -->|Yes| FIX_CWD[Ensure os.chdir(MUSETALK_DIR)]
```

#### 2. Video Generation Failures

```mermaid
flowchart TD
    VIDEO_ERROR[Video Generation Error] --> CHECK_INPUTS[Input Files Valid?]
    CHECK_INPUTS -->|No| FIX_INPUTS[Check File Paths/Formats]
    CHECK_INPUTS -->|Yes| CHECK_LANDMARKS[Face Detection Working?]
    CHECK_LANDMARKS -->|No| BBOX_ADJUST[Adjust bbox_shift Parameter]
    CHECK_LANDMARKS -->|Yes| CHECK_AUDIO[Audio Processing OK?]
    CHECK_AUDIO -->|No| AUDIO_FORMAT[Convert to Supported Format]
    CHECK_AUDIO -->|Yes| CHECK_FFMPEG[FFmpeg Available?]
    CHECK_FFMPEG -->|No| INSTALL_FFMPEG[Install FFmpeg]
    CHECK_FFMPEG -->|Yes| CHECK_SPACE[Disk Space Available?]
    CHECK_SPACE -->|No| CLEANUP[Free Disk Space]
```

### Debug Commands

```bash
# Check server status
curl -s http://localhost:8000/api/v1/health | jq .
curl -s http://localhost:8001/health | jq .

# Monitor logs in real-time
tail -f fastapi_server/model_server.log
tail -f fastapi_server/handler_server.log
tail -f fastapi_server/endpoints.log
tail -f fastapi_server/musetalk_model.log

# Check GPU status
nvidia-smi

# Verify model files
ls -la models/
find models/ -name "*.pth" -o -name "*.json"

# Test model loading
cd /workspace/ai-video-generation/MuseTalk
python -c "from musetalk.utils.utils import load_all_model; print('Import OK')"

# Check port usage
lsof -i :8000
lsof -i :8001
```

## 📚 References and Resources

### Technical Documentation
- **Flask Service**: `/workspace/ai-video-generation/MuseTalk/service/ARCHITECTURE.md`
- **MuseTalk Paper**: [MuseTalk: Real-Time High Quality Lip Synchronization](https://github.com/TMElyralab/MuseTalk)
- **FastAPI Documentation**: [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)

### Key Implementation Files
- **Model Wrapper**: `core/musetalk_model.py:141` (File path pattern)
- **Flask Reference**: `service/core/inference_handler.py:86` (Working implementation)
- **Settings**: `config/settings.py` (Configuration management)

### Dependencies
- **MuseTalk**: Core AI model for talking head generation
- **FastAPI**: Modern Python web framework
- **Uvicorn**: ASGI server implementation
- **PyTorch**: Deep learning framework
- **OpenCV**: Computer vision operations
- **FFmpeg**: Video processing pipeline

---

**Architecture Status**: ✅ **Proven and Production-Ready**

This architecture has been tested and validated to work correctly with MuseTalk video generation, following the same proven patterns as the working Flask service implementation.