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
            
            # Use concatenation method which is more reliable for sequential voiceover
            # and avoids issues with complex filter graphs or mixing limits
            logger.info("Combining audio using concatenation method")
            
            try:
                self._fallback_concatenation(valid_audio_files, valid_timestamps, output_path, total_duration, sample_rate, channels)
                logger.info("Audio combination completed successfully")
                return output_path
            except Exception as e:
                logger.error(f"Concatenation failed: {e}")
                raise
            
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
                audio_bitrate=Config.OUTPUT_AUDIO_BITRATE,
                ac=Config.OUTPUT_AUDIO_CHANNELS,
                ar=Config.OUTPUT_AUDIO_SAMPLE_RATE,
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
    
    def replace_video_audio_with_subtitles(
        self, video_path: str, new_audio_path: str, srt_path: str, output_path: str,
    ) -> str:
        """Replace audio AND burn-in SRT subtitles into the video.

        Unlike ``replace_video_audio`` this re-encodes the video stream
        (libx264) because the ``subtitles`` filter requires decoded frames.
        """
        try:
            logger.info(
                f"Replacing audio + burning subtitles: video={video_path}, "
                f"audio={new_audio_path}, srt={srt_path}"
            )
            for p, label in ((video_path, "Video"), (new_audio_path, "Audio"), (srt_path, "SRT")):
                if not os.path.exists(p):
                    raise Exception(f"{label} file not found: {p}")

            # FFmpeg's subtitles filter needs the path escaped for its own
            # parser — colons and backslashes must be escaped.
            escaped_srt = srt_path.replace("\\", "\\\\").replace(":", "\\:")

            force_style = (
                f"FontName=Noto Sans CJK SC,"
                f"FontSize={Config.SUBTITLE_FONT_SIZE},"
                f"PrimaryColour={Config.SUBTITLE_FONT_COLOR},"
                f"OutlineColour={Config.SUBTITLE_OUTLINE_COLOR},"
                f"Outline={Config.SUBTITLE_OUTLINE_WIDTH},"
                f"Alignment=2"
            )

            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", new_audio_path,
                "-filter_complex",
                f"[0:v]subtitles='{escaped_srt}':force_style='{force_style}'[vout]",
                "-map", "[vout]",
                "-map", "1:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-c:a", "aac",
                "-b:a", Config.OUTPUT_AUDIO_BITRATE,
                "-ac", str(Config.OUTPUT_AUDIO_CHANNELS),
                "-ar", str(Config.OUTPUT_AUDIO_SAMPLE_RATE),
                "-strict", "experimental",
                output_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"FFmpeg subtitle burn-in failed: {result.stderr}")

            logger.info("Video audio+subtitle replacement completed successfully")
            return output_path

        except Exception as e:
            logger.error(f"Error during subtitle burn-in: {e}")
            raise Exception(f"Video subtitle burn-in failed: {str(e)}")

    def _get_segment_duration(self, audio_file: str) -> float:
        """Probe an audio file's duration in seconds. 0.0 on failure."""
        try:
            probe = ffmpeg.probe(audio_file)
            return float(probe['format']['duration'])
        except Exception as e:
            logger.warning(f"Could not probe duration for {audio_file}: {e}")
            return 0.0

    @staticmethod
    def _build_concat_timeline(
        audio_files: List[str],
        timestamps: List[Tuple[float, float]],
        actual_durations: List[float],
        total_duration: float,
    ) -> dict:
        """Pure planning step: decide silences and truncations without I/O.

        Returns a dict with:
          - silences: {segment_idx -> duration} for pre-segment gap fills
          - truncations: {segment_idx -> max_duration} for segments that
            would overrun their slot or push past total_duration
          - final_silence: trailing silence to reach total_duration
          - final_current_time: timeline cursor after the last segment
        """
        silences: dict = {}
        truncations: dict = {}
        current_time = 0.0

        for idx, ((start_time, end_time), actual) in enumerate(zip(timestamps, actual_durations)):
            slot = max(0.0, end_time - start_time)
            # Pre-segment silence only when there's a real forward gap
            if start_time > current_time + 1e-6:
                silences[idx] = start_time - current_time

            # Truncate if actual audio overflows this slot
            if actual > slot + 1e-6:
                truncations[idx] = slot

            # Cap at total_duration
            projected_end = start_time + min(actual, truncations.get(idx, actual))
            if projected_end > total_duration + 1e-6:
                truncations[idx] = max(0.0, total_duration - start_time)

            # Always advance to expected end_time so downstream gaps are correct
            current_time = end_time

        final_silence = max(0.0, total_duration - current_time)
        return {
            "silences": silences,
            "truncations": truncations,
            "final_silence": final_silence,
            "final_current_time": current_time,
        }

    def _fallback_concatenation(self, valid_audio_files: List[str], valid_timestamps: List[Tuple[float, float]],
                               output_path: str, total_duration: float, sample_rate: int, channels: int) -> str:
        """Fallback method using simple concatenation with silence padding.

        Drift-safe: a) advances the timeline cursor by each segment's
        EXPECTED duration regardless of how long the rendered audio is,
        and b) truncates overrunning segments (with a tiny fade-out to
        avoid clicks) so they cannot bleed into the next slot.
        """
        try:
            logger.info("Using fallback concatenation method")

            actual_durations = [self._get_segment_duration(f) for f in valid_audio_files]
            plan = self._build_concat_timeline(
                valid_audio_files, valid_timestamps, actual_durations, total_duration,
            )

            segment_files: List[str] = []
            temp_files: List[str] = []
            channel_layout = "mono" if channels == 1 else "stereo"

            def _make_silence(seconds: float, name: str) -> str:
                silence_path = os.path.join(Config.TEMP_FOLDER, name)
                temp_files.append(silence_path)
                (
                    ffmpeg
                    .input(f'anullsrc=channel_layout={channel_layout}:sample_rate={sample_rate}',
                           f='lavfi', t=seconds)
                    .output(silence_path, acodec='pcm_s16le', ar=sample_rate, ac=channels)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                return silence_path

            def _trim_with_fade(src: str, max_seconds: float, name: str) -> str:
                """Trim with a 10ms fade-out to avoid audible click on cut."""
                trimmed_path = os.path.join(Config.TEMP_FOLDER, name)
                temp_files.append(trimmed_path)
                fade_dur = 0.01
                fade_start = max(0.0, max_seconds - fade_dur)
                cmd = [
                    'ffmpeg', '-y',
                    '-i', src,
                    '-t', str(max_seconds),
                    '-af', f'afade=t=out:st={fade_start:.4f}:d={fade_dur:.4f}',
                    '-acodec', 'pcm_s16le',
                    '-ar', str(sample_rate),
                    '-ac', str(channels),
                    trimmed_path,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"Trim failed for {src}, using original: {result.stderr}")
                    return src
                return trimmed_path

            for idx, (audio_file, (start_time, end_time)) in enumerate(zip(valid_audio_files, valid_timestamps)):
                if idx in plan["silences"]:
                    s = plan["silences"][idx]
                    logger.info(f"Adding {s:.3f}s silence before segment {idx}")
                    segment_files.append(_make_silence(s, f"silence_{idx}.wav"))

                if idx in plan["truncations"]:
                    cap = plan["truncations"][idx]
                    logger.warning(
                        f"Segment {idx} overruns slot ({actual_durations[idx]:.3f}s > {cap:.3f}s); "
                        f"trimming with 10ms fade-out"
                    )
                    segment_files.append(_trim_with_fade(audio_file, cap, f"trim_{idx}.wav"))
                else:
                    segment_files.append(audio_file)

            if plan["final_silence"] > 1e-6:
                logger.info(f"Adding {plan['final_silence']:.3f}s final silence")
                segment_files.append(_make_silence(plan["final_silence"], "final_silence.wav"))
            
            # Concatenate all segments
            logger.info(f"Concatenating {len(segment_files)} audio segments")
            
            # Create concat file list
            concat_file = os.path.join(Config.TEMP_FOLDER, "concat_list.txt")
            temp_files.append(concat_file)
            
            with open(concat_file, 'w') as f:
                for segment_file in segment_files:
                    f.write(f"file '{os.path.abspath(segment_file)}'\n")
            
            # Build output kwargs, optionally adding a single loudnorm pass
            # so per-segment TTS loudness variation is smoothed out without
            # paying for two-pass measurement overhead.
            output_kwargs = dict(acodec='pcm_s16le', ar=sample_rate, ac=channels)
            if Config.ENABLE_LOUDNORM:
                output_kwargs['af'] = (
                    f"loudnorm=I={Config.LOUDNORM_TARGET_I}"
                    f":TP={Config.LOUDNORM_TP}:LRA={Config.LOUDNORM_LRA}"
                )
                logger.info(f"Applying loudnorm filter: {output_kwargs['af']}")

            (
                ffmpeg
                .input(concat_file, format='concat', safe=0)
                .output(output_path, **output_kwargs)
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
