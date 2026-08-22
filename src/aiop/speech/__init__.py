"""
Speech recognition for AIOP
"""

from .whisper_cpp import WhisperCPP, WhisperModel
from .model_manager import ModelManager
from .transcriber import SpeechTranscriber, TranscriptionResult, TranscriptionConfig, get_transcriber
from . import language

__all__ = [
    "WhisperCPP",
    "WhisperModel",
    "ModelManager",
    "SpeechTranscriber",
    "get_transcriber",
    "TranscriptionResult",
    "TranscriptionConfig",
    "language",
]
