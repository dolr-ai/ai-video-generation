import asyncio
import logging
import httpx
import os
from typing import Optional

from core.task_manager import task_manager, TaskStatus
from utils.file_utils import create_task_directory, save_video_file
from config.settings import settings

# Setup logging
queue_logger = logging.getLogger('queue_processor')
queue_handler = logging.FileHandler(os.path.join(settings.FASTAPI_SERVER_DIR, 'queue_processor.log'))
queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
queue_logger.addHandler(queue_handler)
queue_logger.setLevel(logging.DEBUG)

# Also add console output
queue_console_handler = logging.StreamHandler()
queue_console_handler.setFormatter(logging.Formatter('%(asctime)s - QUEUE - %(levelname)s - %(message)s'))
queue_logger.addHandler(queue_console_handler)


class QueueProcessor:
    def __init__(self):
        self.running = False
        self._processor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the queue processor"""
        if self.running:
            return
        
        self.running = True
        self._processor_task = asyncio.create_task(self._process_queue())
        queue_logger.info("Queue processor started")
    
    async def stop(self):
        """Stop the queue processor"""
        if not self.running:
            return
        
        self.running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        queue_logger.info("Queue processor stopped")
    
    async def _process_queue(self):
        """Main queue processing loop"""
        queue_logger.info("Queue processor loop started")
        
        while self.running:
            try:
                # Wait for task in queue
                task_id = await task_manager.task_queue.get()
                
                if not self.running:
                    break
                
                # Acquire semaphore (limit concurrent model requests)
                async with task_manager.processing_semaphore:
                    queue_logger.info(f"🔄 Processing task {task_id} from queue")
                    
                    # Update queue positions for remaining tasks
                    task_manager.update_queue_positions()
                    
                    # Process the task
                    await self._process_single_task(task_id)
                
                # Mark task as done in queue
                task_manager.task_queue.task_done()
                
            except asyncio.CancelledError:
                queue_logger.info("Queue processor cancelled")
                break
            except Exception as e:
                queue_logger.error(f"Error in queue processor: {str(e)}")
                import traceback
                queue_logger.error(f"Full traceback:\n{traceback.format_exc()}")
                await asyncio.sleep(1)  # Prevent tight loop on errors
    
    async def _process_single_task(self, task_id: str):
        """Process a single task"""
        try:
            task = task_manager.get_task(task_id)
            if not task:
                queue_logger.error(f"Task {task_id} not found")
                return
            
            queue_logger.info(f"🎬 Starting processing for task: {task_id}")
            queue_logger.info(f"  Image: {task.image_path}")
            queue_logger.info(f"  Audio: {task.audio_path}")
            queue_logger.info(f"  User ID: {task.user_id}")

            # Update status to processing
            task_manager.update_task_status(task_id, TaskStatus.PROCESSING)

            # Prepare output path
            output_filename = f"generated_{task_id}.mp4"
            temp_output_path = os.path.join(create_task_directory(task_id), output_filename)

            # Call model server
            queue_logger.info(f"🌐 Calling model server for task {task_id}")
            async with httpx.AsyncClient(timeout=settings.MODEL_SERVER_TIMEOUT) as client:
                model_server_url = f"http://{settings.MODEL_SERVER_HOST}:{settings.MODEL_SERVER_PORT}"
                queue_logger.info(f"Model server URL: {model_server_url}")

                generation_request = {
                    "task_id": task_id,
                    "image_path": task.image_path,
                    "audio_path": task.audio_path,
                    "output_path": temp_output_path,
                    "bbox_shift": task.bbox_shift,
                    "fps": task.fps,
                    "batch_size": task.batch_size,
                }

                response = await client.post(
                    f"{model_server_url}/generate",
                    json=generation_request,
                    timeout=settings.GENERATION_TIMEOUT,
                )

                if response.status_code == 200:
                    result = response.json()
                    if result["status"] == "success":
                        # Save video to permanent storage
                        final_video_path = save_video_file(
                            task_id, temp_output_path, output_filename
                        )

                        # Update task status
                        task_manager.update_task_status(
                            task_id, TaskStatus.COMPLETED, output_path=final_video_path
                        )

                        queue_logger.info(
                            f"✅ Task {task_id} completed successfully - Video saved to: {final_video_path}"
                        )
                    else:
                        # Generation failed
                        task_manager.update_task_status(
                            task_id,
                            TaskStatus.FAILED,
                            error_message=result.get("message", "Unknown error"),
                        )
                        queue_logger.error(
                            f"❌ Task {task_id} generation failed: {result.get('message')}"
                        )
                else:
                    # HTTP error
                    error_msg = f"Model server error: {response.status_code}"
                    task_manager.update_task_status(
                        task_id, TaskStatus.FAILED, error_message=error_msg
                    )
                    queue_logger.error(f"❌ Task {task_id} HTTP error: {error_msg}")

        except Exception as e:
            import traceback
            error_msg = f"Error processing task: {str(e)}"
            task_manager.update_task_status(
                task_id, TaskStatus.FAILED, error_message=error_msg
            )
            queue_logger.error(f"❌ Task {task_id} exception: {error_msg}")
            queue_logger.error(f"Full traceback:\n{traceback.format_exc()}")


# Global queue processor instance
queue_processor = QueueProcessor()