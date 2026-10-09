"""
Audio capture for AIOP
"""

import time
import threading
import pyaudio
from typing import Generator, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from ..core import logging, exceptions
from .devices import AudioDeviceInfo, get_audio_devices

logger = logging.get_logger(__name__)

_pyaudio_instance: Optional[pyaudio.PyAudio] = None


def get_pyaudio() -> pyaudio.PyAudio:
    """Return the process-wide PortAudio instance.

    Constructing ``PyAudio`` costs ~280 ms because it boots the audio runtime
    and enumerates every device. Building one per ``AudioStream`` both made
    the first dictation sluggish and leaked an instance on every start/stop
    cycle, since nothing ever called ``terminate()``.
    """
    global _pyaudio_instance
    if _pyaudio_instance is None:
        _pyaudio_instance = pyaudio.PyAudio()
    return _pyaudio_instance


def terminate_pyaudio() -> None:
    """Release the shared PortAudio instance. Safe to call more than once."""
    global _pyaudio_instance
    if _pyaudio_instance is None:
        return
    try:
        _pyaudio_instance.terminate()
    except Exception as error:
        logger.error("Error terminating PortAudio: %s", error)
    _pyaudio_instance = None


class AudioFormat(Enum):
    """Audio format enumeration"""
    INT8 = pyaudio.paInt8
    INT16 = pyaudio.paInt16
    INT24 = pyaudio.paInt24
    INT32 = pyaudio.paInt32
    FLOAT32 = pyaudio.paFloat32


@dataclass
class AudioParameters:
    """Audio capture parameters"""
    sample_rate: int = 16000
    channels: int = 1
    format: AudioFormat = AudioFormat.INT16
    chunk_size: int = 1024
    device_index: Optional[int] = None


@dataclass
class AudioChunk:
    """Audio data chunk"""
    data: bytes
    sample_rate: int
    channels: int
    format: AudioFormat
    timestamp: float = field(default_factory=time.time)


class AudioStream:
    """Audio stream for continuous capture"""

    # A stuck driver can make Pa_OpenStream block forever (seen with a wedged
    # MME capture device). The open runs on a worker thread so a hung call
    # surfaces as an AudioError instead of freezing the whole application.
    _open_timeout = 8.0

    def __init__(
        self,
        parameters: AudioParameters,
        callback: Optional[Callable[[AudioChunk], None]] = None,
    ):
        self.parameters = parameters
        self.callback = callback
        self.pyaudio = get_pyaudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.is_running = False
        self._frames: list = []
        self._opening = False

    def start(self) -> None:
        """Start audio capture"""
        if self.is_running:
            logger.warning("Audio stream already running")
            return
        if self._opening:
            raise exceptions.AudioError("Microphone is already starting up")

        # Determine device index
        device_index = self.parameters.device_index
        if device_index is None:
            default_input = get_audio_devices().get_default_input_device()
            if default_input:
                device_index = default_input.index
            else:
                raise exceptions.AudioError("No default input device found")

        self._opening = True
        try:
            self._open_with_timeout(device_index)
        finally:
            self._opening = False

    def _open_with_timeout(self, device_index: int) -> None:
        """Open the device with a hard deadline so a hung driver cannot stall UI."""
        result: dict = {}

        def open_stream() -> None:
            try:
                stream = self.pyaudio.open(
                    format=self.parameters.format.value,
                    channels=self.parameters.channels,
                    rate=self.parameters.sample_rate,
                    input=True,
                    frames_per_buffer=self.parameters.chunk_size,
                    input_device_index=device_index,
                    stream_callback=self._callback if self.callback else None,
                )
                stream.start_stream()
                result["stream"] = stream
            except Exception as error:
                result["error"] = error

        worker = threading.Thread(target=open_stream, daemon=True)
        worker.start()
        worker.join(timeout=self._open_timeout)

        if "stream" in result:
            self.stream = result["stream"]
            self.is_running = True
            logger.info(
                "Audio stream started: %sHz, %s channels",
                self.parameters.sample_rate,
                self.parameters.channels,
            )
            return

        if "error" in result:
            raise exceptions.AudioError(
                f"Failed to start audio stream: {result['error']}"
            )

        logger.error(
            "Timed out after %.1fs opening the microphone; the audio device "
            "is busy or hung",
            self._open_timeout,
        )
        raise exceptions.AudioError(
            "Timed out opening the microphone. The audio device appears to be "
            "busy or in a bad state."
        )

    def stop(self) -> None:
        """Stop audio capture"""
        if not self.is_running:
            return
        
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            self.is_running = False
            logger.info("Audio stream stopped")
        except Exception as e:
            logger.error(f"Error stopping audio stream: {e}")
    
    def _callback(self, in_data: bytes, frame_count: int, time_info: dict, status: int) -> (bytes, int):
        """PyAudio callback function"""
        if self.callback:
            chunk = AudioChunk(
                data=in_data,
                sample_rate=self.parameters.sample_rate,
                channels=self.parameters.channels,
                format=self.parameters.format,
            )
            self.callback(chunk)
        return (in_data, pyaudio.paContinue)
    
    def read(self) -> Optional[AudioChunk]:
        """Read a chunk of audio data (non-callback mode)"""
        if not self.is_running or not self.stream:
            return None
        
        try:
            data = self.stream.read(self.parameters.chunk_size, exception_on_overflow=False)
            return AudioChunk(
                data=data,
                sample_rate=self.parameters.sample_rate,
                channels=self.parameters.channels,
                format=self.parameters.format,
            )
        except Exception as e:
            logger.error(f"Error reading audio data: {e}")
            return None
    
    def read_generator(self) -> Generator[AudioChunk, None, None]:
        """Generate audio chunks continuously"""
        while self.is_running:
            chunk = self.read()
            if chunk:
                yield chunk
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # The PortAudio instance is shared process-wide, so it is left open
        # for the next stream. Use terminate_pyaudio() on shutdown.
        self.stop()


class AudioCapture:
    """High-level audio capture manager"""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        device_index: Optional[int] = None,
    ):
        self.parameters = AudioParameters(
            sample_rate=sample_rate,
            channels=channels,
            chunk_size=chunk_size,
            device_index=device_index,
        )
        self.stream: Optional[AudioStream] = None
        self._callbacks: list = []
    
    def add_callback(self, callback: Callable[[AudioChunk], None]) -> None:
        """Add a callback for audio data"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[AudioChunk], None]) -> None:
        """Remove a callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _handle_audio(self, chunk: AudioChunk) -> None:
        """Handle incoming audio data"""
        for callback in self._callbacks:
            try:
                callback(chunk)
            except Exception as e:
                logger.error(f"Error in audio callback: {e}")
    
    def start(self) -> None:
        """Start audio capture"""
        if self.stream and self.stream.is_running:
            return
        
        self.stream = AudioStream(
            parameters=self.parameters,
            callback=self._handle_audio if self._callbacks else None,
        )
        self.stream.start()

    def get_input_status(self) -> tuple[bool, str]:
        """Return microphone readiness for onboarding and diagnostics."""
        devices_manager = get_audio_devices()
        return devices_manager.get_input_status()
    
    def stop(self) -> None:
        """Stop audio capture"""
        if self.stream:
            self.stream.stop()
            self.stream = None
    
    def read(self) -> Optional[AudioChunk]:
        """Read a chunk of audio data"""
        if not self.stream:
            return None
        return self.stream.read()
    
    def read_generator(self) -> Generator[AudioChunk, None, None]:
        """Generate audio chunks continuously"""
        if not self.stream:
            self.start()
        return self.stream.read_generator()
    
    def is_running(self) -> bool:
        """Check if capture is running"""
        return self.stream is not None and self.stream.is_running
    
    def get_parameters(self) -> AudioParameters:
        """Get current audio parameters"""
        return self.parameters
    
    def set_parameters(self, **kwargs) -> None:
        """Set audio parameters"""
        for key, value in kwargs.items():
            if hasattr(self.parameters, key):
                setattr(self.parameters, key, value)
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
    
    def list_input_devices(self) -> List[AudioDeviceInfo]:
        """List available input devices"""
        devices_manager = get_audio_devices()
        return devices_manager.list_input_devices()
    
    def list_output_devices(self) -> List[AudioDeviceInfo]:
        """List available output devices"""
        devices_manager = get_audio_devices()
        return devices_manager.list_output_devices()


# Global audio capture instance
_audio_capture: Optional[AudioCapture] = None


def get_audio_capture(**kwargs) -> AudioCapture:
    """Get the global audio capture instance"""
    global _audio_capture
    if _audio_capture is None:
        _audio_capture = AudioCapture(**kwargs)
    return _audio_capture


def start_audio_capture(**kwargs) -> AudioCapture:
    """Start global audio capture"""
    capture = get_audio_capture(**kwargs)
    capture.start()
    return capture


def stop_audio_capture() -> None:
    """Stop global audio capture"""
    global _audio_capture
    if _audio_capture:
        _audio_capture.stop()
