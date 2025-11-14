import os
import logging
from typing import Optional, List, Dict, Any
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError
from config import Config

logger = logging.getLogger(__name__)


class GCSClient:
    """Google Cloud Storage client for handling file operations"""
    
    def __init__(self):
        """Initialize GCS client"""
        try:
            self.client = storage.Client(project=Config.GOOGLE_CLOUD_PROJECT)
            self.bucket_name = Config.GCS_BUCKET_NAME
            self.bucket = None
            
            if self.bucket_name:
                self._initialize_bucket()
            else:
                logger.warning("GCS_BUCKET_NAME not configured")
                
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            raise
    
    def _initialize_bucket(self):
        """Initialize and validate bucket access"""
        try:
            self.bucket = self.client.bucket(self.bucket_name)
            # Test bucket access
            self.bucket.reload()
            logger.info(f"Successfully connected to GCS bucket: {self.bucket_name}")
            
            # Set up lifecycle management if enabled
            if Config.GCS_ENABLE_LIFECYCLE:
                self._setup_lifecycle_policy()
                
        except NotFound:
            logger.error(f"GCS bucket '{self.bucket_name}' not found")
            raise
        except Exception as e:
            logger.error(f"Failed to access GCS bucket '{self.bucket_name}': {e}")
            raise
    
    def _setup_lifecycle_policy(self):
        """Set up lifecycle policy for temporary files"""
        try:
            lifecycle_rule = {
                "action": {"type": "Delete"},
                "condition": {
                    "age": Config.GCS_TEMP_FILE_RETENTION_DAYS,
                    "matchesPrefix": ["temp/", "processing/"]
                }
            }
            
            # Get current lifecycle rules
            current_rules = list(self.bucket.lifecycle_rules)
            
            # Check if our rule already exists
            rule_exists = any(
                rule.action.get("type") == "Delete" and 
                rule.condition.get("age") == Config.GCS_TEMP_FILE_RETENTION_DAYS
                for rule in current_rules
            )
            
            if not rule_exists:
                current_rules.append(lifecycle_rule)
                self.bucket.lifecycle_rules = current_rules
                self.bucket.patch()
                logger.info(f"Set up lifecycle policy: delete temp files after {Config.GCS_TEMP_FILE_RETENTION_DAYS} days")
                
        except Exception as e:
            logger.warning(f"Failed to set up lifecycle policy: {e}")
    
    def upload_file(self, local_path: str, gcs_path: str, content_type: Optional[str] = None) -> str:
        """
        Upload a file to GCS
        
        Args:
            local_path: Local file path
            gcs_path: GCS object path (without gs:// prefix)
            content_type: MIME type of the file
            
        Returns:
            GCS URI (gs://bucket/path)
        """
        try:
            if not self.bucket:
                raise ValueError("GCS bucket not initialized")
            
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local file not found: {local_path}")
            
            blob = self.bucket.blob(gcs_path)
            
            # Set content type if provided
            if content_type:
                blob.content_type = content_type
            
            # Upload file
            blob.upload_from_filename(local_path)
            
            gcs_uri = f"gs://{self.bucket_name}/{gcs_path}"
            logger.info(f"Uploaded {local_path} to {gcs_uri}")
            
            return gcs_uri
            
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to GCS: {e}")
            raise
    
    def download_file(self, gcs_path: str, local_path: str) -> str:
        """
        Download a file from GCS
        
        Args:
            gcs_path: GCS object path (without gs:// prefix)
            local_path: Local destination path
            
        Returns:
            Local file path
        """
        try:
            if not self.bucket:
                raise ValueError("GCS bucket not initialized")
            
            # Create local directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            blob = self.bucket.blob(gcs_path)
            
            if not blob.exists():
                raise FileNotFoundError(f"GCS object not found: gs://{self.bucket_name}/{gcs_path}")
            
            blob.download_to_filename(local_path)
            
            logger.info(f"Downloaded gs://{self.bucket_name}/{gcs_path} to {local_path}")
            
            return local_path
            
        except Exception as e:
            logger.error(f"Failed to download {gcs_path} from GCS: {e}")
            raise
    
    def upload_from_string(self, content: str, gcs_path: str, content_type: str = "text/plain") -> str:
        """
        Upload string content to GCS
        
        Args:
            content: String content to upload
            gcs_path: GCS object path
            content_type: MIME type
            
        Returns:
            GCS URI
        """
        try:
            if not self.bucket:
                raise ValueError("GCS bucket not initialized")
            
            blob = self.bucket.blob(gcs_path)
            
            # Upload string content with the specified content type
            blob.upload_from_string(content, content_type=content_type)
            
            gcs_uri = f"gs://{self.bucket_name}/{gcs_path}"
            logger.info(f"Uploaded string content to {gcs_uri}")
            
            return gcs_uri
            
        except Exception as e:
            logger.error(f"Failed to upload string to GCS: {e}")
            raise
    
    def download_as_string(self, gcs_path: str) -> str:
        """
        Download GCS object as string
        
        Args:
            gcs_path: GCS object path
            
        Returns:
            File content as string
        """
        try:
            if not self.bucket:
                raise ValueError("GCS bucket not initialized")
            
            blob = self.bucket.blob(gcs_path)
            
            if not blob.exists():
                raise FileNotFoundError(f"GCS object not found: gs://{self.bucket_name}/{gcs_path}")
            
            content = blob.download_as_text()
            logger.info(f"Downloaded gs://{self.bucket_name}/{gcs_path} as string")
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to download {gcs_path} as string: {e}")
            raise
    
    def delete_file(self, gcs_path: str) -> bool:
        """
        Delete a file from GCS
        
        Args:
            gcs_path: GCS object path
            
        Returns:
            True if deleted, False if not found
        """
        try:
            if not self.bucket:
                raise ValueError("GCS bucket not initialized")
            
            blob = self.bucket.blob(gcs_path)
            
            if blob.exists():
                blob.delete()
                logger.info(f"Deleted gs://{self.bucket_name}/{gcs_path}")
                return True
            else:
                logger.warning(f"GCS object not found for deletion: gs://{self.bucket_name}/{gcs_path}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete {gcs_path} from GCS: {e}")
            raise
    
    def delete_folder(self, folder_prefix: str) -> int:
        """
        Delete all objects with a given prefix (folder)
        
        Args:
            folder_prefix: Folder prefix to delete
            
        Returns:
            Number of objects deleted
        """
        try:
            if not self.bucket:
                raise ValueError("GCS bucket not initialized")
            
            # Ensure prefix ends with /
            if not folder_prefix.endswith('/'):
                folder_prefix += '/'
            
            blobs = self.bucket.list_blobs(prefix=folder_prefix)
            deleted_count = 0
            
            for blob in blobs:
                blob.delete()
                deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} objects with prefix: {folder_prefix}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete folder {folder_prefix} from GCS: {e}")
            raise
    
    def file_exists(self, gcs_path: str) -> bool:
        """
        Check if a file exists in GCS
        
        Args:
            gcs_path: GCS object path
            
        Returns:
            True if file exists
        """
        try:
            if not self.bucket:
                return False
            
            blob = self.bucket.blob(gcs_path)
            return blob.exists()
            
        except Exception as e:
            logger.error(f"Failed to check if {gcs_path} exists in GCS: {e}")
            return False
    
    def get_file_info(self, gcs_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file information from GCS
        
        Args:
            gcs_path: GCS object path
            
        Returns:
            Dictionary with file info or None if not found
        """
        try:
            if not self.bucket:
                return None
            
            blob = self.bucket.blob(gcs_path)
            
            if not blob.exists():
                return None
            
            blob.reload()
            
            return {
                'name': blob.name,
                'size': blob.size,
                'content_type': blob.content_type,
                'created': blob.time_created,
                'updated': blob.updated,
                'etag': blob.etag,
                'md5_hash': blob.md5_hash,
                'crc32c': blob.crc32c
            }
            
        except Exception as e:
            logger.error(f"Failed to get info for {gcs_path}: {e}")
            return None
    
    def list_files(self, prefix: str = "", max_results: int = 1000) -> List[str]:
        """
        List files in GCS bucket with optional prefix
        
        Args:
            prefix: Object prefix to filter by
            max_results: Maximum number of results
            
        Returns:
            List of object names
        """
        try:
            if not self.bucket:
                return []
            
            blobs = self.bucket.list_blobs(prefix=prefix, max_results=max_results)
            return [blob.name for blob in blobs]
            
        except Exception as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            return []
    
    def generate_signed_url(self, gcs_path: str, expiration_minutes: int = 60) -> Optional[str]:
        """
        Generate a signed URL for temporary access to a GCS object
        
        Args:
            gcs_path: GCS object path
            expiration_minutes: URL expiration time in minutes
            
        Returns:
            Signed URL or None if failed
        """
        try:
            if not self.bucket:
                return None
            
            # Use the enhanced URL generator
            from modules.gcs_url_generator import get_signed_url
            
            expiration_seconds = expiration_minutes * 60
            url = get_signed_url(self.bucket_name, gcs_path, expiration_seconds)
            
            logger.info(f"Generated URL for {gcs_path} (expires in {expiration_minutes} minutes)")
            return url
            
        except Exception as e:
            logger.error(f"Failed to generate URL for {gcs_path}: {e}")
            return None
    
    def get_download_url_info(self, gcs_path: str, expiration_minutes: int = 60) -> dict:
        """
        Get comprehensive download URL information with fallback handling
        
        Args:
            gcs_path: GCS object path
            expiration_minutes: URL expiration time in minutes
            
        Returns:
            Dictionary with URL and metadata
        """
        try:
            if not self.bucket:
                return {
                    'url': None,
                    'type': 'error',
                    'expires_in_minutes': 0,
                    'requires_auth': False,
                    'error': 'GCS bucket not initialized'
                }
            
            from modules.gcs_url_generator import get_download_url_with_fallback
            
            expiration_seconds = expiration_minutes * 60
            result = get_download_url_with_fallback(self.bucket_name, gcs_path, expiration_seconds)
            
            # Convert seconds to minutes for consistency
            result['expires_in_minutes'] = result.get('expires_in_seconds', 0) // 60
            
            logger.info(f"Generated {result['type']} for {gcs_path}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get download URL info for {gcs_path}: {e}")
            return {
                'url': None,
                'type': 'error',
                'expires_in_minutes': 0,
                'requires_auth': False,
                'error': str(e)
            }
    
    def get_gcs_uri(self, gcs_path: str) -> str:
        """
        Get the full GCS URI for a path
        
        Args:
            gcs_path: GCS object path
            
        Returns:
            Full GCS URI (gs://bucket/path)
        """
        return f"gs://{self.bucket_name}/{gcs_path}"
    
    def parse_gcs_uri(self, gcs_uri: str) -> tuple:
        """
        Parse a GCS URI into bucket and path components
        
        Args:
            gcs_uri: Full GCS URI (gs://bucket/path)
            
        Returns:
            Tuple of (bucket_name, object_path)
        """
        if not gcs_uri.startswith('gs://'):
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")
        
        parts = gcs_uri[5:].split('/', 1)
        bucket_name = parts[0]
        object_path = parts[1] if len(parts) > 1 else ""
        
        return bucket_name, object_path
