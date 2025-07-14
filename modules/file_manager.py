import os
import uuid
import shutil
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from config import Config


class FileManager:
    def __init__(self):
        # Ensure directories exist
        Config.validate_config()
    
    def save_uploaded_file(self, file, file_type="video") -> str:
        """Save uploaded file and return the file path"""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            original_filename = secure_filename(file.filename)
            name, ext = os.path.splitext(original_filename)
            
            filename = f"{timestamp}_{unique_id}_{name}{ext}"
            
            # Determine save directory
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
        """Check if file exists"""
        return os.path.exists(file_path) and os.path.isfile(file_path)
