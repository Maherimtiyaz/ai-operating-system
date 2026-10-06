"""
Whisper.cpp integration for AIOP
"""

import ctypes
import math
import os
import subprocess
import tempfile
import threading
import wave
import numpy as np
from pathlib import Path
from typing import Optional, List, Any, Union, Generator
from dataclasses import dataclass, field
from ..core import logging, exceptions, utils
from .model_manager import get_model_path, ModelManager

logger = logging.get_logger(__name__)

# whisper.cpp 1.9.3 ABI -------------------------------------------------
#
# The structs below mirror include/whisper.h from the whisper.cpp release the
# bundled models/whisper.dll was built from. They must stay field-for-field
# identical: whisper_full() takes whisper_full_params *by value*, so a layout
# mismatch corrupts the call instead of failing loudly.

WHISPER_SAMPLE_RATE = 16000

# The conv encoder halves the mel spectrogram, so one encoder position covers
# 20 ms and the model accepts 1500 of them (30 s of audio).
ENCODER_POSITIONS_PER_SECOND = 50
MAX_AUDIO_CTX = 1500

# Head-room added on top of the exact content (200 positions == 4 s). Too
# little and the decoder runs out of audio and loops on the tail of the
# utterance, which is both wrong and extremely slow.
AUDIO_CTX_MARGIN = 200

_SAMPLING_GREEDY = 0

# os.add_dll_directory() returns a handle that unregisters the directory when
# garbage collected, so every handle taken here must outlive the library.
_dll_directory_handles: List[Any] = []
_registered_backend_dirs: set = set()


class _VADParams(ctypes.Structure):
    _fields_ = [
        ("threshold", ctypes.c_float),
        ("min_speech_duration_ms", ctypes.c_int),
        ("min_silence_duration_ms", ctypes.c_int),
        ("max_speech_duration_s", ctypes.c_float),
        ("speech_pad_ms", ctypes.c_int),
        ("samples_overlap", ctypes.c_float),
    ]


class _GreedyParams(ctypes.Structure):
    _fields_ = [("best_of", ctypes.c_int)]


class _BeamSearchParams(ctypes.Structure):
    _fields_ = [("beam_size", ctypes.c_int), ("patience", ctypes.c_float)]


class _Aheads(ctypes.Structure):
    _fields_ = [("n_heads", ctypes.c_size_t), ("heads", ctypes.c_void_p)]


class WhisperContextParams(ctypes.Structure):
    _fields_ = [
        ("use_gpu", ctypes.c_bool),
        ("flash_attn", ctypes.c_bool),
        ("gpu_device", ctypes.c_int),
        ("dtw_token_timestamps", ctypes.c_bool),
        ("dtw_aheads_preset", ctypes.c_int),
        ("dtw_n_top", ctypes.c_int),
        ("dtw_aheads", _Aheads),
        ("dtw_mem_size", ctypes.c_size_t),
    ]


_NewSegmentCallback = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p
)
_ProgressCallback = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p
)
_EncoderBeginCallback = ctypes.CFUNCTYPE(
    ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
)
_AbortCallback = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
_LogitsFilterCallback = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_float),
    ctypes.c_void_p,
)


class WhisperFullParams(ctypes.Structure):
    _fields_ = [
        ("strategy", ctypes.c_int),
        ("n_threads", ctypes.c_int),
        ("n_max_text_ctx", ctypes.c_int),
        ("offset_ms", ctypes.c_int),
        ("duration_ms", ctypes.c_int),
        ("translate", ctypes.c_bool),
        ("no_context", ctypes.c_bool),
        ("no_timestamps", ctypes.c_bool),
        ("single_segment", ctypes.c_bool),
        ("print_special", ctypes.c_bool),
        ("print_progress", ctypes.c_bool),
        ("print_realtime", ctypes.c_bool),
        ("print_timestamps", ctypes.c_bool),
        ("token_timestamps", ctypes.c_bool),
        ("thold_pt", ctypes.c_float),
        ("thold_ptsum", ctypes.c_float),
        ("max_len", ctypes.c_int),
        ("split_on_word", ctypes.c_bool),
        ("max_tokens", ctypes.c_int),
        ("debug_mode", ctypes.c_bool),
        ("audio_ctx", ctypes.c_int),
        ("tdrz_enable", ctypes.c_bool),
        ("suppress_regex", ctypes.c_char_p),
        ("initial_prompt", ctypes.c_char_p),
        ("carry_initial_prompt", ctypes.c_bool),
        ("prompt_tokens", ctypes.POINTER(ctypes.c_int32)),
        ("prompt_n_tokens", ctypes.c_int),
        ("language", ctypes.c_char_p),
        ("detect_language", ctypes.c_bool),
        ("suppress_blank", ctypes.c_bool),
        ("suppress_nst", ctypes.c_bool),
        ("temperature", ctypes.c_float),
        ("max_initial_ts", ctypes.c_float),
        ("length_penalty", ctypes.c_float),
        ("temperature_inc", ctypes.c_float),
        ("entropy_thold", ctypes.c_float),
        ("logprob_thold", ctypes.c_float),
        ("no_speech_thold", ctypes.c_float),
        ("greedy", _GreedyParams),
        ("beam_search", _BeamSearchParams),
        ("new_segment_callback", _NewSegmentCallback),
        ("new_segment_callback_user_data", ctypes.c_void_p),
        ("progress_callback", _ProgressCallback),
        ("progress_callback_user_data", ctypes.c_void_p),
        ("encoder_begin_callback", _EncoderBeginCallback),
        ("encoder_begin_callback_user_data", ctypes.c_void_p),
        ("abort_callback", _AbortCallback),
        ("abort_callback_user_data", ctypes.c_void_p),
        ("logits_filter_callback", _LogitsFilterCallback),
        ("logits_filter_callback_user_data", ctypes.c_void_p),
        ("grammar_rules", ctypes.c_void_p),
        ("n_grammar_rules", ctypes.c_size_t),
        ("i_start_rule", ctypes.c_size_t),
        ("grammar_penalty", ctypes.c_float),
        ("vad", ctypes.c_bool),
        ("vad_model_path", ctypes.c_char_p),
        ("vad_params", _VADParams),
    ]


def audio_ctx_for(
    n_samples: int,
    sample_rate: int = WHISPER_SAMPLE_RATE,
    override: int = 0,
) -> int:
    """Pick the encoder window for one utterance.

    whisper pads every call up to ``audio_ctx`` positions, so passing the
    default 1500 makes a two-second phrase pay for the full 30 s window. The
    window has to stay larger than the content though, otherwise the decoder
    reaches the end of the audio and keeps generating.
    """
    if override and override > 0:
        return min(int(override), MAX_AUDIO_CTX)
    seconds = max(int(n_samples), 0) / float(sample_rate or WHISPER_SAMPLE_RATE)
    positions = math.ceil(seconds * ENCODER_POSITIONS_PER_SECOND) + AUDIO_CTX_MARGIN
    return max(1, min(MAX_AUDIO_CTX, positions))



_DEFAULT_THREADS = os.cpu_count() or 4


@dataclass
class WhisperParameters:
    """Whisper.cpp parameters"""
    n_threads: int = _DEFAULT_THREADS
    n_max_threads: int = _DEFAULT_THREADS
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
    # 0 means "size the window to the utterance"; see audio_ctx_for().
    audio_ctx: int = 0
    # Conditioning the decoder on its own previous output makes short clips
    # loop on the last sentence. WhisperFlow-style dictation wants this off.
    no_context: bool = True
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
        self.cli_path = self._find_cli()
        self.parameters = parameters or WhisperParameters()
        self.lib: Optional[ctypes.CDLL] = None
        self.ctx: Optional[ctypes.c_void_p] = None
        self.state: Optional[ctypes.c_void_p] = None
        self._is_loaded = False
        # whisper_full() is not re-entrant on one context and the model object
        # is a process-wide singleton, so context swaps and inference have to
        # be serialised or a concurrent load_model() frees a live context.
        self._lock = threading.RLock()
        self._load_library()

    def _find_cli(self) -> Optional[Path]:
        """Find the official Whisper command-line backend."""
        candidates = ["whisper-cli.exe", "main.exe"]
        for directory in utils.get_model_search_dirs():
            for name in candidates:
                candidate = directory / name
                if candidate.exists():
                    return candidate
        return None
    
    def _find_library(self) -> str:
        """Find whisper.cpp library"""
        # First, try to use the Python whispercpp package if available
        try:
            from whispercpp import api_cpp2py_export  # noqa: F401
            logger.info("Using Python whispercpp package")
            return "python_package"  # Special marker to indicate using Python package
        except ImportError:
            pass
        
        # Bundled and app-data model directories are searched first so the
        # backend resolves regardless of the working directory.
        library_names = ["whisper.dll", "libwhisper.so", "libwhisper.dylib"]
        for directory in utils.get_model_search_dirs():
            for name in library_names:
                candidate = directory / name
                if candidate.exists():
                    return str(candidate)

        # Fall back to locations relative to the working directory and the
        # system library path for manual installs.
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

        raise exceptions.SpeechError(
            "whisper.cpp library not found. Please download from "
            "https://github.com/ggerganov/whisper.cpp and place whisper.dll in the models directory, "
            "or install the Python package: pip install whispercpp"
        )
    
    def _load_library(self) -> None:
        """Load whisper.cpp library"""
        # If using Python whispercpp package, no need to load native library
        if self.library_path == "python_package":
            try:
                from whispercpp import api_cpp2py_export  # noqa: F401
            except ImportError as error:
                raise exceptions.SpeechError(
                    "The installed whispercpp package has no usable Windows native extension"
                ) from error
            logger.info("Using Python whispercpp package")
            self._is_loaded = True
            return
        
        if not Path(self.library_path).exists():
            raise exceptions.SpeechError(f"Whisper library not found: {self.library_path}")

        try:
            self._register_ggml_backends(Path(self.library_path).resolve().parent)
            self.lib = ctypes.CDLL(self.library_path)
            self._setup_functions()
            logger.info(f"Loaded whisper.cpp library: {self.library_path}")
        except Exception as e:
            self.lib = None
            if self.cli_path:
                logger.info(
                    "whisper.dll backend unavailable (%s); using whisper-cli.exe", e
                )
                self._is_loaded = True
                return
            raise exceptions.SpeechError(f"Failed to load whisper.cpp library: {e}")

    @staticmethod
    def _register_ggml_backends(directory: Path) -> None:
        """Make ggml's registry see the bundled ggml-cpu-*.dll files.

        ggml scans the directory of the running executable, which is python.exe
        or the app exe rather than models/, so without this call the device
        count stays zero and whisper_init aborts with GGML_ASSERT(device).
        """
        if os.name != "nt":
            return
        ggml_path = Path(directory) / "ggml.dll"
        if not ggml_path.exists() or str(directory) in _registered_backend_dirs:
            return
        _registered_backend_dirs.add(str(directory))

        if hasattr(os, "add_dll_directory"):
            # The returned handle unregisters the directory when dropped.
            _dll_directory_handles.append(os.add_dll_directory(str(directory)))

        ggml = ctypes.CDLL(str(ggml_path))
        loader = getattr(ggml, "ggml_backend_load_all_from_path", None)
        if loader is not None:
            loader.argtypes = [ctypes.c_char_p]
            loader.restype = None
            loader(str(directory).encode())
        else:
            ggml.ggml_backend_load_all()
        logger.debug("Registered ggml backends from %s", directory)

    def _setup_functions(self) -> None:
        """Bind the whisper.cpp entry points this module actually calls.

        Raises when a symbol is missing so the caller can fall back to the
        CLI: binding a function that does not exist only fails much later,
        inside an unrelated call.
        """
        signatures = {
            "whisper_version": ([], ctypes.c_char_p),
            "whisper_context_default_params_by_ref": ([], ctypes.c_void_p),
            "whisper_free_context_params": ([ctypes.c_void_p], None),
            "whisper_full_default_params_by_ref": ([ctypes.c_int], ctypes.c_void_p),
            "whisper_free_params": ([ctypes.c_void_p], None),
            "whisper_init_from_file_with_params": (
                [ctypes.c_char_p, WhisperContextParams],
                ctypes.c_void_p,
            ),
            "whisper_free": ([ctypes.c_void_p], None),
            "whisper_full": (
                [
                    ctypes.c_void_p,
                    WhisperFullParams,
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.c_int,
                ],
                ctypes.c_int,
            ),
            "whisper_full_n_segments": ([ctypes.c_void_p], ctypes.c_int),
            "whisper_full_get_segment_text": (
                [ctypes.c_void_p, ctypes.c_int],
                ctypes.c_char_p,
            ),
        }

        missing = []
        for name, (argtypes, restype) in signatures.items():
            try:
                function = getattr(self.lib, name)
            except AttributeError:
                missing.append(name)
                continue
            function.argtypes = argtypes
            function.restype = restype

        if missing:
            raise exceptions.SpeechError(
                "whisper.dll does not export: " + ", ".join(missing)
            )
    
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

        if self.lib is None and self.cli_path:
            self._is_loaded = True
            logger.info(f"Using whisper-cli with model: {self.model_path}")
            return

        with self._lock:
            # Free existing context
            if self.ctx:
                self.lib.whisper_free(self.ctx)
                self.ctx = None

            context_params = self._copy_default_params(
                WhisperContextParams,
                self.lib.whisper_context_default_params_by_ref,
                self.lib.whisper_free_context_params,
            )
            model_path_bytes = str(self.model_path).encode('utf-8')
            self.ctx = self.lib.whisper_init_from_file_with_params(
                model_path_bytes, context_params
            )

            if not self.ctx:
                raise exceptions.SpeechError(f"Failed to load model: {self.model_path}")

            self._is_loaded = True
        logger.info(f"Loaded whisper model: {self.model_path}")

    @staticmethod
    def _copy_default_params(structure, maker, free, *args):
        """Snapshot a `_by_ref` default-params struct and release the C copy."""
        pointer = maker(*args)
        if not pointer:
            raise exceptions.SpeechError("whisper.cpp returned no default parameters")
        try:
            view = ctypes.cast(pointer, ctypes.POINTER(structure)).contents
            return structure.from_buffer_copy(bytes(view))
        finally:
            free(pointer)
    
    def unload_model(self) -> None:
        """Unload whisper model"""
        with self._lock:
            if self.state and self.lib:
                self.lib.whisper_free_state(self.state)
                self.state = None

            if self.ctx and self.lib:
                self.lib.whisper_free(self.ctx)
                self.ctx = None

            self._is_loaded = False
        logger.info("Unloaded whisper model")

    def _transcribe_cli(self, audio_data: Union[bytes, np.ndarray], sample_rate: int) -> str:
        """Transcribe one utterance with the official fixed executable."""
        if not self.cli_path or not self.model_path:
            raise exceptions.SpeechError("Whisper CLI backend is not configured")

        with tempfile.TemporaryDirectory(prefix="aiop-whisper-") as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "audio.wav"
            output_prefix = temp_path / "result"
            if isinstance(audio_data, bytes):
                samples = np.frombuffer(audio_data, dtype=np.int16)
            else:
                samples = np.asarray(audio_data, dtype=np.float32)
                samples = np.clip(samples, -1.0, 1.0)
                samples = (samples * 32767).astype(np.int16)

            with wave.open(str(audio_path), "wb") as audio_file:
                audio_file.setnchannels(1)
                audio_file.setsampwidth(2)
                audio_file.setframerate(sample_rate)
                audio_file.writeframes(samples.tobytes())

            command = [
                str(self.cli_path),
                "-m", str(self.model_path),
                "-f", str(audio_path),
                "-otxt",
                "-of", str(output_prefix),
                "-nt",
                "-np",
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            result_path = output_prefix.with_suffix(".txt")
            if completed.returncode != 0 or not result_path.exists():
                raise exceptions.SpeechError(
                    completed.stderr.strip() or "Whisper transcription failed"
                )
            return result_path.read_text(encoding="utf-8").strip()
    
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
        if self.lib is None and self.cli_path:
            return self._transcribe_cli(audio_data, sample_rate)

        samples = self._to_float32(audio_data, sample_rate)

        with self._lock:
            if not self.ctx:
                self.load_model()

            params = self._build_params(
                n_samples=samples.size,
                language=language,
                translate=translate,
                temperature=temperature,
                max_len=max_len,
            )
            return self._process_audio(samples, params)

    @staticmethod
    def _to_float32(
        audio_data: Union[bytes, np.ndarray],
        sample_rate: int,
    ) -> np.ndarray:
        """Return mono float32 PCM at 16 kHz, the format whisper_full expects."""
        if isinstance(audio_data, (bytes, bytearray, memoryview)):
            samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            samples /= 32768.0
        else:
            raw = np.asarray(audio_data).reshape(-1)
            if raw.dtype == np.int16:
                samples = raw.astype(np.float32) / 32768.0
            else:
                samples = raw.astype(np.float32)
                if samples.size and (samples.max() > 1.0 or samples.min() < -1.0):
                    samples = samples / 32768.0
            samples = np.clip(samples, -1.0, 1.0)

        rate = int(sample_rate or WHISPER_SAMPLE_RATE)
        if rate != WHISPER_SAMPLE_RATE and samples.size > 1:
            target = int(round(samples.size * WHISPER_SAMPLE_RATE / rate))
            if target > 0:
                positions = np.linspace(0.0, samples.size - 1, target)
                samples = np.interp(positions, np.arange(samples.size), samples)

        return np.ascontiguousarray(samples, dtype=np.float32)

    def _build_params(
        self,
        n_samples: int,
        language: Optional[str] = None,
        translate: bool = False,
        temperature: float = 0.0,
        max_len: int = 0,
    ) -> WhisperFullParams:
        """Build decoding parameters from whisper's own greedy defaults."""
        params = self._copy_default_params(
            WhisperFullParams,
            self.lib.whisper_full_default_params_by_ref,
            self.lib.whisper_free_params,
            _SAMPLING_GREEDY,
        )
        params.n_threads = max(1, int(self.parameters.n_threads))
        params.audio_ctx = audio_ctx_for(
            n_samples, WHISPER_SAMPLE_RATE, self.parameters.audio_ctx
        )
        params.no_context = bool(self.parameters.no_context)
        params.no_timestamps = True
        params.translate = bool(translate)
        params.temperature = float(temperature)
        params.max_len = int(max_len or self.parameters.max_len or 0)
        params.detect_language = bool(self.parameters.detect_language)
        params.print_special = False
        params.print_progress = False
        params.print_realtime = False
        params.print_timestamps = False

        language = language or self.parameters.language
        if language:
            params.language = str(language).encode("ascii", "ignore")
        return params

    def _process_audio(self, samples: np.ndarray, params: WhisperFullParams) -> str:
        """Run whisper_full over float32 PCM and join the resulting segments."""
        audio_ptr = samples.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        result = self.lib.whisper_full(self.ctx, params, audio_ptr, int(samples.size))
        if result != 0:
            raise exceptions.SpeechError(f"Whisper processing failed with code: {result}")

        n_segments = self.lib.whisper_full_n_segments(self.ctx)
        parts = []
        for i in range(n_segments):
            text = self.lib.whisper_full_get_segment_text(self.ctx, i)
            if text:
                parts.append(text.decode("utf-8", "replace").strip())
        return " ".join(part for part in parts if part)
    
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

    def is_ready(self) -> bool:
        """True when the DLL backend is bound and the weights are resident."""
        with self._lock:
            return self.lib is not None and self.ctx is not None
    
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

    def warmup(self) -> bool:
        """Read the weights now so the first dictation only pays for inference.

        Returns False when the DLL backend is unavailable and the CLI backend
        (which loads the model per call) will be used instead.
        """
        if not self.whisper or self.whisper.lib is None:
            return False
        if self.whisper.is_ready():
            return True
        try:
            self.whisper.load_model()
            return True
        except Exception as error:
            logger.debug("Whisper warmup failed: %s", error)
            return False
    
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
