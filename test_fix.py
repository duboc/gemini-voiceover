import os
import time
import logging
import uuid
from app import process_video, processing_status
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_fix")

def test_processing():
    video_path = "video2-small.mp4"
    if not os.path.exists(video_path):
        logger.error(f"Test video not found: {video_path}")
        return

    process_id = str(uuid.uuid4())
    processing_status[process_id] = {
        'status': 'started',
        'progress': 0,
        'message': 'Starting test...',
        'error': None,
        'result_file': None
    }

    logger.info(f"Starting processing for {process_id}")
    
    # Start processing in a separate thread (simulating app behavior)
    import threading
    thread = threading.Thread(
        target=process_video,
        args=(
            process_id, 
            video_path, 
            'pt-BR',  # Target language
            'Zephyr', # Voice
            'gemini', # Backend
            'htdemucs', # Separation
            'preserve_music', # Mode
            0.8, # Balance
            'video2-small.mp4' # Original filename
        )
    )
    thread.start()

    # Monitor status
    while True:
        status = processing_status[process_id]
        current_status = status.get('status')
        progress = status.get('progress')
        message = status.get('message')
        
        logger.info(f"Status: {current_status} ({progress}%) - {message}")
        
        if current_status == 'awaiting_review':
            logger.info("Status is awaiting_review. Auto-approving...")
            status['approved'] = True
            status['status'] = 'processing'
            status['message'] = 'Auto-approved for testing'
            
        if current_status == 'completed':
            logger.info("Processing completed successfully!")
            break
            
        if current_status == 'error':
            logger.error(f"Processing failed: {status.get('error')}")
            break
            
        time.sleep(5)

if __name__ == "__main__":
    test_processing()
