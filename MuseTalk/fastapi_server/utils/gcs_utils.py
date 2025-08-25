import os
import json
import logging
from datetime import datetime
from typing import Optional
from google.cloud import storage
from google.oauth2 import service_account

from config.settings import settings

logger = logging.getLogger(__name__)


class GCSUploader:
    def __init__(self):
        self.client = None
        self.bucket = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize GCS client with credentials from environment"""
        try:
            if not settings.GCS_ENABLED:
                logger.info("GCS upload is disabled")
                return
            
            if not settings.GCP_CREDENTIALS:
                logger.warning("GCP_CREDENTIALS environment variable not set, GCS upload disabled")
                return
            
            # Parse credentials from environment variable (JSON string)
            try:
                credentials_info = json.loads(settings.GCP_CREDENTIALS)
                credentials = service_account.Credentials.from_service_account_info(credentials_info)
                self.client = storage.Client(credentials=credentials)
                self.bucket = self.client.bucket(settings.GCS_BUCKET_NAME)
                logger.info(f"GCS client initialized for bucket: {settings.GCS_BUCKET_NAME}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse GCP_CREDENTIALS JSON: {str(e)}")
                return
            except Exception as e:
                logger.error(f"Failed to create GCS credentials: {str(e)}")
                return
                
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {str(e)}")
    
    def upload_video(self, local_file_path: str, task_id: str) -> Optional[str]:
        """
        Upload video to GCS and return the GCS path
        
        Args:
            local_file_path: Path to the local video file
            task_id: Unique task identifier
            
        Returns:
            GCS path (gs://bucket/path) if successful, None otherwise
        """
        if not self.client or not self.bucket:
            logger.warning("GCS client not initialized, skipping upload")
            return None
        
        try:
            # Generate GCS path with date
            date_str = datetime.now().strftime("%d%m%y")
            filename = f"output-{date_str}.mp4"
            blob_path = f"{settings.GCS_BASE_PATH}/{task_id}/{filename}"
            
            # Upload file
            blob = self.bucket.blob(blob_path)
            blob.upload_from_filename(local_file_path)
            
            # Generate GCS URI
            gcs_uri = f"gs://{settings.GCS_BUCKET_NAME}/{blob_path}"
            
            logger.info(f"Successfully uploaded video to GCS: {gcs_uri}")
            return gcs_uri
            
        except Exception as e:
            logger.error(f"Failed to upload video to GCS: {str(e)}")
            return None
    
    def check_connection(self) -> bool:
        """Check if GCS connection is working"""
        if not self.client or not self.bucket:
            return False
        
        try:
            # Try to check if bucket exists
            self.bucket.reload()
            return True
        except Exception as e:
            logger.error(f"GCS connection check failed: {str(e)}")
            return False


# Global GCS uploader instance
gcs_uploader = GCSUploader()