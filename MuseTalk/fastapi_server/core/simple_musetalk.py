"""
Simple MuseTalk wrapper that closely mirrors the working Flask service approach
"""
import os
import sys
import subprocess
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class SimpleMuseTalkModel:
    """Simple wrapper that calls the working Flask service internally"""
    
    def __init__(self):
        self.flask_service_url = "http://localhost:5000/api/v1"
        
    def generate_talking_head(self, image_path: str, audio_path: str, output_path: str, 
                            bbox_shift: int = 0, fps: int = 25, batch_size: int = 8) -> Dict:
        """Generate talking head by calling the working Flask service"""
        try:
            import requests
            
            logger.info(f"Using Flask service to generate: {image_path} + {audio_path}")
            
            # Call the working Flask service
            data = {
                "image": image_path,
                "audio": audio_path,
                "local_dev": True,
                "bbox_shift": bbox_shift,
                "fps": fps,
                "batch_size": batch_size
            }
            
            response = requests.post(f"{self.flask_service_url}/generate", json=data, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                
                if result['status'] == 'success':
                    # Copy the generated video to our desired location
                    flask_output = result['output_path']
                    
                    if os.path.exists(flask_output):
                        # Create output directory
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        
                        # Copy the file
                        import shutil
                        shutil.copy2(flask_output, output_path)
                        
                        logger.info(f"Successfully copied video from {flask_output} to {output_path}")
                        
                        return {
                            'status': 'success',
                            'output_path': output_path,
                            'message': 'Video generated via Flask service'
                        }
                    else:
                        return {
                            'status': 'error',
                            'message': f'Flask service output file not found: {flask_output}'
                        }
                else:
                    return {
                        'status': 'error',
                        'message': f'Flask service error: {result.get("message", "Unknown error")}'
                    }
            else:
                return {
                    'status': 'error',
                    'message': f'Flask service HTTP error: {response.status_code}'
                }
                
        except Exception as e:
            logger.error(f"Error calling Flask service: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def health_check(self) -> Dict:
        """Check if Flask service is available"""
        try:
            import requests
            response = requests.get(f"{self.flask_service_url}/health", timeout=5)
            if response.status_code == 200:
                return {
                    'status': 'healthy',
                    'models_loaded': True,
                    'device': 'flask_service',
                    'cuda_available': True
                }
        except:
            pass
        
        return {
            'status': 'unhealthy',
            'models_loaded': False,
            'device': 'unavailable',
            'cuda_available': False
        }