"""
Whisper.cpp integration for AIOP
"""

import ctypes
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from ..core import logging, exceptions, utils
from .model_manager import get_model_path, ModelManager

logger = logging.get_logger(__name__)


@dataclass
class WhisperParameters:
    """Whisper.cpp parameters"""
    n_threads: int = 4
    n_max_threads: int = 4
    print_special: bool = False
    print_progress: bool = False
    print_realtime: bool = False
    print_timestamps: bool = False
    translate: bool = False
    language: Optional[str] = None
    detect_language: bool = False
    diarize: bool = False
    n_max_text_ctx: int = 16384
    split_on_word: bool = False
    audio_ctx: int = 0
    speed_up: bool = False
    debug_mode: bool = False
    prompt: Optional[str] = None
    prompt_tokens: Optional[List[int]] = None
    suppress_blank: bool = True
    suppress_non_speech_tokens: bool = False
    temperature: float = 0.0
    max_len: int = 0
    clip_timestamps: List[float] = field(default_factory=list)
    skip_special_tokens: bool = False
    initial_prompt: Optional[str] = None


@dataclass
class WhisperResult:
    """Whisper transcription result"""
    text: str
    start_time: float = 0.0
    end_time: float = 0.0
    language: Optional[str] = None
    tokens: Optional[List[int]] = None
    confidence: float = 0.0


class WhisperCPP:
    """Whisper.cpp wrapper for speech recognition"""
    
    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        library_path: Optional[str] = None,
        parameters: WhisperParameters = None,
    ):
        self.model_path = Path(model_path) if model_path else None
        self.library_path = library_path or self._find_library()
        self.parameters = parameters or WhisperParameters()
        self.lib: Optional[ctypes.CDLL] = None
        self.ctx: Optional[ctypes.c_void_p] = None
        self.state: Optional[ctypes.c_void_p] = None
        self._is_loaded = False
        self._load_library()
    
    def _find_library(self) -> str:
        """Find whisper.cpp library"""
        # Try common locations
        possible_paths = [
            "whisper.dll",
            "whisper.cpp/whisper.dll",
            "libwhisper.dll",
            "/usr/local/lib/libwhisper.so",
            "whisper.so",
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                return path
        
        # Try in the models directory
        models_dir = utils.get_models_dir()
        whisper_path = models_dir / "whisper.dll"
        if whisper_path.exists():
            return str(whisper_path)
        
        raise exceptions.SpeechError(
            "whisper.cpp library not found. Please download from "
            "https://github.com/ggerganov/whisper.cpp and place whisper.dll in the models directory."
        )
    
    def _load_library(self) -> None:
        """Load whisper.cpp library"""
        if not Path(self.library_path).exists():
            raise exceptions.SpeechError(f"Whisper library not found: {self.library_path}")
        
        try:
            self.lib = ctypes.CDLL(self.library_path)
            self._setup_functions()
            logger.info(f"Loaded whisper.cpp library: {self.library_path}")
        except Exception as e:
            raise exceptions.SpeechError(f"Failed to load whisper.cpp library: {e}")
    
    def _setup_functions(self) -> None:
        """Set up function prototypes"""
        # Context functions
        self.lib.whisper_init_from_file_with_params.argtypes = [
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        self.lib.whisper_init_from_file_with_params.restype = ctypes.c_void_p
        
        self.lib.whisper_init_from_file.argtypes = [ctypes.c_char_p]
        self.lib.whisper_init_from_file.restype = ctypes.c_void_p
        
        self.lib.whisper_free.argtypes = [ctypes.c_void_p]
        self.lib.whisper_free.restype = None
        
        # State functions
        self.lib.whisper_init_state.argtypes = [ctypes.c_void_p]
        self.lib.whisper_init_state.restype = ctypes.c_void_p
        
        self.lib.whisper_free_state.argtypes = [ctypes.c_void_p]
        self.lib.whisper_free_state.restype = None
        
        # Processing functions
        self.lib.whisper_full.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
        ]
        self.lib.whisper_full.restype = ctypes.c_int
        
        self.lib.whisper_full_with_state.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
        ]
        self.lib.whisper_full_with_state.restype = ctypes.c_int
        
        self.lib.whisper_chunk.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
        ]
        self.lib.whisper_chunk.restype = ctypes.c_int
        
        self.lib.whisper_chunk_state.argtypes = [ctypes.c_void_p]
        self.lib.whisper_chunk_state.restype = ctypes.c_void_p
        
        # Parameter functions
        self.lib.whisper_set_mel.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_float),
        ]
        self.lib.whisper_set_mel.restype = None
        
        # Text functions
        self.lib.whisper_token_to_str.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        self.lib.whisper_token_to_str.restype = ctypes.c_char_p
        
        self.lib.whisper_lang_id.argtypes = [ctypes.c_int]
        self.lib.whisper_lang_id.restype = ctypes.c_char_p
        
        # Language functions
        self.lib.whisper_lang_max_id.argtypes = []
        self.lib.whisper_lang_max_id.restype = ctypes.c_int
        
        self.lib.whisper_lang_str.argtypes = [ctypes.c_int]
        self.lib.whisper_lang_str.restype = ctypes.c_char_p
    
    def load_model(self, model_path: Optional[Union[str, Path]] = None) -> None:
        """Load whisper model"""
        if model_path:
            self.model_path = Path(model_path)
        
        if not self.model_path:
            # Try to find a default model
            model_manager = ModelManager()
            model_path = model_manager.get_model_path("base.en")
            if model_path:
                self.model_path = model_path
            else:
                raise exceptions.SpeechError("No model path specified and no default model found")
        
        if not self.model_path.exists():
            raise exceptions.SpeechError(f"Model file not found: {self.model_path}")
        
        # Free existing context
        if self.ctx:
            self.lib.whisper_free(self.ctx)
            self.ctx = None
        
        # Load model
        model_path_bytes = str(self.model_path).encode('utf-8')
        self.ctx = self.lib.whisper_init_from_file(model_path_bytes)
        
        if not self.ctx:
            raise exceptions.SpeechError(f"Failed to load model: {self.model_path}")
        
        # Initialize state
        self.state = self.lib.whisper_init_state(self.ctx)
        
        self._is_loaded = True
        logger.info(f"Loaded whisper model: {self.model_path}")
    
    def unload_model(self) -> None:
        """Unload whisper model"""
        if self.state:
            self.lib.whisper_free_state(self.state)
            self.state = None
        
        if self.ctx:
            self.lib.whisper_free(self.ctx)
            self.ctx = None
        
        self._is_loaded = False
        logger.info("Unloaded whisper model")
    
    def transcribe(
        self,
        audio_data: Union[bytes, np.ndarray],
        sample_rate: int = 16000,
        language: Optional[str] = None,
        translate: bool = False,
        temperature: float = 0.0,
        max_len: int = 0,
    ) -> str:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Audio data (bytes or numpy array)
            sample_rate: Sample rate of audio data
            language: Language code (e.g., "en")
            translate: Whether to translate to English
            temperature: Sampling temperature
            max_len: Maximum token length
        
        Returns:
            Transcribed text
        """
        if not self.ctx:
            self.load_model()
        
        # Convert audio data
        if isinstance(audio_data, bytes):
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
        else:
            audio_array = audio_data.astype(np.float32)
        
        # Set parameters
        params = self._create_params(
            n_threads=self.parameters.n_threads,
            translate=translate,
            language=language,
            temperature=temperature,
            max_len=max_len,
        )
        
        # Process audio
        result = self._process_audio(audio_array, params)
        return result
    
    def _create_params(self, **kwargs) -> ctypes.c_void_p:
        """Create whisper parameters"""
        # This is a simplified version
        # In practice, we'd create a proper params struct
        class Params(ctypes.Structure):
            _fields_ = [
                ("n_threads", ctypes.c_int),
                ("n_max_threads", ctypes.c_int),
                ("print_special", ctypes.c_bool),
                ("print_progress", ctypes.c_bool),
                ("print_realtime", ctypes.c_bool),
                ("print_timestamps", ctypes.c_bool),
                ("translate", ctypes.c_bool),
                ("language", ctypes.c_char_p),
                ("detect_language", ctypes.c_bool),
                ("diarize", ctypes.c_bool),
                ("n_max_text_ctx", ctypes.c_int),
                ("split_on_word", ctypes.c_bool),
                ("audio_ctx", ctypes.c_int),
                ("speed_up", ctypes.c_bool),
                ("debug_mode", ctypes.c_bool),
                ("prompt", ctypes.c_char_p),
                ("temperature", ctypes.c_float),
                ("max_len", ctypes.c_int),
            ]
        
        params = Params()
        for key, value in kwargs.items():
            if hasattr(params, key):
                setattr(params, key, value)
        
        return ctypes.byref(params)
    
    def _process_audio(
        self,
        audio_array: np.ndarray,
        params: ctypes.c_void_p,
    ) -> str:
        """Process audio with whisper"""
        # Convert to int16 if needed
        if audio_array.dtype != np.int16:
            audio_array = (audio_array * 32767).astype(np.int16)
        
        # Get array pointer
        audio_ptr = audio_array.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        
        # Process
        result = self.lib.whisper_full(
            self.ctx,
            params,
            audio_ptr,
            len(audio_array),
        )
        
        if result != 0:
            raise exceptions.SpeechError(f"Whisper processing failed with code: {result}")
        
        # Get result text
        n_segments = self.lib.whisper_full_n_segments(self.ctx)
        text_parts = []
        
        for i in range(n_segments):
            text_ptr = self.lib.whisper_full_get_segment_text(self.ctx, i)
            text = ctypes.c_char_p(text_ptr).value.decode('utf-8')
            text_parts.append(text)
        
        return ' '.join(text_parts)
    
    def transcribe_streaming(
        self,
        audio_generator: Generator[bytes, None, None],
        sample_rate: int = 16000,
        language: Optional[str] = None,
        callback: Optional[callable] = None,
    ) -> str:
        """
        Transcribe audio stream
        
        Args:
            audio_generator: Generator yielding audio chunks
            sample_rate: Sample rate of audio data
            language: Language code
            callback: Optional callback for partial results
        
        Returns:
            Final transcribed text
        """
        if not self.ctx:
            self.load_model()
        
        full_text = ""
        audio_buffer = bytearray()
        
        for audio_chunk in audio_generator:
            audio_buffer.extend(audio_chunk)
            
            # Process in chunks
            if len(audio_buffer) >= sample_rate:  # Process every 1 second
                text = self.transcribe(
                    bytes(audio_buffer),
                    sample_rate=sample_rate,
                    language=language,
                )
                
                if text and text != full_text:
                    full_text = text
                    if callback:
                        callback(text)
                
                audio_buffer = bytearray()
        
        # Process remaining audio
        if audio_buffer:
            text = self.transcribe(
                bytes(audio_buffer),
                sample_rate=sample_rate,
                language=language,
            )
            if text:
                full_text = text
        
        return full_text
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self._is_loaded
    
    def get_model_path(self) -> Optional[Path]:
        """Get current model path"""
        return self.model_path
    
    def set_language(self, language: str) -> None:
        """Set language for transcription"""
        self.parameters.language = language
    
    def set_translate(self, translate: bool) -> None:
        """Set translate option"""
        self.parameters.translate = translate
    
    def set_temperature(self, temperature: float) -> None:
        """Set sampling temperature"""
        self.parameters.temperature = temperature
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unload_model()


class WhisperModel:
    """High-level whisper model wrapper"""
    
    def __init__(
        self,
        model_name: str = "base.en",
        library_path: Optional[str] = None,
    ):
        self.model_name = model_name
        self.library_path = library_path
        self.whisper: Optional[WhisperCPP] = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load the whisper model"""
        model_path = get_model_path(self.model_name)
        if not model_path:
            # Try to download
            from .model_manager import download_model
            if not download_model(self.model_name):
                raise exceptions.SpeechError(f"Model not found and failed to download: {self.model_name}")
            model_path = get_model_path(self.model_name)
        
        self.whisper = WhisperCPP(
            model_path=model_path,
            library_path=self.library_path,
        )
    
    def transcribe(
        self,
        audio_data: Union[bytes, np.ndarray],
        sample_rate: int = 16000,
        language: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Transcribe audio to text"""
        if not self.whisper:
            self._load_model()
        
        return self.whisper.transcribe(
            audio_data,
            sample_rate=sample_rate,
            language=language,
            **kwargs,
        )
    
    def transcribe_file(
        self,
        file_path: Union[str, Path],
        language: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Transcribe audio file"""
        try:
            import soundfile as sf
            data, sample_rate = sf.read(file_path)
            return self.transcribe(data, sample_rate=sample_rate, language=language, **kwargs)
        except ImportError:
            # Fallback to raw file reading
            with open(file_path, 'rb') as f:
                data = f.read()
            return self.transcribe(data, sample_rate=16000, language=language, **kwargs)
    
    def transcribe_streaming(
        self,
        audio_generator: Generator[bytes, None, None],
        sample_rate: int = 16000,
        language: Optional[str] = None,
        callback: Optional[callable] = None,
    ) -> str:
        """Transcribe audio stream"""
        if not self.whisper:
            self._load_model()
        
        return self.whisper.transcribe_streaming(
            audio_generator,
            sample_rate=sample_rate,
            language=language,
            callback=callback,
        )
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.whisper is not None and self.whisper.is_loaded()
    
    def unload(self) -> None:
        """Unload model"""
        if self.whisper:
            self.whisper.unload_model()
            self.whisper = None


# Global whisper instance
_whisper: Optional[WhisperModel] = None


def get_whisper_model(model_name: str = "base.en") -> WhisperModel:
    """Get the global whisper model instance"""
    global _whisper
    if _whisper is None or _whisper.model_name != model_name:
        _whisper = WhisperModel(model_name)
    return _whisper


def transcribe(
    audio_data: Union[bytes, np.ndarray],
    model_name: str = "base.en",
    language: Optional[str] = None,
    **kwargs,
) -> str:
    """Transcribe audio to text"""
    model = get_whisper_model(model_name)
    return model.transcribe(audio_data, language=language, **kwargs)


def transcribe_file(
    file_path: Union[str, Path],
    model_name: str = "base.en",
    language: Optional[str] = None,
    **kwargs,
) -> str:
    """Transcribe audio file"""
    model = get_whisper_model(model_name)
    return model.transcribe_file(file_path, language=language, **kwargs)
