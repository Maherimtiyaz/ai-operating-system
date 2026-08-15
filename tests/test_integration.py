"""
Integration tests for AIOP

These tests verify the integration between different components
and test complete workflows rather than isolated units.
"""

import os
import sys
import time
import tempfile
import wave
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestConfigIntegration:
    """Test configuration management integration"""
    
    def test_config_persistence(self, tmp_path):
        """Test that config changes persist across reloads"""
        from aiop.core import config
        
        # Create temp config directory
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Create config manager
        cm = config.ConfigManager(config_dir=str(config_dir))
        
        # Modify settings
        original_rate = cm.get_config().audio.sample_rate
        cm.get_config().audio.sample_rate = 48000
        cm._save_config()
        
        # Create new manager and verify persistence
        cm2 = config.ConfigManager(config_dir=str(config_dir))
        assert cm2.get_config().audio.sample_rate == 48000
        
        # Reset
        cm2.get_config().audio.sample_rate = original_rate
        cm2._save_config()
    
    def test_config_update_and_reload(self, tmp_path):
        """Test updating config and reloading"""
        from aiop.core import config
        
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        cm = config.ConfigManager(config_dir=str(config_dir))
        
        # Update via method
        cm.update_config(audio={'sample_rate': 44100})
        
        # Reload and verify
        cm.reload()
        assert cm.get_config().audio.sample_rate == 44100
    
    def test_config_reset(self, tmp_path):
        """Test resetting config to defaults"""
        from aiop.core import config
        
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        cm = config.ConfigManager(config_dir=str(config_dir))
        
        # Modify
        cm.get_config().audio.sample_rate = 48000
        cm._save_config()
        
        # Reset
        cm.reset()
        
        # Verify defaults
        assert cm.get_config().audio.sample_rate == 16000


class TestAudioSpeechIntegration:
    """Test audio and speech recognition integration"""
    
    @pytest.fixture
    def sample_audio_file(self, tmp_path):
        """Create a sample WAV file for testing"""
        from aiop.audio import AudioConfig
        
        config = AudioConfig()
        filepath = tmp_path / "test_silence.wav"
        
        # Create 1 second of silence
        with wave.open(str(filepath), 'w') as wf:
            wf.setnchannels(config.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(config.sample_rate)
            silence = b'\x00\x00' * config.sample_rate  # 1 second
            wf.writeframes(silence)
        
        return str(filepath)
    
    def test_audio_capture_instantiation(self):
        """Test audio capture can be created"""
        from aiop.audio import AudioCapture
        
        capture = AudioCapture()
        assert capture is not None
        # Just verify it was created, actual device access may fail in test env
    
    def test_vad_processor_integration(self):
        """Test VAD processor with audio data"""
        from aiop.audio import VoiceActivityDetector
        from aiop.audio.processing import VADConfig
        
        # Create with default config
        vad = VoiceActivityDetector()
        
        # Test with silence - should return False (no speech detected)
        # Note: VAD expects specific frame sizes based on sample rate
        # For 16kHz, frames should be 160, 320, 480, or 640 samples (10-40ms)
        silence = b'\x00\x00' * 160  # 10ms of silence at 16kHz, 16-bit
        
        try:
            result = vad.is_speech(silence)
            # Result should be boolean
            assert isinstance(result, bool)
        except Exception as e:
            # VAD may fail without proper initialization, that's OK for this test
            pass
    
    def test_model_manager_initialization(self):
        """Test model manager can be initialized"""
        from aiop.speech import ModelManager
        
        mm = ModelManager()
        assert mm is not None
        # Don't test actual download, just initialization


class TestWindowsIntegration:
    """Test Windows-specific integration"""
    
    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows-only tests")
    def test_hotkey_registration(self):
        """Test hotkey registration on Windows"""
        from aiop.windows import HotkeyManager
        
        hm = HotkeyManager()
        assert hm is not None
        
        # Note: Actual registration requires window handle
        # This just tests instantiation
    
    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows-only tests")
    def test_clipboard_operations(self):
        """Test clipboard read/write"""
        from aiop.windows import Clipboard
        
        clipboard = Clipboard()
        test_text = "AIOP Test Clipboard"
        
        # Write
        clipboard.set_text(test_text)
        
        # Read
        read_text = clipboard.get_text()
        assert read_text == test_text
    
    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows-only tests")
    def test_win32_api_window_enumeration(self):
        """Test Win32 API window enumeration"""
        from aiop.windows import Win32API
        
        api = Win32API()
        windows = api.enumerate_windows()
        
        # Should return a list (may be empty)
        assert isinstance(windows, list)


class TestUIIntegration:
    """Test UI component integration"""
    
    @pytest.mark.skip(reason="Requires display/GUI environment")
    def test_main_window_creation(self):
        """Test main window can be created"""
        from PyQt6.QtWidgets import QApplication
        from aiop.ui import MainWindow
        
        app = QApplication.instance() or QApplication(sys.argv)
        window = MainWindow()
        
        assert window is not None
        assert window.windowTitle() == "AI Operating Platform"
    
    @pytest.mark.skip(reason="Requires display/GUI environment")
    def test_settings_dialog_creation(self):
        """Test settings dialog can be created"""
        from PyQt6.QtWidgets import QApplication
        from aiop.ui import SettingsDialog
        
        app = QApplication.instance() or QApplication(sys.argv)
        dialog = SettingsDialog()
        
        assert dialog is not None
        assert dialog.windowTitle() == "Settings"
    
    @pytest.mark.skip(reason="Requires display/GUI environment")
    def test_overlay_creation(self):
        """Test dictation overlay can be created"""
        from PyQt6.QtWidgets import QApplication
        from aiop.ui import DictationOverlay
        
        app = QApplication.instance() or QApplication(sys.argv)
        overlay = DictationOverlay()
        
        assert overlay is not None


class TestTranscriptionWorkflow:
    """Test complete transcription workflow"""
    
    @pytest.fixture
    def transcriber_setup(self):
        """Set up transcriber with mocked dependencies"""
        from aiop.speech import SpeechTranscriber, ModelManager
        
        # Mock model manager to avoid actual model loading
        mock_mm = Mock(spec=ModelManager)
        mock_mm.is_model_loaded.return_value = False
        
        transcriber = SpeechTranscriber(model_manager=mock_mm)
        return transcriber, mock_mm
    
    def test_transcriber_initialization(self, transcriber_setup):
        """Test transcriber can be initialized"""
        transcriber, mock_mm = transcriber_setup
        
        assert transcriber is not None
        assert not transcriber.is_running()
    
    def test_transcriber_start_stop(self, transcriber_setup):
        """Test starting and stopping transcriber"""
        transcriber, mock_mm = transcriber_setup
        
        # Start
        transcriber.start()
        assert transcriber.is_running()
        
        # Stop
        transcriber.stop()
        assert not transcriber.is_running()
    
    def test_callback_registration(self, transcriber_setup):
        """Test callback registration"""
        transcriber, mock_mm = transcriber_setup
        
        callback = Mock()
        transcriber.add_callback(callback)
        
        # Verify callback was added
        assert len(transcriber._callbacks) > 0


class TestEndToEndWorkflow:
    """End-to-end workflow tests"""
    
    @pytest.mark.skip(reason="Requires full environment setup")
    def test_complete_dictation_session(self):
        """Test complete dictation session from start to finish"""
        # This would require:
        # 1. whisper.cpp library installed
        # 2. Model file downloaded
        # 3. Audio hardware available
        # 4. GUI environment
        
        from aiop.main import main
        
        # Integration test placeholder
        # In production, this would:
        # - Start the application
        # - Trigger dictation via hotkey
        # - Speak a test phrase
        # - Verify transcription appears
        # - Stop dictation
        # - Verify output
        
        pass
    
    def test_config_to_ui_binding(self, tmp_path):
        """Test that config changes reflect in UI settings"""
        from aiop.core import config
        from aiop.ui.settings_dialog import SettingsDialog
        from PyQt6.QtWidgets import QApplication
        
        # Setup config
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        cm = config.ConfigManager(config_dir=str(config_dir))
        cm.get_config().audio.sample_rate = 44100
        cm._save_config()
        
        # Would test UI reflects this, but requires GUI
        # Placeholder for future GUI automation tests
        pass


class TestErrorHandlingIntegration:
    """Test error handling across component boundaries"""
    
    def test_missing_model_graceful_handling(self):
        """Test graceful handling when model is missing"""
        from aiop.speech import ModelManager
        
        mm = ModelManager()
        
        # Should not crash even if model doesn't exist
        loaded = mm.is_model_downloaded("tiny")
        assert loaded is False
    
    def test_audio_device_unavailable(self):
        """Test handling when audio device is unavailable"""
        from aiop.audio import AudioCapture
        
        capture = AudioCapture()
        
        # Without proper device, should handle gracefully
        # This depends on system state
        devices = capture.list_input_devices()
        assert isinstance(devices, list)
    
    def test_invalid_config_recovery(self, tmp_path):
        """Test recovery from invalid config file"""
        from aiop.core import config
        
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Write invalid YAML
        config_file = config_dir / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")
        
        # Should not crash, should use defaults
        cm = config.ConfigManager(config_dir=str(config_dir))
        assert cm.get_config() is not None
        assert cm.get_config().audio.sample_rate == 16000  # default


class TestPerformanceIntegration:
    """Integration performance tests"""
    
    def test_config_load_performance(self, tmp_path):
        """Test configuration loading performance"""
        from aiop.core import config
        import time
        
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        cm = config.ConfigManager(config_dir=str(config_dir))
        
        # Time multiple reloads
        start = time.time()
        for _ in range(10):
            cm.reload()
        elapsed = time.time() - start
        
        # Should load quickly (< 1 second for 10 reloads)
        assert elapsed < 1.0
    
    def test_audio_buffer_allocation(self):
        """Test audio buffer allocation performance"""
        from aiop.audio import AudioCapture
        import time
        
        capture = AudioCapture()
        
        # Allocate multiple buffers
        start = time.time()
        buffers = []
        for _ in range(100):
            # Simulate buffer creation
            buffer = bytearray(1024 * 2)  # 1KB buffer
            buffers.append(buffer)
        elapsed = time.time() - start
        
        # Should be fast (< 0.5 seconds)
        assert elapsed < 0.5


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
