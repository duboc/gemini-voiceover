import os
import numpy as np
import torch
import torchaudio
import soundfile as sf
import logging
from typing import Tuple, Dict, Optional
from pathlib import Path
import tempfile
import subprocess
from config import Config

# Set up logging
logger = logging.getLogger(__name__)


class AudioSeparator:
    def __init__(self):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Audio separator initialized with device: {self.device}")
        
    def separate_audio(self, audio_file_path: str, model_name: str, output_dir: str) -> Dict[str, str]:
        """
        Separate audio using Demucs with intelligent fallback
        Returns dictionary with paths to separated audio files
        """
        try:
            logger.info(f"Starting Demucs audio separation with model: {model_name}")
            logger.info(f"Input file: {audio_file_path}")
            
            # Validate input file
            if not os.path.exists(audio_file_path):
                raise Exception(f"Audio file not found: {audio_file_path}")
            
            # Create output directory for Demucs
            demucs_output_dir = os.path.join(output_dir, "demucs_output")
            os.makedirs(demucs_output_dir, exist_ok=True)
            
            # Run Demucs separation
            separated_files = self._run_demucs_separation(
                audio_file_path, model_name, demucs_output_dir
            )
            
            # Assess separation quality
            quality_score = self._assess_separation_quality(separated_files)
            logger.info(f"Separation quality score: {quality_score:.3f}")
            
            # Check if separation meets quality threshold
            if quality_score < Config.SEPARATION_QUALITY_THRESHOLD:
                logger.warning(f"Low separation quality detected: {quality_score:.3f}")
                if Config.ENABLE_FALLBACK:
                    logger.info("Quality below threshold, will recommend fallback to replace_all mode")
                    # Still return the files but mark quality as poor
                    separated_files['_quality_score'] = quality_score
                    separated_files['_recommend_fallback'] = True
                else:
                    raise Exception("Separation quality below threshold and fallback disabled")
            else:
                separated_files['_quality_score'] = quality_score
                separated_files['_recommend_fallback'] = False
            
            return separated_files
            
        except Exception as e:
            logger.error(f"Demucs separation failed: {str(e)}", exc_info=True)
            # Return fallback indication
            return {
                '_separation_failed': True,
                '_recommend_fallback': True,
                '_error': str(e)
            }
    
    def _run_demucs_separation(self, audio_file_path: str, model_name: str, output_dir: str) -> Dict[str, str]:
        """
        Run Demucs separation using command line interface
        """
        try:
            # Map model names to Demucs model identifiers
            model_mapping = {
                'htdemucs': 'htdemucs',
                'mdx_extra': 'mdx_extra',
                'mdx': 'mdx'
            }
            
            demucs_model = model_mapping.get(model_name, 'htdemucs')
            logger.info(f"Using Demucs model: {demucs_model}")
            
            # Prepare Demucs command with correct syntax
            cmd = [
                'python', '-m', 'demucs.separate',
                '-n', demucs_model,  # Use -n for model name
                '-o', output_dir,    # Use -o for output directory
                audio_file_path      # Audio file as positional argument
            ]
            
            # Add device specification
            if self.device == 'cuda':
                cmd.extend(['-d', 'cuda'])
            else:
                cmd.extend(['-d', 'cpu'])
            
            logger.info(f"Running Demucs command: {' '.join(cmd)}")
            
            # Run Demucs separation
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Demucs command failed: {result.stderr}")
                raise Exception(f"Demucs separation failed: {result.stderr}")
            
            logger.info("Demucs separation completed successfully")
            
            # Find the output files - Demucs creates subdirectories by model name
            audio_filename = Path(audio_file_path).stem
            
            # Try different possible output structures
            possible_paths = [
                os.path.join(output_dir, demucs_model, audio_filename),  # model/track/
                os.path.join(output_dir, audio_filename),                # track/
                os.path.join(output_dir, "separated", demucs_model, audio_filename)  # separated/model/track/
            ]
            
            track_dir = None
            for path in possible_paths:
                if os.path.exists(path):
                    track_dir = path
                    logger.info(f"Found Demucs output directory: {track_dir}")
                    break
            
            if not track_dir:
                # List what's actually in the output directory for debugging
                logger.error(f"Could not find Demucs output. Contents of {output_dir}:")
                for item in os.listdir(output_dir):
                    item_path = os.path.join(output_dir, item)
                    if os.path.isdir(item_path):
                        logger.error(f"  Directory: {item}")
                        for subitem in os.listdir(item_path):
                            logger.error(f"    {subitem}")
                    else:
                        logger.error(f"  File: {item}")
                raise Exception("Could not locate Demucs output files")
            
            separated_files = {}
            
            # Look for standard Demucs outputs
            expected_stems = ['vocals', 'bass', 'drums', 'other']
            for stem in expected_stems:
                stem_file = os.path.join(track_dir, f"{stem}.wav")
                if os.path.exists(stem_file):
                    separated_files[stem] = stem_file
                    file_size = os.path.getsize(stem_file)
                    logger.info(f"Found {stem}: {stem_file} ({file_size} bytes)")
            
            # Create accompaniment by combining non-vocal stems
            if len(separated_files) > 1 and 'vocals' in separated_files:
                accompaniment_path = self._create_accompaniment(separated_files, track_dir)
                separated_files['accompaniment'] = accompaniment_path
            
            if not separated_files:
                raise Exception("No separated audio files found in Demucs output")
            
            return separated_files
            
        except subprocess.TimeoutExpired:
            logger.error("Demucs separation timed out")
            raise Exception("Audio separation timed out (>10 minutes)")
        except Exception as e:
            logger.error(f"Demucs separation error: {e}")
            raise Exception(f"Demucs separation failed: {str(e)}")
    
    def _create_accompaniment(self, separated_files: Dict[str, str], output_dir: str) -> str:
        """
        Create accompaniment track by combining non-vocal stems
        """
        try:
            logger.info("Creating accompaniment track from non-vocal stems")
            
            # Load all non-vocal stems
            accompaniment_audio = None
            sample_rate = None
            
            for stem_name, stem_path in separated_files.items():
                if stem_name != 'vocals' and os.path.exists(stem_path):
                    audio, sr = torchaudio.load(stem_path)
                    
                    if sample_rate is None:
                        sample_rate = sr
                        accompaniment_audio = audio
                    else:
                        # Ensure same sample rate and length
                        if sr != sample_rate:
                            audio = torchaudio.functional.resample(audio, sr, sample_rate)
                        
                        # Ensure same length
                        min_length = min(accompaniment_audio.shape[1], audio.shape[1])
                        accompaniment_audio = accompaniment_audio[:, :min_length]
                        audio = audio[:, :min_length]
                        
                        # Add to accompaniment
                        accompaniment_audio = accompaniment_audio + audio
            
            if accompaniment_audio is not None:
                # Normalize to prevent clipping
                max_val = torch.max(torch.abs(accompaniment_audio))
                if max_val > 0.95:
                    accompaniment_audio = accompaniment_audio * (0.95 / max_val)
                    logger.info("Applied normalization to accompaniment track")
                
                # Save accompaniment
                accompaniment_path = os.path.join(output_dir, "accompaniment.wav")
                torchaudio.save(accompaniment_path, accompaniment_audio, sample_rate)
                
                file_size = os.path.getsize(accompaniment_path)
                logger.info(f"Created accompaniment: {accompaniment_path} ({file_size} bytes)")
                
                return accompaniment_path
            else:
                raise Exception("No non-vocal stems found to create accompaniment")
                
        except Exception as e:
            logger.error(f"Failed to create accompaniment: {e}")
            raise Exception(f"Accompaniment creation failed: {str(e)}")
    
    def mix_audio_tracks(self, vocals_path: str, music_path: str, output_path: str, 
                        vocal_balance: float = 0.5) -> str:
        """
        Mix vocal and music tracks with specified balance using FFmpeg for reliability
        vocal_balance: 0.0 = all music, 1.0 = all vocals, 0.5 = balanced
        """
        try:
            logger.info(f"Mixing audio tracks with vocal balance: {vocal_balance}")
            logger.info(f"Vocals: {vocals_path}")
            logger.info(f"Music: {music_path}")
            
            # Validate input files
            if not os.path.exists(vocals_path):
                raise Exception(f"Vocals file not found: {vocals_path}")
            if not os.path.exists(music_path):
                raise Exception(f"Music file not found: {music_path}")
            
            vocals_size = os.path.getsize(vocals_path)
            music_size = os.path.getsize(music_path)
            logger.info(f"Input file sizes - Vocals: {vocals_size} bytes, Music: {music_size} bytes")
            
            # Use FFmpeg for reliable audio mixing
            import ffmpeg
            
            # Calculate volume levels for mixing with vocal emphasis
            # vocal_balance: 0.0 = all music, 1.0 = all vocals
            music_volume = (1.0 - vocal_balance) * 0.7  # Reduce music volume more
            vocal_volume = vocal_balance * 1.2  # Boost vocal volume
            
            # Ensure vocal volume doesn't exceed reasonable limits
            vocal_volume = min(vocal_volume, 1.5)
            
            logger.info(f"Enhanced mixing - Vocal volume: {vocal_volume:.2f}, Music volume: {music_volume:.2f}")
            
            # Create FFmpeg inputs
            vocals_input = ffmpeg.input(vocals_path)
            music_input = ffmpeg.input(music_path)
            
            # Apply volume adjustments and mix
            vocals_adjusted = vocals_input.filter('volume', vocal_volume)
            music_adjusted = music_input.filter('volume', music_volume)
            
            # Mix the two audio streams
            mixed = ffmpeg.filter([vocals_adjusted, music_adjusted], 'amix', inputs=2, duration='longest')
            
            # Output with high quality settings
            out = ffmpeg.output(mixed, output_path, acodec='pcm_s16le', ar=24000, ac=1)
            
            # Run the mixing process
            ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            
            # Validate output
            if not os.path.exists(output_path):
                raise Exception("Mixed audio file was not created")
            
            file_size = os.path.getsize(output_path)
            if file_size < 1000:
                raise Exception(f"Mixed audio file is too small: {file_size} bytes")
            
            logger.info(f"Successfully mixed audio: {output_path} ({file_size} bytes)")
            return output_path
            
        except Exception as e:
            logger.error(f"FFmpeg audio mixing failed: {str(e)}", exc_info=True)
            
            # Fallback to PyTorch mixing
            logger.info("Attempting fallback PyTorch mixing...")
            try:
                return self._mix_audio_tracks_pytorch(vocals_path, music_path, output_path, vocal_balance)
            except Exception as fallback_error:
                logger.error(f"Fallback PyTorch mixing also failed: {fallback_error}")
                raise Exception(f"Both FFmpeg and PyTorch mixing failed. FFmpeg: {str(e)}, PyTorch: {str(fallback_error)}")
    
    def _mix_audio_tracks_pytorch(self, vocals_path: str, music_path: str, output_path: str, 
                                 vocal_balance: float = 0.5) -> str:
        """
        Fallback mixing method using PyTorch/torchaudio
        """
        try:
            logger.info("Using PyTorch fallback for audio mixing")
            
            # Load audio files with torchaudio
            vocals_audio, vocals_sr = torchaudio.load(vocals_path)
            music_audio, music_sr = torchaudio.load(music_path)
            
            logger.info(f"Loaded vocals: {vocals_audio.shape} at {vocals_sr}Hz")
            logger.info(f"Loaded music: {music_audio.shape} at {music_sr}Hz")
            
            # Choose target sample rate (prefer higher quality)
            target_sr = max(vocals_sr, music_sr)
            
            # Resample if needed
            if vocals_sr != target_sr:
                vocals_audio = torchaudio.functional.resample(vocals_audio, vocals_sr, target_sr)
                logger.info(f"Resampled vocals to {target_sr}Hz")
            
            if music_sr != target_sr:
                music_audio = torchaudio.functional.resample(music_audio, music_sr, target_sr)
                logger.info(f"Resampled music to {target_sr}Hz")
            
            # Handle channel differences
            if vocals_audio.shape[0] != music_audio.shape[0]:
                # Convert to mono if needed
                if vocals_audio.shape[0] > 1:
                    vocals_audio = torch.mean(vocals_audio, dim=0, keepdim=True)
                if music_audio.shape[0] > 1:
                    music_audio = torch.mean(music_audio, dim=0, keepdim=True)
                logger.info("Converted to mono for channel compatibility")
            
            # Ensure same length (use longer duration)
            max_length = max(vocals_audio.shape[1], music_audio.shape[1])
            
            # Pad shorter audio with silence
            if vocals_audio.shape[1] < max_length:
                padding = max_length - vocals_audio.shape[1]
                vocals_audio = torch.nn.functional.pad(vocals_audio, (0, padding))
                logger.info(f"Padded vocals with {padding} samples")
            
            if music_audio.shape[1] < max_length:
                padding = max_length - music_audio.shape[1]
                music_audio = torch.nn.functional.pad(music_audio, (0, padding))
                logger.info(f"Padded music with {padding} samples")
            
            # Apply volume balance
            music_gain = 1.0 - vocal_balance
            vocal_gain = vocal_balance
            
            logger.info(f"Applying gains - Vocals: {vocal_gain:.2f}, Music: {music_gain:.2f}")
            
            # Mix tracks
            mixed_audio = (vocals_audio * vocal_gain) + (music_audio * music_gain)
            
            # Normalize to prevent clipping
            max_amplitude = torch.max(torch.abs(mixed_audio))
            if max_amplitude > 0.95:
                mixed_audio = mixed_audio * (0.95 / max_amplitude)
                logger.info(f"Applied normalization (max was {max_amplitude:.3f})")
            
            # Save mixed audio
            torchaudio.save(output_path, mixed_audio, target_sr)
            
            file_size = os.path.getsize(output_path)
            logger.info(f"PyTorch mixed audio saved: {output_path} ({file_size} bytes)")
            
            return output_path
            
        except Exception as e:
            logger.error(f"PyTorch audio mixing failed: {str(e)}", exc_info=True)
            raise Exception(f"PyTorch audio mixing failed: {str(e)}")
    
    def _assess_separation_quality(self, separated_files: Dict[str, str]) -> float:
        """
        Assess the quality of Demucs separation
        Returns a score between 0 and 1 (higher is better)
        """
        try:
            if 'vocals' not in separated_files or 'accompaniment' not in separated_files:
                logger.warning("Missing vocals or accompaniment for quality assessment")
                return 0.2
            
            # Load vocals and accompaniment
            vocals_audio, _ = torchaudio.load(separated_files['vocals'])
            accompaniment_audio, _ = torchaudio.load(separated_files['accompaniment'])
            
            # Calculate energy metrics
            vocals_energy = torch.mean(vocals_audio ** 2).item()
            accompaniment_energy = torch.mean(accompaniment_audio ** 2).item()
            
            # Calculate signal-to-noise ratio approximation
            total_energy = vocals_energy + accompaniment_energy
            if total_energy > 0:
                # Good separation should have reasonable energy in both components
                energy_balance = min(vocals_energy, accompaniment_energy) / total_energy
                
                # Additional quality checks
                vocals_peak = torch.max(torch.abs(vocals_audio)).item()
                accompaniment_peak = torch.max(torch.abs(accompaniment_audio)).item()
                
                # Check for reasonable dynamic range
                dynamic_range_score = min(vocals_peak, accompaniment_peak) / max(vocals_peak, accompaniment_peak)
                
                # Combine metrics
                quality_score = (energy_balance * 2 + dynamic_range_score) / 2
                return min(quality_score, 1.0)
            
            return 0.3
            
        except Exception as e:
            logger.warning(f"Quality assessment failed: {e}")
            return 0.3
    
    def validate_separation_result(self, separated_files: Dict[str, str], model_name: str) -> bool:
        """
        Validate that Demucs separation produced usable results
        """
        try:
            # Check for separation failure indicators
            if separated_files.get('_separation_failed', False):
                logger.error("Separation marked as failed")
                return False
            
            # Check for required components
            required_components = ['vocals']
            
            for component in required_components:
                if component not in separated_files:
                    logger.error(f"Missing component: {component}")
                    return False
                
                file_path = separated_files[component]
                if not os.path.exists(file_path):
                    logger.error(f"Component file not found: {file_path}")
                    return False
                
                file_size = os.path.getsize(file_path)
                if file_size < 10000:  # Less than 10KB indicates likely failure
                    logger.error(f"Component file too small: {file_path} ({file_size} bytes)")
                    return False
            
            # Check quality score if available
            quality_score = separated_files.get('_quality_score', 0.5)
            if quality_score < Config.SEPARATION_QUALITY_THRESHOLD:
                logger.warning(f"Separation quality below threshold: {quality_score}")
                return False
            
            logger.info("Demucs separation validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Separation validation failed: {e}")
            return False
    
    def get_background_music(self, separated_files: Dict[str, str], model_name: str) -> str:
        """
        Get the background music track from Demucs separated components
        """
        # Prefer accompaniment if available, otherwise try to create from stems
        if 'accompaniment' in separated_files:
            return separated_files['accompaniment']
        
        # If no accompaniment, try to find other stems to combine
        available_stems = [k for k in separated_files.keys() 
                          if k not in ['vocals', '_quality_score', '_recommend_fallback', '_separation_failed', '_error']]
        
        if available_stems:
            # Return the first non-vocal stem as background
            return separated_files[available_stems[0]]
        
        return None
    
    def should_use_fallback(self, separated_files: Dict[str, str]) -> bool:
        """
        Determine if fallback to replace_all mode should be used
        """
        return separated_files.get('_recommend_fallback', False) or separated_files.get('_separation_failed', False)
