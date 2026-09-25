"""
Tests for audio modules
"""

import pytest
from aiop.audio import devices, capture, processing


def test_audio_devices():
    """Test audio device enumeration"""
    devices_manager = devices.get_audio_devices()
    all_devices = devices_manager.list_devices()
    
    # Skip if no audio devices are available (e.g., in CI/headless environments)
    if len(all_devices) == 0:
        pytest.skip("No audio devices available in this environment")
    
    input_devices = devices_manager.list_input_devices()
    output_devices = devices_manager.list_output_devices()
    
    # Should have at least one input or output device
    assert len(input_devices) > 0 or len(output_devices) > 0


def test_audio_input_status_reports_missing_microphone():
    """A missing input device produces an actionable readiness message."""
    manager = devices.AudioDevices.__new__(devices.AudioDevices)
    manager.devices = {
        1: devices.AudioDeviceInfo(
            index=1,
            name="Speakers",
            max_input_channels=0,
            max_output_channels=2,
            default_sample_rate=48000.0,
        )
    }

    ready, message = manager.get_input_status()

    assert ready is False
    assert message == "No microphone input device was found"


def test_audio_capture():
    """Test audio capture"""
    capture_instance = capture.AudioCapture()
    
    assert capture_instance is not None
    assert capture_instance.parameters is not None
    assert capture_instance.parameters.sample_rate == 16000


def test_audio_processor():
    """Test audio processor"""
    processor = processing.AudioProcessor()
    
    assert processor is not None
    assert processor.sample_rate == 16000


def test_vad():
    """Test voice activity detection"""
    vad = processing.VoiceActivityDetector()
    
    assert vad is not None
    assert vad.sample_rate == 16000
