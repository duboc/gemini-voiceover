import os
import subprocess
import ffmpeg
import logging
from typing import Tuple, List
from config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoProcessor:
    def __init__(self):
        pass
    
    def extract_audio(self, video_path: str, output_path: str) -> str:
        """Extract audio from video file with high quality"""
        try:
            logger.info(f"Extracting audio from {video_path} to {output_path}")
            
            # Use ffmpeg to extract audio with higher quality
            (
                ffmpeg
                .input(video_path)
                .output(output_path, acodec='pcm_s16le', ac=2, ar='44100')  # Stereo, 44.1kHz
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            logger.info(f"Audio extraction completed successfully")
            return output_path
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error during audio extraction: {e.stderr.decode()}")
            raise Exception(f"Audio extraction failed: {e.stderr.decode()}")
        except Exception as e:
            logger.error(f"Unexpected error during audio extraction: {str(e)}")
            raise Exception(f"Audio extraction failed: {str(e)}")
    
    def get_video_info(self, video_path: str) -> dict:
        """Get video information including duration"""
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
            
            duration = float(probe['format']['duration'])
            
            info = {
                'duration': duration,
                'video_codec': video_stream['codec_name'] if video_stream else None,
                'audio_codec': audio_stream['codec_name'] if audio_stream else None,
                'width': int(video_stream['width']) if video_stream else None,
                'height': int(video_stream['height']) if video_stream else None,
                'fps': eval(video_stream['r_frame_rate']) if video_stream else None
            }
            
            return info
        except Exception as e:
            raise Exception(f"Failed to get video info: {str(e)}")
    
    def combine_audio_segments(self, audio_files: List[str], timestamps: List[Tuple[float, float]], 
                              output_path: str, total_duration: float) -> str:
        """Combine audio segments with proper timing and quality preservation"""
        try:
            logger.info(f"Combining {len(audio_files)} audio segments for duration {total_duration}s")
            
            # Validate input files and get audio properties from first valid file
            valid_audio_files = []
            valid_timestamps = []
            sample_rate = 24000  # Default Google Cloud TTS sample rate
            channels = 1  # Default mono
            
            for i, (audio_file, timestamp) in enumerate(zip(audio_files, timestamps)):
                if os.path.exists(audio_file):
                    file_size = os.path.getsize(audio_file)
                    logger.info(f"Audio segment {i}: {audio_file} ({file_size} bytes) at {timestamp}")
                    valid_audio_files.append(audio_file)
                    valid_timestamps.append(timestamp)
                    
                    # Get audio properties from first file
                    if i == 0:
                        try:
                            probe = ffmpeg.probe(audio_file)
                            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
                            if audio_stream:
                                sample_rate = int(audio_stream['sample_rate'])
                                channels = int(audio_stream['channels'])
                                logger.info(f"Detected audio format: {sample_rate}Hz, {channels} channels")
                        except Exception as e:
                            logger.warning(f"Could not detect audio properties, using defaults: {e}")
                else:
                    logger.warning(f"Audio segment {i} not found: {audio_file}")
            
            if not valid_audio_files:
                logger.warning("No valid audio files found, creating silent track")
                # Create a silent audio track with proper format
                (
                    ffmpeg
                    .input(f'anullsrc=channel_layout={"mono" if channels == 1 else "stereo"}:sample_rate={sample_rate}', 
                           f='lavfi', t=total_duration)
                    .output(output_path, acodec='pcm_s16le', ar=sample_rate, ac=channels)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                return output_path
            
            # Use the most reliable approach - build a proper filter complex
            logger.info("Creating combined audio using filter complex approach")
            
            try:
                # Build inputs list
                inputs = []
                
                # Add silent base track
                inputs.append(ffmpeg.input(
                    f'anullsrc=channel_layout={"mono" if channels == 1 else "stereo"}:sample_rate={sample_rate}', 
                    f='lavfi', t=total_duration
                ))
                
                # Add all audio files
                for audio_file in valid_audio_files:
                    inputs.append(ffmpeg.input(audio_file))
                
                # Build filter complex string
                filter_parts = []
                
                # Apply delays to each audio segment
                for i, (start_time, end_time) in enumerate(valid_timestamps):
                    delay_ms = int(start_time * 1000)
                    if delay_ms > 0:
                        # Apply delay to the audio segment
                        filter_parts.append(f'[{i+1}:a]adelay={delay_ms}|{delay_ms}[delayed{i}]')
                    else:
                        # No delay needed, just label it
                        filter_parts.append(f'[{i+1}:a]acopy[delayed{i}]')
                
                # Mix all delayed segments with the silent base
                mix_inputs = '[0:a]'  # Start with silent base
                for i in range(len(valid_audio_files)):
                    mix_inputs += f'[delayed{i}]'
                
                # Create the final mix
                filter_parts.append(f'{mix_inputs}amix=inputs={len(valid_audio_files) + 1}:duration=longest:dropout_transition=0:weights=1 {"2 " * len(valid_audio_files)}[out]')
                
                # Join all filter parts
                filter_complex = ';'.join(filter_parts)
                
                logger.info(f"Using filter complex: {filter_complex[:300]}...")
                
                # Run FFmpeg with the complex filter
                out = ffmpeg.output(
                    *inputs,
                    output_path,
                    filter_complex=filter_complex,
                    map='[out]',
                    acodec='pcm_s16le',
                    ar=sample_rate,
                    ac=channels
                ).overwrite_output()
                
                ffmpeg.run(out, capture_stdout=True, capture_stderr=True)
                logger.info("Audio combination completed successfully")
                
            except Exception as complex_error:
                logger.warning(f"Single-pass mixing failed: {complex_error}")
                logger.info("Falling back to simple concatenation method")
                
                # Fallback to simple concatenation
                self._fallback_concatenation(valid_audio_files, valid_timestamps, output_path, total_duration, sample_rate, channels)
            
            logger.info("Audio combination completed successfully with quality preservation")
            return output_path
            
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error during audio combination: {e.stderr.decode()}")
            raise Exception(f"Audio combination failed: {e.stderr.decode()}")
        except Exception as e:
            logger.error(f"Unexpected error during audio combination: {str(e)}")
            raise Exception(f"Audio combination failed: {str(e)}")
    
    def replace_video_audio(self, video_path: str, new_audio_path: str, output_path: str) -> str:
        """Replace video audio with new audio track"""
        try:
            logger.info(f"Replacing audio in {video_path} with {new_audio_path}")
            
            # Verify input files exist
            if not os.path.exists(video_path):
                raise Exception(f"Video file not found: {video_path}")
            if not os.path.exists(new_audio_path):
                raise Exception(f"Audio file not found: {new_audio_path}")
            
            video_input = ffmpeg.input(video_path)
            audio_input = ffmpeg.input(new_audio_path)
            
            out = ffmpeg.output(
                video_input['v'],
                audio_input['a'],
                output_path,
                vcodec='copy',
                acodec='aac',
                strict='experimental'
            ).overwrite_output()
            
            ffmpeg.run(out, capture_stdout=True, capture_stderr=True)
            
            logger.info("Video audio replacement completed successfully")
            return output_path
            
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error during video audio replacement: {e.stderr.decode()}")
            raise Exception(f"Video audio replacement failed: {e.stderr.decode()}")
        except Exception as e:
            logger.error(f"Unexpected error during video audio replacement: {str(e)}")
            raise Exception(f"Video audio replacement failed: {str(e)}")
    
    def _fallback_concatenation(self, valid_audio_files: List[str], valid_timestamps: List[Tuple[float, float]], 
                               output_path: str, total_duration: float, sample_rate: int, channels: int) -> str:
        """Fallback method using simple concatenation with silence padding"""
        try:
            logger.info("Using fallback concatenation method")
            
            # Create segments with proper timing
            segment_files = []
            current_time = 0.0
            temp_files = []  # Track temp files for cleanup
            
            for i, (audio_file, (start_time, end_time)) in enumerate(zip(valid_audio_files, valid_timestamps)):
                # Add silence before this segment if needed
                if start_time > current_time:
                    silence_duration = start_time - current_time
                    silence_file = os.path.join(Config.TEMP_FOLDER, f"silence_{i}.wav")
                    temp_files.append(silence_file)
                    
                    logger.info(f"Adding {silence_duration}s silence before segment {i}")
                    
                    (
                        ffmpeg
                        .input(f'anullsrc=channel_layout={"mono" if channels == 1 else "stereo"}:sample_rate={sample_rate}', 
                               f='lavfi', t=silence_duration)
                        .output(silence_file, acodec='pcm_s16le', ar=sample_rate, ac=channels)
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True)
                    )
                    segment_files.append(silence_file)
                
                # Add the actual audio segment
                segment_files.append(audio_file)
                current_time = end_time
            
            # Add final silence if needed
            if current_time < total_duration:
                final_silence_duration = total_duration - current_time
                final_silence_file = os.path.join(Config.TEMP_FOLDER, "final_silence.wav")
                temp_files.append(final_silence_file)
                
                logger.info(f"Adding {final_silence_duration}s final silence")
                
                (
                    ffmpeg
                    .input(f'anullsrc=channel_layout={"mono" if channels == 1 else "stereo"}:sample_rate={sample_rate}', 
                           f='lavfi', t=final_silence_duration)
                    .output(final_silence_file, acodec='pcm_s16le', ar=sample_rate, ac=channels)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                segment_files.append(final_silence_file)
            
            # Concatenate all segments
            logger.info(f"Concatenating {len(segment_files)} audio segments")
            
            # Create concat file list
            concat_file = os.path.join(Config.TEMP_FOLDER, "concat_list.txt")
            temp_files.append(concat_file)
            
            with open(concat_file, 'w') as f:
                for segment_file in segment_files:
                    f.write(f"file '{os.path.abspath(segment_file)}'\n")
            
            # Use concat demuxer
            (
                ffmpeg
                .input(concat_file, format='concat', safe=0)
                .output(output_path, acodec='pcm_s16le', ar=sample_rate, ac=channels)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
            
            logger.info("Fallback concatenation completed successfully")
            return output_path
            
        except Exception as e:
            logger.error(f"Fallback concatenation failed: {e}")
            raise Exception(f"Fallback concatenation failed: {str(e)}")

    def validate_video_file(self, file_path: str) -> bool:
        """Validate if file is a supported video format"""
        try:
            probe = ffmpeg.probe(file_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            return video_stream is not None
        except:
            return False
