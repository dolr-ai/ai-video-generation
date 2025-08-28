import os
import hashlib
import pickle
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import shutil

logger = logging.getLogger(__name__)

class FaceDetectionCache:
    """
    Cache system for face detection results to avoid expensive recomputation
    """
    
    def __init__(self, cache_dir: str, max_size_gb: float = 10.0):
        """
        Initialize face detection cache
        
        Args:
            cache_dir: Directory to store cache files
            max_size_gb: Maximum cache size in GB
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_gb * 1024 * 1024 * 1024
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.load_metadata()
        
    def load_metadata(self):
        """Load cache metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    self.metadata = json.load(f)
            except:
                self.metadata = {}
        else:
            self.metadata = {}
    
    def save_metadata(self):
        """Save cache metadata"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache metadata: {e}")
    
    def get_cache_key(self, file_path: str, bbox_shift: int = 0, 
                      extra_params: Optional[Dict] = None) -> str:
        """
        Generate unique cache key for a file and parameters
        
        Args:
            file_path: Path to video/image file
            bbox_shift: Bounding box shift parameter
            extra_params: Additional parameters affecting face detection
            
        Returns:
            Unique cache key string
        """
        # Get file stats
        file_stats = os.stat(file_path)
        file_size = file_stats.st_size
        file_mtime = file_stats.st_mtime
        
        # Create unique identifier
        cache_data = {
            'file_path': os.path.abspath(file_path),
            'file_size': file_size,
            'file_mtime': file_mtime,
            'bbox_shift': bbox_shift
        }
        
        if extra_params:
            cache_data.update(extra_params)
        
        # Generate hash
        cache_str = json.dumps(cache_data, sort_keys=True)
        cache_hash = hashlib.md5(cache_str.encode()).hexdigest()
        
        return cache_hash
    
    def get_cache_path(self, cache_key: str) -> Path:
        """Get path for cache file"""
        return self.cache_dir / f"{cache_key}.pkl"
    
    def save_face_data(self, cache_key: str, coord_list: List, 
                       frame_list: Optional[List] = None,
                       extra_data: Optional[Dict] = None) -> bool:
        """
        Save face detection data to cache
        
        Args:
            cache_key: Unique cache key
            coord_list: List of face coordinates/bounding boxes
            frame_list: Optional list of frames
            extra_data: Additional data to cache
            
        Returns:
            True if saved successfully
        """
        try:
            cache_path = self.get_cache_path(cache_key)
            
            # Prepare cache data
            cache_data = {
                'coord_list': coord_list,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            # Don't cache actual frames (too large), just metadata
            if frame_list:
                cache_data['frame_count'] = len(frame_list)
                cache_data['frame_shapes'] = [frame.shape for frame in frame_list[:1]]  # Sample shape
            
            if extra_data:
                cache_data['extra'] = extra_data
            
            # Save to pickle file
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            
            # Update metadata
            self.metadata[cache_key] = {
                'path': str(cache_path),
                'timestamp': cache_data['timestamp'],
                'size': os.path.getsize(cache_path),
                'hits': 0
            }
            self.save_metadata()
            
            logger.info(f"Cached face detection data: {cache_key}")
            
            # Check cache size and cleanup if needed
            self._check_cache_size()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            return False
    
    def load_face_data(self, cache_key: str) -> Optional[Dict]:
        """
        Load face detection data from cache
        
        Args:
            cache_key: Unique cache key
            
        Returns:
            Cached data dictionary or None if not found/invalid
        """
        try:
            cache_path = self.get_cache_path(cache_key)
            
            if not cache_path.exists():
                return None
            
            # Load cached data
            with open(cache_path, 'rb') as f:
                cache_data = pickle.load(f)
            
            # Update hit count
            if cache_key in self.metadata:
                self.metadata[cache_key]['hits'] = self.metadata[cache_key].get('hits', 0) + 1
                self.metadata[cache_key]['last_accessed'] = datetime.now().isoformat()
                self.save_metadata()
            
            logger.info(f"Loaded cached face detection data: {cache_key}")
            return cache_data
            
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            # Remove corrupted cache entry
            if cache_path.exists():
                try:
                    os.remove(cache_path)
                    if cache_key in self.metadata:
                        del self.metadata[cache_key]
                        self.save_metadata()
                except:
                    pass
            return None
    
    def _check_cache_size(self):
        """Check cache size and cleanup old entries if needed"""
        try:
            # Calculate total cache size
            total_size = sum(
                entry.get('size', 0) 
                for entry in self.metadata.values()
            )
            
            if total_size > self.max_size_bytes:
                logger.warning(f"Cache size ({total_size / 1e9:.2f}GB) exceeds limit ({self.max_size_bytes / 1e9:.2f}GB)")
                self._cleanup_old_entries()
                
        except Exception as e:
            logger.error(f"Error checking cache size: {e}")
    
    def _cleanup_old_entries(self):
        """Remove oldest cache entries based on last access time"""
        try:
            # Sort by last access time (oldest first)
            sorted_entries = sorted(
                self.metadata.items(),
                key=lambda x: x[1].get('last_accessed', x[1].get('timestamp', ''))
            )
            
            # Remove oldest 20% of entries
            num_to_remove = max(1, len(sorted_entries) // 5)
            
            for cache_key, entry in sorted_entries[:num_to_remove]:
                cache_path = Path(entry['path'])
                if cache_path.exists():
                    os.remove(cache_path)
                del self.metadata[cache_key]
                logger.info(f"Removed old cache entry: {cache_key}")
            
            self.save_metadata()
            
        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")
    
    def clear_cache(self):
        """Clear all cache entries"""
        try:
            # Remove all cache files
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            
            # Clear metadata
            self.metadata = {}
            self.save_metadata()
            
            logger.info("Cache cleared successfully")
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def get_statistics(self) -> Dict:
        """Get cache statistics"""
        try:
            total_size = sum(
                entry.get('size', 0) 
                for entry in self.metadata.values()
            )
            
            total_hits = sum(
                entry.get('hits', 0)
                for entry in self.metadata.values()
            )
            
            return {
                'num_entries': len(self.metadata),
                'total_size_gb': round(total_size / 1e9, 2),
                'max_size_gb': round(self.max_size_bytes / 1e9, 2),
                'total_hits': total_hits,
                'cache_dir': str(self.cache_dir)
            }
            
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {}


class RealtimePreparationCache:
    """
    Cache system for realtime video generation preparations
    """
    
    def __init__(self, prep_dir: str, cleanup_days: int = 7):
        """
        Initialize realtime preparation cache
        
        Args:
            prep_dir: Directory to store preparation data
            cleanup_days: Days to keep preparations before cleanup
        """
        self.prep_dir = Path(prep_dir)
        self.prep_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_days = cleanup_days
        self.metadata_file = self.prep_dir / "preparations.json"
        self.load_metadata()
    
    def load_metadata(self):
        """Load preparations metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    self.metadata = json.load(f)
            except:
                self.metadata = {}
        else:
            self.metadata = {}
    
    def save_metadata(self):
        """Save preparations metadata"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save preparations metadata: {e}")
    
    def save_preparation(self, prep_id: str, data: Dict) -> bool:
        """
        Save realtime preparation data
        
        Args:
            prep_id: Unique preparation ID
            data: Preparation data including coordinates, latents, masks
            
        Returns:
            True if saved successfully
        """
        try:
            prep_path = self.prep_dir / prep_id
            prep_path.mkdir(parents=True, exist_ok=True)
            
            # Save different components
            if 'coordinates' in data:
                with open(prep_path / 'coordinates.pkl', 'wb') as f:
                    pickle.dump(data['coordinates'], f)
            
            if 'latents' in data:
                import torch
                torch.save(data['latents'], prep_path / 'latents.pt')
            
            if 'masks' in data:
                with open(prep_path / 'masks.pkl', 'wb') as f:
                    pickle.dump(data['masks'], f)
            
            if 'metadata' in data:
                with open(prep_path / 'metadata.json', 'w') as f:
                    json.dump(data['metadata'], f, indent=2)
            
            # Update global metadata
            self.metadata[prep_id] = {
                'path': str(prep_path),
                'timestamp': datetime.now().isoformat(),
                'size': self._get_dir_size(prep_path),
                'uses': 0
            }
            self.save_metadata()
            
            logger.info(f"Saved realtime preparation: {prep_id}")
            
            # Cleanup old preparations
            self._cleanup_old_preparations()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save preparation: {e}")
            return False
    
    def load_preparation(self, prep_id: str) -> Optional[Dict]:
        """
        Load realtime preparation data
        
        Args:
            prep_id: Unique preparation ID
            
        Returns:
            Preparation data or None if not found
        """
        try:
            prep_path = self.prep_dir / prep_id
            
            if not prep_path.exists():
                return None
            
            data = {}
            
            # Load components
            coord_path = prep_path / 'coordinates.pkl'
            if coord_path.exists():
                with open(coord_path, 'rb') as f:
                    data['coordinates'] = pickle.load(f)
            
            latents_path = prep_path / 'latents.pt'
            if latents_path.exists():
                import torch
                data['latents'] = torch.load(latents_path)
            
            masks_path = prep_path / 'masks.pkl'
            if masks_path.exists():
                with open(masks_path, 'rb') as f:
                    data['masks'] = pickle.load(f)
            
            metadata_path = prep_path / 'metadata.json'
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    data['metadata'] = json.load(f)
            
            # Update usage count
            if prep_id in self.metadata:
                self.metadata[prep_id]['uses'] = self.metadata[prep_id].get('uses', 0) + 1
                self.metadata[prep_id]['last_used'] = datetime.now().isoformat()
                self.save_metadata()
            
            logger.info(f"Loaded realtime preparation: {prep_id}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to load preparation: {e}")
            return None
    
    def _get_dir_size(self, path: Path) -> int:
        """Calculate directory size in bytes"""
        total = 0
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
        return total
    
    def _cleanup_old_preparations(self):
        """Remove preparations older than cleanup_days"""
        try:
            cutoff_time = datetime.now() - timedelta(days=self.cleanup_days)
            
            to_remove = []
            for prep_id, info in self.metadata.items():
                timestamp = datetime.fromisoformat(info['timestamp'])
                if timestamp < cutoff_time:
                    to_remove.append(prep_id)
            
            for prep_id in to_remove:
                prep_path = Path(self.metadata[prep_id]['path'])
                if prep_path.exists():
                    shutil.rmtree(prep_path)
                del self.metadata[prep_id]
                logger.info(f"Removed old preparation: {prep_id}")
            
            if to_remove:
                self.save_metadata()
                
        except Exception as e:
            logger.error(f"Error cleaning up preparations: {e}")
    
    def delete_preparation(self, prep_id: str) -> bool:
        """
        Delete a specific preparation
        
        Args:
            prep_id: Preparation ID to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            if prep_id in self.metadata:
                prep_path = Path(self.metadata[prep_id]['path'])
                if prep_path.exists():
                    shutil.rmtree(prep_path)
                del self.metadata[prep_id]
                self.save_metadata()
                logger.info(f"Deleted preparation: {prep_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting preparation: {e}")
            return False
    
    def get_statistics(self) -> Dict:
        """Get preparation cache statistics"""
        try:
            total_size = sum(
                info.get('size', 0)
                for info in self.metadata.values()
            )
            
            total_uses = sum(
                info.get('uses', 0)
                for info in self.metadata.values()
            )
            
            return {
                'num_preparations': len(self.metadata),
                'total_size_gb': round(total_size / 1e9, 2),
                'total_uses': total_uses,
                'cleanup_days': self.cleanup_days,
                'prep_dir': str(self.prep_dir)
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}