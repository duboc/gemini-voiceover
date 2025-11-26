import os
import logging
import subprocess
from typing import List, Tuple, Dict
from config import Config

# Set up logging
logger = logging.getLogger(__name__)


class AudioSynchronizer:
    """Handle audio synchronization and timing adjustments"""
    
    def __init__(self):
        """Initialize audio synchronizer"""
        self.enable_sync = Config.ENABLE_AUDIO_SYNC
        self.max_difference = Config.MAX_TIMING_DIFFERENCE_SEC
        self.sync_method = Config.SYNC_METHOD
        self.max_stretch_factor = getattr(Config, 'MAX_SPEAKING_RATE', 1.2)  # Max speed up (1.2x)
        self.min_stretch_factor = getattr(Config, 'MIN_SPEAKING_RATE', 0.8)  # Max slow down (0.8x)
        logger.info(f"Audio Synchronizer initialized: enabled={self.enable_sync}, method={self.sync_method}, max_stretch={self.max_stretch_factor}")
    
    def synchronize_segments(
        self,
        audio_files: List[str],
        expected_timings: List[Tuple[float, float]],
        output_dir: str
    ) -> List[str]:
        """
        Synchronize audio segments to match expected timings
        
        Args:
            audio_files: List of audio file paths
            expected_timings: List of (start_time, end_time) tuples
            output_dir: Directory to save synchronized files
            
        Returns:
            List of synchronized audio file paths
        """
        if not self.enable_sync:
            logger.info("Audio synchronization disabled, returning original files")
            return audio_files
        
        try:
            logger.info(f"Synchronizing {len(audio_files)} audio segments")
            synchronized_files = []
            
            for i, (audio_file, (start_time, end_time)) in enumerate(zip(audio_files, expected_timings)):
                expected_duration = end_time - start_time
                actual_duration = self._get_audio_duration(audio_file)
                
                time_difference = abs(actual_duration - expected_duration)
                
                logger.info(f"Segment {i}: expected={expected_duration:.2f}s, actual={actual_duration:.2f}s, diff={time_difference:.2f}s")
                
                # If timing is close enough, no adjustment needed
                if time_difference <= self.max_difference:
                    logger.info(f"Segment {i}: timing acceptable, no adjustment needed")
                    synchronized_files.append(audio_file)
                    continue
                
                # Apply synchronization based on method
                synced_file = self._apply_synchronization(
                    audio_file,
                    actual_duration,
                    expected_duration,
                    i,
                    output_dir
                )
                
                synchronized_files.append(synced_file)
            
            logger.info(f"Synchronization complete: {len(synchronized_files)} files processed")
            return synchronized_files
            
        except Exception as e:
            logger.error(f"Synchronization failed: {e}", exc_info=True)
            # Return original files if synchronization fails
            return audio_files
    
    def _apply_synchronization(
        self,
        audio_file: str,
        actual_duration: float,
        expected_duration: float,
        segment_index: int,
        output_dir: str
    ) -> str:
        """
        Apply synchronization to a single audio segment
        
        Args:
            audio_file: Path to audio file
            actual_duration: Actual duration in seconds
            expected_duration: Expected duration in seconds
            segment_index: Index of the segment
            output_dir: Output directory
            
        Returns:
            Path to synchronized audio file
        """
        try:
            output_file = os.path.join(output_dir, f"synced_segment_{segment_index:03d}.wav")
            
            if self.sync_method == 'stretch':
                # Time-stretch the audio to match expected duration
                return self._stretch_audio(audio_file, actual_duration, expected_duration, output_file)
            
            elif self.sync_method == 'pad':
                # Add silence to match expected duration
                return self._pad_audio(audio_file, actual_duration, expected_duration, output_file)
            
            elif self.sync_method == 'trim':
                # Trim or speed up to match expected duration
                if actual_duration > expected_duration:
                    return self._trim_audio(audio_file, expected_duration, output_file)
                else:
                    return self._pad_audio(audio_file, actual_duration, expected_duration, output_file)
            
            else:
                logger.warning(f"Unknown sync method: {self.sync_method}, using original file")
                return audio_file
                
        except Exception as e:
            logger.error(f"Failed to synchronize segment {segment_index}: {e}")
            return audio_file
    
    def _stretch_audio(
        self,
        input_file: str,
        actual_duration: float,
        expected_duration: float,
        output_file: str
    ) -> str:
        """
        Time-stretch audio using FFmpeg's atempo filter
        
        Args:
            input_file: Input audio file
            actual_duration: Actual duration
            expected_duration: Expected duration
            output_file: Output file path
            
        Returns:
            Path to stretched audio file
        """
        try:
            # Calculate stretch factor (tempo change)
            tempo = actual_duration / expected_duration
            
            # Check if tempo exceeds natural limits
            if tempo > self.max_stretch_factor:
                logger.warning(f"Required tempo {tempo:.2f}x exceeds max {self.max_stretch_factor:.2f}x. Limiting stretch.")
                tempo = self.max_stretch_factor
            elif tempo < self.min_stretch_factor:
                logger.warning(f"Required tempo {tempo:.2f}x below min {self.min_stretch_factor:.2f}x. Limiting stretch.")
                tempo = self.min_stretch_factor
            
            # FFmpeg atempo filter supports 0.5 to 2.0, so we may need to chain filters
            tempo_filters = []
            remaining_tempo = tempo
            
            while remaining_tempo > 2.0:
                tempo_filters.append("atempo=2.0")
                remaining_tempo /= 2.0
            
            while remaining_tempo < 0.5:
                tempo_filters.append("atempo=0.5")
                remaining_tempo /= 0.5
            
            if remaining_tempo != 1.0:
                tempo_filters.append(f"atempo={remaining_tempo:.4f}")
            
            filter_chain = ",".join(tempo_filters)
            
            logger.info(f"Stretching audio: tempo={tempo:.4f}, filters={filter_chain}")
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_file,
                '-af', filter_chain,
                '-acodec', 'pcm_s16le',
                '-ar', '24000',
                output_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg stretch failed: {result.stderr}")
                return input_file
            
            logger.info(f"Audio stretched successfully: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to stretch audio: {e}")
            return input_file
    
    def _pad_audio(
        self,
        input_file: str,
        actual_duration: float,
        expected_duration: float,
        output_file: str
    ) -> str:
        """
        Pad audio with silence to match expected duration
        
        Args:
            input_file: Input audio file
            actual_duration: Actual duration
            expected_duration: Expected duration
            output_file: Output file path
            
        Returns:
            Path to padded audio file
        """
        try:
            pad_duration = expected_duration - actual_duration
            
            if pad_duration <= 0:
                # No padding needed
                import shutil
                shutil.copy(input_file, output_file)
                return output_file
            
            logger.info(f"Padding audio with {pad_duration:.2f}s of silence")
            
            # Add silence at the end
            cmd = [
                'ffmpeg', '-y',
                '-i', input_file,
                '-af', f'apad=pad_dur={pad_duration:.3f}',
                '-acodec', 'pcm_s16le',
                '-ar', '24000',
                output_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg pad failed: {result.stderr}")
                return input_file
            
            logger.info(f"Audio padded successfully: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to pad audio: {e}")
            return input_file
    
    def _trim_audio(
        self,
        input_file: str,
        expected_duration: float,
        output_file: str
    ) -> str:
        """
        Trim audio to match expected duration
        
        Args:
            input_file: Input audio file
            expected_duration: Expected duration
            output_file: Output file path
            
        Returns:
            Path to trimmed audio file
        """
        try:
            logger.info(f"Trimming audio to {expected_duration:.2f}s")
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_file,
                '-t', str(expected_duration),
                '-acodec', 'pcm_s16le',
                '-ar', '24000',
                output_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg trim failed: {result.stderr}")
                return input_file
            
            logger.info(f"Audio trimmed successfully: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to trim audio: {e}")
            return input_file
    
    def _get_audio_duration(self, audio_file: str) -> float:
        """
        Get duration of audio file using FFmpeg
        
        Args:
            audio_file: Path to audio file
            
        Returns:
            Duration in seconds
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return duration
            else:
                logger.error(f"FFprobe failed: {result.stderr}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 0.0
    
    def analyze_timing_accuracy(
        self,
        audio_files: List[str],
        expected_timings: List[Tuple[float, float]]
    ) -> Dict:
        """
        Analyze timing accuracy of audio segments
        
        Args:
            audio_files: List of audio file paths
            expected_timings: List of (start_time, end_time) tuples
            
        Returns:
            Dictionary with timing analysis
        """
        try:
            total_difference = 0.0
            max_difference = 0.0
            segments_out_of_sync = 0
            
            timing_data = []
            
            for i, (audio_file, (start_time, end_time)) in enumerate(zip(audio_files, expected_timings)):
                expected_duration = end_time - start_time
                actual_duration = self._get_audio_duration(audio_file)
                difference = abs(actual_duration - expected_duration)
                
                required_tempo = actual_duration / expected_duration if expected_duration > 0 else 1.0
                
                timing_data.append({
                    'segment': i,
                    'expected_duration': expected_duration,
                    'actual_duration': actual_duration,
                    'difference': difference,
                    'required_tempo': required_tempo,
                    'needs_shortening': required_tempo > self.max_stretch_factor,
                    'in_sync': difference <= self.max_difference
                })
                
                total_difference += difference
                max_difference = max(max_difference, difference)
                
                if difference > self.max_difference:
                    segments_out_of_sync += 1
            
            avg_difference = total_difference / len(audio_files) if audio_files else 0.0
            
            analysis = {
                'total_segments': len(audio_files),
                'segments_in_sync': len(audio_files) - segments_out_of_sync,
                'segments_out_of_sync': segments_out_of_sync,
                'average_difference': avg_difference,
                'max_difference': max_difference,
                'sync_threshold': self.max_difference,
                'timing_data': timing_data
            }
            
            logger.info(f"Timing analysis: {segments_out_of_sync}/{len(audio_files)} segments out of sync, avg diff: {avg_difference:.2f}s")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze timing accuracy: {e}")
            return {
                'total_segments': 0,
                'segments_in_sync': 0,
                'segments_out_of_sync': 0,
                'average_difference': 0.0,
                'max_difference': 0.0,
                'sync_threshold': self.max_difference,
                'timing_data': []
            }
