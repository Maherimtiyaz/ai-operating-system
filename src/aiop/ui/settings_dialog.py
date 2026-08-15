"""
Settings dialog for AIOP
"""

import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
    QLabel, QComboBox, QSpinBox, QCheckBox, QLineEdit, 
    QPushButton, QGroupBox, QFormLayout, QFileDialog, QMessageBox,
    QSlider, QFontComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from typing import Optional, List, Dict, Any
from ..core import config, logging
from ..audio import get_audio_devices

logger = logging.get_logger(__name__)


class SettingsDialog(QDialog):
    """Settings dialog for configuring AIOP"""
    
    settings_saved = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(700, 550)
        
        self._config_manager = config.get_config_manager()
        self._config = self._config_manager.get_config()
        
        # Store original values for cancellation
        self._original_config = self._clone_config()
        
        self._setup_ui()
        self._load_settings()
        
    def _clone_config(self) -> config.AIOPConfig:
        """Create a deep copy of current config"""
        return config.AIOPConfig(
            audio=config.AudioConfig(**self._config.audio.__dict__),
            speech=config.SpeechConfig(**self._config.speech.__dict__),
            windows=config.WindowsConfig(**self._config.windows.__dict__),
            ui=config.UIConfig(**self._config.ui.__dict__),
            ai=config.AIConfig(**self._config.ai.__dict__),
            automation=config.AutomationConfig(**self._config.automation.__dict__),
            plugin=config.PluginConfig(**self._config.plugin.__dict__),
            mcp=config.MCPConfig(**self._config.mcp.__dict__),
        )
    
    def _setup_ui(self) -> None:
        """Set up settings UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Tab widget
        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)
        
        # Create tabs
        self._tab_widget.addTab(self._create_audio_tab(), "Audio")
        self._tab_widget.addTab(self._create_speech_tab(), "Speech")
        self._tab_widget.addTab(self._create_ui_tab(), "Interface")
        self._tab_widget.addTab(self._create_windows_tab(), "Windows Integration")
        self._tab_widget.addTab(self._create_advanced_tab(), "Advanced")
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self._reset_button = QPushButton("Reset to Defaults")
        self._reset_button.setStyleSheet(
            "QPushButton { background-color: #303030; color: #a0a0a0; border: 1px solid #404040; border-radius: 4px; padding: 8px 16px; }"
            "QPushButton:hover { background-color: #404040; }"
        )
        self._reset_button.clicked.connect(self._on_reset)
        button_layout.addWidget(self._reset_button)
        
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setStyleSheet(
            "QPushButton { background-color: #303030; color: #a0a0a0; border: 1px solid #404040; border-radius: 4px; padding: 8px 16px; }"
            "QPushButton:hover { background-color: #404040; }"
        )
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)
        
        self._save_button = QPushButton("Save")
        self._save_button.setStyleSheet(
            "QPushButton { background-color: #2a82e4; color: white; border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3a92f4; }"
        )
        self._save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self._save_button)
        
        layout.addLayout(button_layout)
    
    def _create_audio_tab(self) -> QWidget:
        """Create audio settings tab"""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setSpacing(10)
        
        # Sample rate
        self._audio_sample_rate = QSpinBox()
        self._audio_sample_rate.setRange(8000, 48000)
        self._audio_sample_rate.setSingleStep(8000)
        self._audio_sample_rate.setStyleSheet("QSpinBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        layout.addRow("Sample Rate:", self._audio_sample_rate)
        
        # Channels
        self._audio_channels = QSpinBox()
        self._audio_channels.setRange(1, 2)
        self._audio_channels.setStyleSheet("QSpinBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        layout.addRow("Channels:", self._audio_channels)
        
        # Chunk size
        self._audio_chunk_size = QSpinBox()
        self._audio_chunk_size.setRange(256, 4096)
        self._audio_chunk_size.setSingleStep(256)
        self._audio_chunk_size.setStyleSheet("QSpinBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        layout.addRow("Chunk Size:", self._audio_chunk_size)
        
        # Device selection
        self._audio_device_combo = QComboBox()
        self._audio_device_combo.setStyleSheet("QComboBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        self._refresh_audio_devices()
        layout.addRow("Input Device:", self._audio_device_combo)
        
        # Refresh devices button
        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.setStyleSheet(
            "QPushButton { background-color: #303030; color: #a0a0a0; border: 1px solid #404040; border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #404040; }"
        )
        refresh_btn.clicked.connect(self._refresh_audio_devices)
        layout.addRow("", refresh_btn)
        
        return widget
    
    def _create_speech_tab(self) -> QWidget:
        """Create speech settings tab"""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setSpacing(10)
        
        # Model path
        model_layout = QHBoxLayout()
        self._speech_model_path = QLineEdit()
        self._speech_model_path.setStyleSheet("QLineEdit { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        model_layout.addWidget(self._speech_model_path)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet(
            "QPushButton { background-color: #303030; color: #a0a0a0; border: 1px solid #404040; border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #404040; }"
        )
        browse_btn.clicked.connect(self._browse_model)
        model_layout.addWidget(browse_btn)
        
        layout.addRow("Model Path:", model_layout)
        
        # Language
        self._speech_language = QComboBox()
        self._speech_language.addItems([
            "English", "Spanish", "French", "German", "Italian", 
            "Portuguese", "Dutch", "Russian", "Chinese", "Japanese", "Korean"
        ])
        self._speech_language.setStyleSheet("QComboBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        layout.addRow("Language:", self._speech_language)
        
        # Use VAD
        self._speech_use_vad = QCheckBox()
        self._speech_use_vad.setStyleSheet("QCheckBox { color: #e0e0e0; }")
        layout.addRow("Use Voice Activity Detection:", self._speech_use_vad)
        
        # VAD aggressiveness
        self._speech_vad_aggro = QSpinBox()
        self._speech_vad_aggro.setRange(0, 3)
        self._speech_vad_aggro.setStyleSheet("QSpinBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        layout.addRow("VAD Aggressiveness:", self._speech_vad_aggro)
        
        # Beam size
        self._speech_beam_size = QSpinBox()
        self._speech_beam_size.setRange(1, 10)
        self._speech_beam_size.setStyleSheet("QSpinBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        layout.addRow("Beam Size:", self._speech_beam_size)
        
        # Temperature
        self._speech_temp_slider = QSlider(Qt.Orientation.Horizontal)
        self._speech_temp_slider.setRange(0, 100)
        self._speech_temp_slider.setStyleSheet("QSlider::groove:horizontal { background-color: #404040; height: 4px; border-radius: 2px; } QSlider::handle:horizontal { background-color: #2a82e4; width: 16px; margin: -6px 0; border-radius: 8px; }")
        self._speech_temp_label = QLabel("0.0")
        self._speech_temp_label.setStyleSheet("color: #a0a0a0; min-width: 30px;")
        self._speech_temp_slider.valueChanged.connect(lambda v: self._speech_temp_label.setText(f"{v/100:.1f}"))
        
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(self._speech_temp_slider)
        temp_layout.addWidget(self._speech_temp_label)
        layout.addRow("Temperature:", temp_layout)
        
        return widget
    
    def _create_ui_tab(self) -> QWidget:
        """Create UI settings tab"""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setSpacing(10)
        
        # Theme
        self._ui_theme = QComboBox()
        self._ui_theme.addItems(["System", "Light", "Dark"])
        self._ui_theme.setStyleSheet("QComboBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        layout.addRow("Theme:", self._ui_theme)
        
        # Font size
        self._ui_font_size = QSpinBox()
        self._ui_font_size.setRange(8, 24)
        self._ui_font_size.setStyleSheet("QSpinBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        layout.addRow("Font Size:", self._ui_font_size)
        
        # Overlay position
        self._ui_overlay_position = QComboBox()
        self._ui_overlay_position.addItems([
            "Bottom Right", "Bottom Left", "Top Right", "Top Left", "Center"
        ])
        self._ui_overlay_position.setStyleSheet("QComboBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        layout.addRow("Overlay Position:", self._ui_overlay_position)
        
        # Show tray icon
        self._ui_show_tray = QCheckBox()
        self._ui_show_tray.setStyleSheet("QCheckBox { color: #e0e0e0; }")
        layout.addRow("Show Tray Icon:", self._ui_show_tray)
        
        return widget
    
    def _create_windows_tab(self) -> QWidget:
        """Create Windows integration settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        # Hotkeys group
        hotkey_group = QGroupBox("Global Hotkeys")
        hotkey_layout = QFormLayout(hotkey_group)
        hotkey_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        hotkey_layout.setSpacing(10)
        
        self._win_hotkey_dictation = QLineEdit()
        self._win_hotkey_dictation.setStyleSheet("QLineEdit { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        hotkey_layout.addRow("Dictation:", self._win_hotkey_dictation)
        
        self._win_hotkey_ai = QLineEdit()
        self._win_hotkey_ai.setStyleSheet("QLineEdit { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        hotkey_layout.addRow("AI Assistant:", self._win_hotkey_ai)
        
        self._win_hotkey_workflows = QLineEdit()
        self._win_hotkey_workflows.setStyleSheet("QLineEdit { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        hotkey_layout.addRow("Workflows:", self._win_hotkey_workflows)
        
        layout.addWidget(hotkey_group)
        
        # Startup group
        startup_group = QGroupBox("Startup & Behavior")
        startup_layout = QVBoxLayout(startup_group)
        startup_layout.setSpacing(8)
        
        self._win_start_on_boot = QCheckBox("Start on Windows boot")
        self._win_start_on_boot.setStyleSheet("QCheckBox { color: #e0e0e0; }")
        startup_layout.addWidget(self._win_start_on_boot)
        
        self._win_run_in_tray = QCheckBox("Run in system tray")
        self._win_run_in_tray.setStyleSheet("QCheckBox { color: #e0e0e0; }")
        startup_layout.addWidget(self._win_run_in_tray)
        
        self._win_minimize_to_tray = QCheckBox("Minimize to tray instead of closing")
        self._win_minimize_to_tray.setStyleSheet("QCheckBox { color: #e0e0e0; }")
        startup_layout.addWidget(self._win_minimize_to_tray)
        
        layout.addWidget(startup_group)
        layout.addStretch()
        
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        """Create advanced settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        # AI settings group
        ai_group = QGroupBox("AI Settings (Future)")
        ai_layout = QFormLayout(ai_group)
        ai_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        ai_layout.setSpacing(10)
        
        self._ai_default_model = QLineEdit()
        self._ai_default_model.setStyleSheet("QLineEdit { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        ai_layout.addRow("Default Model:", self._ai_default_model)
        
        self._ai_max_context = QSpinBox()
        self._ai_max_context.setRange(512, 32768)
        self._ai_max_context.setSingleStep(512)
        self._ai_max_context.setStyleSheet("QSpinBox { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 4px; }")
        ai_layout.addRow("Max Context Length:", self._ai_max_context)
        
        layout.addWidget(ai_group)
        
        # Plugin settings group
        plugin_group = QGroupBox("Plugin Settings (Future)")
        plugin_layout = QVBoxLayout(plugin_group)
        plugin_layout.setSpacing(8)
        
        self._plugin_auto_load = QCheckBox("Auto-load plugins")
        self._plugin_auto_load.setStyleSheet("QCheckBox { color: #e0e0e0; }")
        plugin_layout.addWidget(self._plugin_auto_load)
        
        self._plugin_sandbox = QCheckBox("Enable plugin sandboxing")
        self._plugin_sandbox.setStyleSheet("QCheckBox { color: #e0e0e0; }")
        plugin_layout.addWidget(self._plugin_sandbox)
        
        layout.addWidget(plugin_group)
        
        # Info section
        info_label = QLabel(
            "<b>Note:</b> Some settings require application restart to take effect.<br>"
            "<b>Version:</b> 0.1.0 (Phase 1 MVP)<br>"
            "<b>Platform:</b> Windows 10/11"
        )
        info_label.setStyleSheet("color: #808080; font-size: 11px; padding: 8px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        return widget
    
    def _refresh_audio_devices(self) -> None:
        """Refresh audio device list"""
        try:
            devices = get_audio_devices()
            self._audio_device_combo.clear()
            self._audio_device_combo.addItem("Default Device", userData=-1)
            
            for i, device in enumerate(devices):
                if device.get('is_input', False):
                    self._audio_device_combo.addItem(
                        device.get('name', f'Device {i}'),
                        userData=device.get('index', i)
                    )
            
            logger.info(f"Found {self._audio_device_combo.count() - 1} input devices")
        except Exception as e:
            logger.error(f"Failed to refresh audio devices: {e}")
            self._audio_device_combo.clear()
            self._audio_device_combo.addItem("No devices available", userData=-1)
    
    def _browse_model(self) -> None:
        """Browse for whisper model file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Whisper Model",
            "",
            "Whisper Models (*.bin);;All Files (*)"
        )
        if file_path:
            self._speech_model_path.setText(file_path)
    
    def _load_settings(self) -> None:
        """Load current settings into UI controls"""
        # Audio
        self._audio_sample_rate.setValue(self._config.audio.sample_rate)
        self._audio_channels.setValue(self._config.audio.channels)
        self._audio_chunk_size.setValue(self._config.audio.chunk_size)
        if self._config.audio.device_index is not None:
            for i in range(self._audio_device_combo.count()):
                if self._audio_device_combo.itemData(i) == self._config.audio.device_index:
                    self._audio_device_combo.setCurrentIndex(i)
                    break
        
        # Speech
        self._speech_model_path.setText(self._config.speech.model_path)
        language_map = {
            'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
            'it': 'Italian', 'pt': 'Portuguese', 'nl': 'Dutch', 'ru': 'Russian',
            'zh': 'Chinese', 'ja': 'Japanese', 'ko': 'Korean'
        }
        lang_text = language_map.get(self._config.speech.language, 'English')
        lang_index = self._speech_language.findText(lang_text)
        if lang_index >= 0:
            self._speech_language.setCurrentIndex(lang_index)
        
        self._speech_use_vad.setChecked(self._config.speech.use_vad)
        self._speech_vad_aggro.setValue(self._config.speech.vad_aggressiveness)
        self._speech_beam_size.setValue(self._config.speech.beam_size)
        self._speech_temp_slider.setValue(int(self._config.speech.temperature * 100))
        self._speech_temp_label.setText(f"{self._config.speech.temperature:.1f}")
        
        # UI
        theme_map = {'system': 'System', 'light': 'Light', 'dark': 'Dark'}
        theme_text = theme_map.get(self._config.ui.theme, 'System')
        theme_index = self._ui_theme.findText(theme_text)
        if theme_index >= 0:
            self._ui_theme.setCurrentIndex(theme_index)
        
        self._ui_font_size.setValue(self._config.ui.font_size)
        
        position_map = {
            'bottom_right': 'Bottom Right', 'bottom_left': 'Bottom Left',
            'top_right': 'Top Right', 'top_left': 'Top Left', 'center': 'Center'
        }
        pos_text = position_map.get(self._config.ui.overlay_position, 'Bottom Right')
        pos_index = self._ui_overlay_position.findText(pos_text)
        if pos_index >= 0:
            self._ui_overlay_position.setCurrentIndex(pos_index)
        
        self._ui_show_tray.setChecked(self._config.ui.show_tray_icon)
        
        # Windows
        self._win_hotkey_dictation.setText(self._config.windows.hotkey_dictation)
        self._win_hotkey_ai.setText(self._config.windows.hotkey_ai_assistant)
        self._win_hotkey_workflows.setText(self._config.windows.hotkey_workflows)
        self._win_start_on_boot.setChecked(self._config.windows.start_on_boot)
        self._win_run_in_tray.setChecked(self._config.windows.run_in_tray)
        self._win_minimize_to_tray.setChecked(self._config.windows.minimize_to_tray)
        
        # Advanced
        self._ai_default_model.setText(self._config.ai.default_model)
        self._ai_max_context.setValue(self._config.ai.max_context)
        self._plugin_auto_load.setChecked(self._config.plugin.auto_load)
        self._plugin_sandbox.setChecked(self._config.plugin.sandbox_enabled)
    
    def _save_settings(self) -> bool:
        """Save settings from UI controls"""
        try:
            # Audio
            self._config.audio.sample_rate = self._audio_sample_rate.value()
            self._config.audio.channels = self._audio_channels.value()
            self._config.audio.chunk_size = self._audio_chunk_size.value()
            device_index = self._audio_device_combo.currentData()
            self._config.audio.device_index = device_index if device_index != -1 else None
            
            # Speech
            self._config.speech.model_path = self._speech_model_path.text()
            language_map = {
                'English': 'en', 'Spanish': 'es', 'French': 'fr', 'German': 'de',
                'Italian': 'it', 'Portuguese': 'pt', 'Dutch': 'nl', 'Russian': 'ru',
                'Chinese': 'zh', 'Japanese': 'ja', 'Korean': 'ko'
            }
            selected_lang = self._speech_language.currentText()
            self._config.speech.language = language_map.get(selected_lang, 'en')
            
            self._config.speech.use_vad = self._speech_use_vad.isChecked()
            self._config.speech.vad_aggressiveness = self._speech_vad_aggro.value()
            self._config.speech.beam_size = self._speech_beam_size.value()
            self._config.speech.temperature = self._speech_temp_slider.value() / 100.0
            
            # UI
            theme_map = {'System': 'system', 'Light': 'light', 'Dark': 'dark'}
            self._config.ui.theme = theme_map.get(self._ui_theme.currentText(), 'system')
            self._config.ui.font_size = self._ui_font_size.value()
            
            position_map = {
                'Bottom Right': 'bottom_right', 'Bottom Left': 'bottom_left',
                'Top Right': 'top_right', 'Top Left': 'top_left', 'Center': 'center'
            }
            self._config.ui.overlay_position = position_map.get(
                self._ui_overlay_position.currentText(), 'bottom_right'
            )
            self._config.ui.show_tray_icon = self._ui_show_tray.isChecked()
            
            # Windows
            self._config.windows.hotkey_dictation = self._win_hotkey_dictation.text()
            self._config.windows.hotkey_ai_assistant = self._win_hotkey_ai.text()
            self._config.windows.hotkey_workflows = self._win_hotkey_workflows.text()
            self._config.windows.start_on_boot = self._win_start_on_boot.isChecked()
            self._config.windows.run_in_tray = self._win_run_in_tray.isChecked()
            self._config.windows.minimize_to_tray = self._win_minimize_to_tray.isChecked()
            
            # Advanced
            self._config.ai.default_model = self._ai_default_model.text()
            self._config.ai.max_context = self._ai_max_context.value()
            self._config.plugin.auto_load = self._plugin_auto_load.isChecked()
            self._config.plugin.sandbox_enabled = self._plugin_sandbox.isChecked()
            
            # Save to file
            self._config_manager._save_config()
            
            logger.info("Settings saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save settings:\n{str(e)}"
            )
            return False
    
    def _on_save(self) -> None:
        """Handle save button click"""
        if self._save_settings():
            self.settings_saved.emit()
            self.accept()
    
    def _on_reset(self) -> None:
        """Handle reset button click"""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._config_manager.reset()
            self._config = self._config_manager.get_config()
            self._load_settings()
            QMessageBox.information(
                self,
                "Settings Reset",
                "Settings have been reset to defaults."
            )
    
    def reject(self) -> None:
        """Handle dialog rejection (cancel)"""
        # Restore original config
        self._config = self._original_config
        super().reject()


def show_settings_dialog(parent=None) -> Optional[SettingsDialog]:
    """Show settings dialog and return it if accepted"""
    dialog = SettingsDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog
    return None
