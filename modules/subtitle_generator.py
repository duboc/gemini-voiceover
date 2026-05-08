"""Generate SRT subtitle files from translation segments.

Takes the same segment format used throughout the pipeline
(``start_time``, ``end_time``, ``text``) and writes a standard
SubRip (.srt) file suitable for FFmpeg burn-in via the ``subtitles``
video filter.
"""
from __future__ import annotations

import logging
import textwrap
from typing import Dict, List

logger = logging.getLogger(__name__)

MAX_LINE_WIDTH = 42


def _format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp ``HH:MM:SS,mmm``."""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _wrap_text(text: str, width: int = MAX_LINE_WIDTH) -> str:
    """Wrap long subtitle text into multiple lines for readability."""
    lines = textwrap.wrap(text, width=width)
    return "\n".join(lines) if lines else text


class SubtitleGenerator:
    """Generates SRT subtitle files from translation segments."""

    def generate_srt(self, segments: List[Dict], output_path: str) -> str:
        """Write an SRT file from translation segments.

        Parameters
        ----------
        segments : list[dict]
            Each dict must have ``start_time`` (float), ``end_time`` (float),
            and ``text`` (str).
        output_path : str
            Destination ``.srt`` file path.

        Returns
        -------
        str
            The *output_path* written to.
        """
        logger.info(f"Generating SRT with {len(segments)} segments -> {output_path}")

        lines: list[str] = []
        for idx, seg in enumerate(segments, start=1):
            start = _format_timestamp(seg["start_time"])
            end = _format_timestamp(seg["end_time"])
            text = _wrap_text(seg.get("text", ""))
            lines.append(f"{idx}")
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"SRT file written: {output_path} ({idx} entries)")
        return output_path
