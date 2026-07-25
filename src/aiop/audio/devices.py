"""
Audio device management for AIOP
"""

import pyaudio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from ..core import logging

logger = logging.get_logger(__name__)


@dataclass
class AudioDeviceInfo:
    """Audio device information"""
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float
    is_default_input: bool = False
    is_default_output: bool = False


class AudioDevices:
    """Audio device manager"""
    
    def __init__(self):
        self.pyaudio = pyaudio.PyAudio()
        self.devices: Dict[int, AudioDeviceInfo] = {}
        self._load_devices()
    
    def _load_devices(self) -> None:
        """Load available audio devices"""
        self.devices = {}
        
        for i in range(self.pyaudio.get_device_count()):
            device_info = self.pyaudio.get_device_info_by_index(i)
            
            self.devices[i] = AudioDeviceInfo(
                index=i,
                name=device_info.get('name', 'Unknown'),
                max_input_channels=device_info.get('maxInputChannels', 0),
                max_output_channels=device_info.get('maxOutputChannels', 0),
                default_sample_rate=device_info.get('defaultSampleRate', 44100.0),
                is_default_input=self.pyaudio.get_default_input_device_info().get('index') == i,
                is_default_output=self.pyaudio.get_default_output_device_info().get('index') == i,
            )
    
    def list_devices(self) -> List[AudioDeviceInfo]:
        """List all available audio devices"""
        return list(self.devices.values())
    
    def list_input_devices(self) -> List[AudioDeviceInfo]:
        """List all input-capable devices"""
        return [d for d in self.devices.values() if d.max_input_channels > 0]
    
    def list_output_devices(self) -> List[AudioDeviceInfo]:
        """List all output-capable devices"""
        return [d for d in self.devices.values() if d.max_output_channels > 0]
    
    def get_default_input_device(self) -> Optional[AudioDeviceInfo]:
        """Get the default input device"""
        for device in self.devices.values():
            if device.is_default_input:
                return device
        return None
    
    def get_default_output_device(self) -> Optional[AudioDeviceInfo]:
        """Get the default output device"""
        for device in self.devices.values():
            if device.is_default_output:
                return device
        return None
    
    def get_device_by_index(self, index: int) -> Optional[AudioDeviceInfo]:
        """Get device by index"""
        return self.devices.get(index)
    
    def get_device_by_name(self, name: str) -> Optional[AudioDeviceInfo]:
        """Get device by name"""
        for device in self.devices.values():
            if device.name == name:
                return device
        return None
    
    def refresh(self) -> None:
        """Refresh device list"""
        self._load_devices()
    
    def __del__(self):
        """Cleanup"""
        self.pyaudio.terminate()


# Global audio devices instance
_audio_devices: Optional[AudioDevices] = None


def get_audio_devices() -> AudioDevices:
    """Get the global audio devices manager"""
    global _audio_devices
    if _audio_devices is None:
        _audio_devices = AudioDevices()
    return _audio_devices


def list_audio_devices() -> List[AudioDeviceInfo]:
    """List all available audio devices"""
    return get_audio_devices().list_devices()


def get_default_input_device() -> Optional[AudioDeviceInfo]:
    """Get the default input device"""
    return get_audio_devices().get_default_input_device()


def get_default_output_device() -> Optional[AudioDeviceInfo]:
    """Get the default output device"""
    return get_audio_devices().get_default_output_device()
