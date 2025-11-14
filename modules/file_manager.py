import os
import uuid
import shutil
import logging
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from config import Config

logger = logging.getLogger(__name__)


class FileManager:
    def __init__(self):
        # Ensure directories exist
        Config.validate_config()
        
        # Initialize storage backend
        self.storage_backend = Config.STORAGE_BACKEND
        self.gcs_client = None
        
        if self.storage_backend == 'gcs':
            try:
                from modules.gcs_client import GCSClient
                self.gcs_client = GCSClient()
                logger.info("Initialized GCS storage backend")
            except Exception as e:
                logger.error(f"Failed to initialize GCS client: {e}")
                logger.warning("Falling back to local storage")
                self.storage_backend = 'local'
        else:
            logger.info("Using local storage backend")
    
    def save_uploaded_file(self, file, file_type="video") -> str:
        """Save uploaded file and return the file path or GCS URI"""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            original_filename = secure_filename(file.filename)
            name, ext = os.path.splitext(original_filename)
            
            filename = f"{timestamp}_{unique_id}_{name}{ext}"
            
            if self.storage_backend == 'gcs' and self.gcs_client:
                # Save to GCS
                if file_type == "video":
                    gcs_path = f"uploads/{filename}"
                else:
                    gcs_path = f"temp/{filename}"
                
                # Save locally first, then upload to GCS
                local_temp_path = os.path.join("/tmp", filename)
                file.save(local_temp_path)
                
                # Determine content type
                content_type = None
                if ext.lower() in ['.mp4', '.mov']:
                    content_type = f"video/{ext[1:]}"
                elif ext.lower() in ['.wav', '.mp3']:
                    content_type = f"audio/{ext[1:]}"
                
                gcs_uri = self.gcs_client.upload_file(local_temp_path, gcs_path, content_type)
                
                # Clean up local temp file
                os.remove(local_temp_path)
                
                logger.info(f"Uploaded {filename} to GCS: {gcs_uri}")
                return gcs_uri
            else:
                # Save locally
                if file_type == "video":
                    save_dir = Config.UPLOAD_FOLDER
                else:
                    save_dir = Config.TEMP_FOLDER
                
                file_path = os.path.join(save_dir, filename)
                file.save(file_path)
                
                return file_path
            
        except Exception as e:
            raise Exception(f"File save failed: {str(e)}")
    
    def create_temp_directory(self, prefix="processing") -> str:
        """Create a temporary directory for processing"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            dir_name = f"{prefix}_{timestamp}_{unique_id}"
            
            temp_dir = os.path.join(Config.TEMP_FOLDER, dir_name)
            os.makedirs(temp_dir, exist_ok=True)
            
            return temp_dir
            
        except Exception as e:
            raise Exception(f"Temp directory creation failed: {str(e)}")
    
    def save_output_file(self, source_path: str, original_filename: str) -> str:
        """Save final output file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(original_filename)
            
            output_filename = f"{name}_translated_{timestamp}{ext}"
            
            if self.storage_backend == 'gcs' and self.gcs_client:
                # Upload to GCS
                gcs_path = f"outputs/{output_filename}"
                content_type = f"video/{ext[1:]}" if ext.lower() in ['.mp4', '.mov'] else None
                gcs_uri = self.gcs_client.upload_file(source_path, gcs_path, content_type)
                
                logger.info(f"Uploaded output file to GCS: {gcs_uri}")
                return gcs_uri
            else:
                # Save locally
                output_path = os.path.join(Config.OUTPUT_FOLDER, output_filename)
                shutil.copy2(source_path, output_path)
                return output_path
            
        except Exception as e:
            raise Exception(f"Output file save failed: {str(e)}")
    
    def cleanup_temp_files(self, temp_dir: str = None):
        """Clean up temporary files"""
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            # Clean up old temp files
            self._cleanup_old_files(Config.TEMP_FOLDER)
            self._cleanup_old_files(Config.UPLOAD_FOLDER)
            
        except Exception as e:
            print(f"Cleanup warning: {str(e)}")
    
    def _cleanup_old_files(self, directory: str):
        """Remove files older than configured hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=Config.CLEANUP_TEMP_FILES_HOURS)
            
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    if file_time < cutoff_time:
                        os.remove(file_path)
                elif os.path.isdir(file_path):
                    dir_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    if dir_time < cutoff_time:
                        shutil.rmtree(file_path)
                        
        except Exception as e:
            print(f"Cleanup warning for {directory}: {str(e)}")
    
    def validate_file_extension(self, filename: str, allowed_extensions: set) -> bool:
        """Validate file extension"""
        if '.' not in filename:
            return False
        
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in allowed_extensions
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        try:
            return os.path.getsize(file_path)
        except:
            return 0
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists (local or GCS)"""
        if file_path.startswith('gs://'):
            # GCS file
            if self.gcs_client:
                _, gcs_path = self.gcs_client.parse_gcs_uri(file_path)
                return self.gcs_client.file_exists(gcs_path)
            return False
        else:
            # Local file
            return os.path.exists(file_path) and os.path.isfile(file_path)
    
    def download_file(self, source_path: str, local_path: str) -> str:
        """Download file from GCS to local path if needed"""
        try:
            if source_path.startswith('gs://'):
                # Download from GCS
                if not self.gcs_client:
                    raise Exception("GCS client not available")
                
                _, gcs_path = self.gcs_client.parse_gcs_uri(source_path)
                return self.gcs_client.download_file(gcs_path, local_path)
            else:
                # Local file - just copy if different paths
                if source_path != local_path:
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    shutil.copy2(source_path, local_path)
                return local_path
                
        except Exception as e:
            raise Exception(f"File download failed: {str(e)}")
    
    def upload_file(self, local_path: str, gcs_path: str, content_type: str = None) -> str:
        """Upload local file to GCS"""
        try:
            if self.storage_backend == 'gcs' and self.gcs_client:
                return self.gcs_client.upload_file(local_path, gcs_path, content_type)
            else:
                raise Exception("GCS storage not configured")
                
        except Exception as e:
            raise Exception(f"File upload failed: {str(e)}")
    
    def save_artifact(self, content: str, filename: str, process_id: str, artifact_type: str = "json") -> str:
        """Save processing artifact (transcription, translation, etc.)"""
        try:
            gcs_path = f"artifacts/{process_id}/{artifact_type}/{filename}"
            
            if self.storage_backend == 'gcs' and self.gcs_client:
                # Save to GCS
                content_type = "application/json" if artifact_type == "json" else "text/plain"
                gcs_uri = self.gcs_client.upload_from_string(content, gcs_path, content_type)
                logger.info(f"Saved artifact to GCS: {gcs_uri}")
                return gcs_uri
            else:
                # Save locally
                artifact_dir = os.path.join(Config.TEMP_FOLDER, "artifacts", process_id, artifact_type)
                os.makedirs(artifact_dir, exist_ok=True)
                
                local_path = os.path.join(artifact_dir, filename)
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                logger.info(f"Saved artifact locally: {local_path}")
                return local_path
                
        except Exception as e:
            raise Exception(f"Artifact save failed: {str(e)}")
    
    def save_audio_segment(self, local_path: str, process_id: str, segment_name: str) -> str:
        """Save audio segment file"""
        try:
            if self.storage_backend == 'gcs' and self.gcs_client:
                # Upload to GCS
                gcs_path = f"processing/{process_id}/audio_segments/{segment_name}"
                content_type = "audio/wav"
                gcs_uri = self.gcs_client.upload_file(local_path, gcs_path, content_type)
                logger.info(f"Uploaded audio segment to GCS: {gcs_uri}")
                return gcs_uri
            else:
                # Keep local
                return local_path
                
        except Exception as e:
            logger.warning(f"Failed to save audio segment: {e}")
            return local_path
    
    def cleanup_processing_files(self, process_id: str):
        """Clean up all processing files for a specific process"""
        try:
            if self.storage_backend == 'gcs' and self.gcs_client:
                # Clean up GCS processing files
                processing_prefix = f"processing/{process_id}/"
                deleted_count = self.gcs_client.delete_folder(processing_prefix)
                logger.info(f"Cleaned up {deleted_count} GCS processing files for {process_id}")
            
            # Also clean up any local temp files
            local_processing_dir = os.path.join(Config.TEMP_FOLDER, process_id)
            if os.path.exists(local_processing_dir):
                shutil.rmtree(local_processing_dir)
                logger.info(f"Cleaned up local processing directory: {local_processing_dir}")
                
        except Exception as e:
            logger.warning(f"Cleanup warning for process {process_id}: {e}")
    
    def get_download_info(self, file_path: str) -> dict:
        """Get download information for a file (local path or enhanced URL for GCS)"""
        try:
            if file_path.startswith('gs://'):
                # GCS file - use enhanced URL generation
                if self.gcs_client:
                    _, gcs_path = self.gcs_client.parse_gcs_uri(file_path)
                    url_info = self.gcs_client.get_download_url_info(gcs_path, expiration_minutes=60)
                    
                    if url_info.get('url'):
                        return {
                            'type': 'gcs',
                            'url': url_info['url'],
                            'url_type': url_info['type'],
                            'expires_in_minutes': url_info.get('expires_in_minutes', 60),
                            'requires_auth': url_info.get('requires_auth', False),
                            'error': url_info.get('error')
                        }
                    else:
                        return {
                            'type': 'gcs',
                            'error': url_info.get('error', 'Failed to generate download URL')
                        }
                
                return {'type': 'gcs', 'error': 'GCS client not available'}
            else:
                # Local file
                return {
                    'type': 'local',
                    'path': file_path
                }
                
        except Exception as e:
            return {'type': 'error', 'error': str(e)}
