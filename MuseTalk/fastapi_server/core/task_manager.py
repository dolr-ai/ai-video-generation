import asyncio
import json
import logging
import os
from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass, asdict

from config.settings import settings

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Task:
    task_id: str
    status: TaskStatus
    image_path: str
    audio_path: str
    output_path: Optional[str] = None
    created_at: str = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    bbox_shift: int = 0
    fps: int = 25
    batch_size: int = 8
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.tasks_file = os.path.join(settings.STORAGE_DIR, 'tasks.json')
        self._load_tasks()
        
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
    
    def create_task(self, task_id: str, image_path: str, audio_path: str, 
                   bbox_shift: int = 0, fps: int = 25, batch_size: int = 8) -> Task:
        """Create a new task"""
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            image_path=image_path,
            audio_path=audio_path,
            bbox_shift=bbox_shift,
            fps=fps,
            batch_size=batch_size
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
            
        if error_message:
            task.error_message = error_message
            
        self._save_tasks()
        logger.info(f"Updated task {task_id} status to {status}")
    
    def get_all_tasks(self) -> Dict[str, Task]:
        """Get all tasks"""
        return self.tasks.copy()
    
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