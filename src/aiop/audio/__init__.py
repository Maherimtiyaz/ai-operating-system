"""
Audio engine for AIOP
"""

from .capture import AudioCapture, AudioStream, AudioChunk, AudioParameters, AudioFormat, get_audio_capture, start_audio_capture, stop_audio_capture
from .processing import VoiceActivityDetector, AudioProcessor, VADConfig, ProcessingResult, get_audio_processor
from .playback import AudioPlayback
from . import devices

__all__ = [
    "AudioCapture",
    "AudioStream",
    "AudioChunk",
    "AudioParameters",
    "AudioFormat",
    "VoiceActivityDetector",
    "AudioProcessor",
    "VADConfig",
    "ProcessingResult",
    "AudioPlayback",
    "devices",
    "get_audio_capture",
    "start_audio_capture",
    "stop_audio_capture",
    "get_audio_processor",
]
