import asyncio
import json
import logging
import os
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict

from config.settings import settings

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Task:
    task_id: str
    status: TaskStatus
    image_path: str
    audio_path: str
    user_id: str
    output_path: Optional[str] = None
    gcs_path: Optional[str] = None  # GCS path for uploaded video
    created_at: str = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    bbox_shift: int = settings.DEFAULT_BBOX_SHIFT
    fps: int = settings.DEFAULT_FPS
    batch_size: int = settings.DEFAULT_BATCH_SIZE
    queue_position: Optional[int] = None
    input_type: str = "image"  # "image" or "video"
    video_start_time: Optional[float] = None  # For video input
    video_end_time: Optional[float] = None  # For video input
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.task_queue: Optional[asyncio.Queue] = None
        self.processing_semaphore: Optional[asyncio.Semaphore] = None
        self.tasks_file = os.path.join(settings.STORAGE_DIR, 'tasks.json')
        self._load_tasks()
        # Start the queue processor
        self._queue_processor_task = None
        
    def _ensure_async_objects(self):
        """Initialize async objects when event loop is available"""
        if self.task_queue is None:
            self.task_queue = asyncio.Queue()
        if self.processing_semaphore is None:
            self.processing_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_MODEL_REQUESTS)
        
    def _load_tasks(self):
        """Load tasks from persistent storage"""
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, 'r') as f:
                    tasks_data = json.load(f)
                    for task_id, task_data in tasks_data.items():
                        self.tasks[task_id] = Task(**task_data)
                logger.info(f"Loaded {len(self.tasks)} tasks from storage")
        except Exception as e:
            logger.error(f"Error loading tasks: {str(e)}")
            self.tasks = {}
    
    def _save_tasks(self):
        """Save tasks to persistent storage"""
        try:
            os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)
            with open(self.tasks_file, 'w') as f:
                tasks_data = {task_id: asdict(task) for task_id, task in self.tasks.items()}
                json.dump(tasks_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving tasks: {str(e)}")
    
    def create_task(self, task_id: str, image_path: str, audio_path: str, user_id: str,
                   bbox_shift: int = settings.DEFAULT_BBOX_SHIFT, fps: int = settings.DEFAULT_FPS, 
                   batch_size: int = settings.DEFAULT_BATCH_SIZE, input_type: str = "image",
                   video_start_time: Optional[float] = None, video_end_time: Optional[float] = None) -> Task:
        """Create a new task"""
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            image_path=image_path,
            audio_path=audio_path,
            user_id=user_id,
            bbox_shift=bbox_shift,
            fps=fps,
            batch_size=batch_size,
            input_type=input_type,
            video_start_time=video_start_time,
            video_end_time=video_end_time
        )
        
        self.tasks[task_id] = task
        self._save_tasks()
        
        logger.info(f"Created task: {task_id}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    def update_task_status(self, task_id: str, status: TaskStatus, 
                          output_path: Optional[str] = None, 
                          gcs_path: Optional[str] = None,
                          error_message: Optional[str] = None):
        """Update task status"""
        task = self.tasks.get(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
            return
        
        task.status = status
        
        if status == TaskStatus.PROCESSING and not task.started_at:
            task.started_at = datetime.now().isoformat()
        
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            task.completed_at = datetime.now().isoformat()
            
        if output_path:
            task.output_path = output_path
            
        if gcs_path:
            task.gcs_path = gcs_path
            
        if error_message:
            task.error_message = error_message
            
        self._save_tasks()
        logger.info(f"Updated task {task_id} status to {status}")
    
    def get_all_tasks(self) -> Dict[str, Task]:
        """Get all tasks"""
        return self.tasks.copy()
    
    def add_task_to_queue(self, task_id: str):
        """Add task to processing queue"""
        if task_id not in self.tasks:
            logger.error(f"Cannot queue task {task_id}: task not found")
            return
        
        # Ensure async objects are initialized
        self._ensure_async_objects()
        
        # Update status to queued
        self.update_task_status(task_id, TaskStatus.QUEUED)
        
        # Add to queue
        self.task_queue.put_nowait(task_id)
        logger.info(f"Added task {task_id} to queue. Queue size: {self.task_queue.qsize()}")
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        if self.task_queue is None:
            return 0
        return self.task_queue.qsize()
    
    def get_queued_tasks(self) -> List[str]:
        """Get list of queued task IDs"""
        queued_tasks = []
        for task_id, task in self.tasks.items():
            if task.status == TaskStatus.QUEUED:
                queued_tasks.append(task_id)
        return queued_tasks
    
    def update_queue_positions(self):
        """Update queue positions for queued tasks"""
        queued_tasks = self.get_queued_tasks()
        for position, task_id in enumerate(queued_tasks):
            task = self.tasks.get(task_id)
            if task:
                task.queue_position = position + 1
        self._save_tasks()
    
    def cleanup_old_tasks(self, days: int = 7):
        """Remove tasks older than specified days"""
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            created_at = datetime.fromisoformat(task.created_at)
            if created_at < cutoff_date:
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
            logger.info(f"Removed old task: {task_id}")
        
        if tasks_to_remove:
            self._save_tasks()

# Global task manager instance
task_manager = TaskManager()