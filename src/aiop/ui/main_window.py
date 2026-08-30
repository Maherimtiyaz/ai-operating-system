"""
Main window for AIOP - Redesigned with modern WhisperFlow-inspired UI
"""

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QTextEdit, QSystemTrayIcon, QMenu, QApplication,
    QFrame, QScrollArea, QSizePolicy, QSpacerItem, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QIcon, QAction, QFont, QColor, QPalette, QLinearGradient, QPainter
from PyQt6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from typing import Optional, Callable
from ..core import logging, config
from ..speech import SpeechTranscriber, TranscriptionResult
from ..windows import get_clipboard, get_win32_api
from .overlay import DictationOverlay, get_overlay
from .styles import apply_theme, Colors
from .settings_dialog import SettingsDialog

logger = logging.get_logger(__name__)


class ModernButton(QPushButton):
    """Modern styled button with hover effects"""
    
    def __init__(self, text: str, primary: bool = False, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if primary:
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #2a82e4, stop:1 #4a92f4);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 0 24px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3a92f4, stop:1 #5aa2ff);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #1a62c4, stop:1 #2a72d4);
                }
                QPushButton:disabled {
                    background: #404040;
                    color: #808080;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #303030;
                    color: #e0e0e0;
                    border: 1px solid #404040;
                    border-radius: 8px;
                    font-size: 13px;
                    padding: 0 24px;
                }
                QPushButton:hover {
                    background-color: #404040;
                    border-color: #505050;
                }
                QPushButton:pressed {
                    background-color: #282828;
                }
                QPushButton:disabled {
                    background-color: #252525;
                    color: #606060;
                    border-color: #353535;
                }
            """)


class StatusIndicator(QFrame):
    """Animated status indicator"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.setStyleSheet("""
            QFrame {
                background-color: #40c040;
                border-radius: 6px;
            }
        """)
        self._pulse_animation = QPropertyAnimation(self, b"opacity")
        self._pulse_animation.setDuration(1000)
        self._pulse_animation.setStartValue(1.0)
        self._pulse_animation.setEndValue(0.3)
        self._pulse_animation.setLoopCount(-1)
    
    @pyqtProperty(float)
    def opacity(self):
        return self.graphicsEffect().opacity() if self.graphicsEffect() else 1.0
    
    @opacity.setter
    def opacity(self, value):
        effect = self.graphicsEffect()
        if not effect:
            effect = QGraphicsDropShadowEffect()
            self.setGraphicsEffect(effect)
        effect.setOpacity(value)
    
    def start_pulsing(self):
        self._pulse_animation.start()
    
    def stop_pulsing(self):
        self._pulse_animation.stop()
        self.setGraphicsEffect(None)
        self.setStyleSheet("background-color: #40c040; border-radius: 6px;")
    
    def set_status(self, active: bool):
        if active:
            self.setStyleSheet("background-color: #40c040; border-radius: 6px;")
            self.start_pulsing()
        else:
            self._pulse_animation.stop()
            self.setGraphicsEffect(None)
            self.setStyleSheet("background-color: #606060; border-radius: 6px;")


class TranscriptionDisplay(QTextEdit):
    """Modern transcription display with smooth scrolling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #303030;
                border-radius: 12px;
                padding: 16px;
                font-size: 14px;
                line-height: 1.6;
            }
            QTextEdit:focus {
                border-color: #2a82e4;
            }
        """)
        self.setFont(QFont("Segoe UI", 13))


class MainWindow(QMainWindow):
    """Main application window with modern WhisperFlow-inspired design"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Operating Platform")
        self.setWindowIcon(QIcon(":/assets/icon.png"))
        self.resize(1100, 750)
        self.setMinimumSize(900, 650)
        
        # Apply modern window styling
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e1e1e, stop:1 #2a2a2a);
            }
        """)
        
        # Configuration
        self._config = config.get_config()
        
        # Components
        self._transcriber: Optional[SpeechTranscriber] = None
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._overlay: Optional[DictationOverlay] = None
        self._is_listening = False
        
        # Setup
        self._setup_ui()
        self._setup_tray()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Set up modern main UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Top bar with custom title and controls
        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)
        
        # Main content area
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(24, 20, 24, 24)
        content_layout.setSpacing(16)
        
        # Status bar
        self._status_bar = self._create_status_bar()
        content_layout.addWidget(self._status_bar)
        
        # Main transcription area
        self._transcription_display = TranscriptionDisplay()
        self._transcription_display.setPlaceholderText("Your transcribed text will appear here...\n\nPress 'Start Dictation' or use Ctrl+Shift+Space to begin.")
        content_layout.addWidget(self._transcription_display, stretch=1)
        
        # Control panel
        control_panel = self._create_control_panel()
        content_layout.addWidget(control_panel)
        
        # Info panel
        info_panel = self._create_info_panel()
        content_layout.addWidget(info_panel)
        
        main_layout.addWidget(content_area, stretch=1)
    
    def _create_top_bar(self) -> QWidget:
        """Create modern top bar"""
        top_bar = QFrame()
        top_bar.setFixedHeight(60)
        top_bar.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border-bottom: 1px solid #303030;
            }
        """)
        
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(20, 0, 12, 0)
        
        # Logo and title
        logo_label = QLabel()
        logo_label.setText("🎙️ AIOP")
        logo_label.setStyleSheet("font-size: 20px; font-weight: 700; color: #e0e0e0;")
        layout.addWidget(logo_label)
        
        subtitle = QLabel("AI Operating Platform")
        subtitle.setStyleSheet("font-size: 12px; color: #808080; margin-left: 8px;")
        layout.addWidget(subtitle)
        
        layout.addStretch()
        
        # Window controls
        minimize_btn = QPushButton("─")
        minimize_btn.setFixedSize(36, 36)
        minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a0a0a0;
                border: none;
                border-radius: 4px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #404040;
                color: #e0e0e0;
            }
        """)
        minimize_btn.clicked.connect(self.showMinimized)
        layout.addWidget(minimize_btn)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 36)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a0a0a0;
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #e04040;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return top_bar
    
    def _create_status_bar(self) -> QWidget:
        """Create modern status bar"""
        status_widget = QFrame()
        status_widget.setFixedHeight(40)
        status_widget.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        
        layout = QHBoxLayout(status_widget)
        layout.setContentsMargins(16, 0, 16, 0)
        
        # Status indicator
        self._status_indicator = StatusIndicator()
        layout.addWidget(self._status_indicator)
        
        # Status label
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #a0a0a0; font-size: 13px; font-weight: 500;")
        layout.addWidget(self._status_label)
        
        layout.addStretch()
        
        # Model status
        self._model_status = QLabel("⚠️ Whisper model not loaded")
        self._model_status.setStyleSheet("color: #ffa500; font-size: 12px;")
        layout.addWidget(self._model_status)
        
        return status_widget
    
    def _create_control_panel(self) -> QWidget:
        """Create modern control panel"""
        control_widget = QFrame()
        control_widget.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        
        layout = QHBoxLayout(control_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Start button
        self._start_button = ModernButton("▶ Start Dictation", primary=True)
        self._start_button.clicked.connect(self.on_start_dictation)
        layout.addWidget(self._start_button)
        
        # Stop button
        self._stop_button = ModernButton("⏹ Stop Dictation")
        self._stop_button.clicked.connect(self.on_stop_dictation)
        self._stop_button.setEnabled(False)
        layout.addWidget(self._stop_button)
        
        # Settings button
        settings_btn = ModernButton("⚙ Settings")
        settings_btn.clicked.connect(self.on_settings)
        layout.addWidget(settings_btn)
        
        layout.addStretch()
        
        return control_widget
    
    def _create_info_panel(self) -> QWidget:
        """Create info panel with shortcuts and clipboard"""
        info_widget = QFrame()
        info_widget.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(info_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Keyboard shortcuts
        shortcuts_title = QLabel("⌨️ Keyboard Shortcuts")
        shortcuts_title.setStyleSheet("color: #e0e0e0; font-size: 13px; font-weight: 600;")
        layout.addWidget(shortcuts_title)
        
        shortcuts_layout = QHBoxLayout()
        shortcuts_layout.setSpacing(16)
        
        shortcut1 = QLabel("<span style='color: #808080;'>Ctrl+Shift+Space:</span> <span style='color: #e0e0e0;'>Toggle Dictation</span>")
        shortcut1.setStyleSheet("font-size: 12px;")
        shortcuts_layout.addWidget(shortcut1)
        
        shortcut2 = QLabel("<span style='color: #808080;'>Ctrl+Shift+O:</span> <span style='color: #e0e0e0;'>Toggle Overlay</span>")
        shortcut2.setStyleSheet("font-size: 12px;")
        shortcuts_layout.addWidget(shortcut2)
        
        layout.addLayout(shortcuts_layout)
        
        # Clipboard section
        clipboard_title = QLabel("📋 Clipboard")
        clipboard_title.setStyleSheet("color: #e0e0e0; font-size: 13px; font-weight: 600; margin-top: 8px;")
        layout.addWidget(clipboard_title)
        
        clipboard_layout = QHBoxLayout()
        clipboard_layout.setSpacing(8)
        
        self._clipboard_text = QLabel("Empty")
        self._clipboard_text.setStyleSheet("""
            color: #a0a0a0;
            font-size: 12px;
            background-color: #1a1a1a;
            padding: 8px;
            border-radius: 6px;
        """)
        self._clipboard_text.setWordWrap(True)
        self._clipboard_text.setMaximumHeight(60)
        clipboard_layout.addWidget(self._clipboard_text, stretch=1)
        
        self._copy_button = ModernButton("📄 Copy All")
        self._copy_button.setFixedHeight(36)
        self._copy_button.clicked.connect(self.on_copy_to_clipboard)
        clipboard_layout.addWidget(self._copy_button)
        
        layout.addLayout(clipboard_layout)
        
        return info_widget
    
    def _setup_tray(self) -> None:
        """Set up system tray icon"""
        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(QIcon(":/assets/icon.png"))
        self._tray_icon.setToolTip("AI Operating Platform")
        
        tray_menu = QMenu()
        
        # Show action
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        # Start dictation action
        start_action = QAction("Start Dictation", self)
        start_action.triggered.connect(self.on_start_dictation)
        tray_menu.addAction(start_action)
        
        # Stop dictation action
        stop_action = QAction("Stop Dictation", self)
        stop_action.triggered.connect(self.on_stop_dictation)
        stop_action.setEnabled(False)
        tray_menu.addAction(stop_action)
        
        tray_menu.addSeparator()
        
        # Settings action
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.on_settings)
        tray_menu.addAction(settings_action)
        
        tray_menu.addSeparator()
        
        # Quit action
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(quit_action)
        
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.show()
        
        # Connect activated signal
        self._tray_icon.activated.connect(self.on_tray_activated)
    
    def _setup_connections(self) -> None:
        """Set up signal connections"""
        # Initialize transcriber
        self._transcriber = SpeechTranscriber()
        self._transcriber.add_callback(self.on_transcription_result)
        
        # Initialize overlay
        self._overlay = get_overlay()
        self._overlay.add_transcription_callback(self.on_overlay_transcription)
        self._overlay.add_state_change_callback(self.on_overlay_state_change)
        
        # Timer for clipboard monitoring
        self._clipboard_timer = QTimer(self)
        self._clipboard_timer.timeout.connect(self.update_clipboard)
        self._clipboard_timer.start(1000)  # Update every second
        
        # Update clipboard initially
        self.update_clipboard()
    
    def _setup_styles(self) -> None:
        """Set up styles - kept for compatibility but styles are now in widgets"""
        pass
    
    def on_start_dictation(self) -> None:
        """Start voice dictation"""
        if not self._transcriber:
            return
        
        try:
            self._transcriber.start()
            self._is_listening = True
            self._start_button.setEnabled(False)
            self._stop_button.setEnabled(True)
            self._status_label.setText("Listening...")
            self._status_label.setStyleSheet("color: #40c040; font-size: 13px; font-weight: 500;")
            self._status_indicator.set_status(True)
            
            # Update model status
            if hasattr(self._transcriber, '_model') and self._transcriber._model is not None:
                self._model_status.setText("✓ Whisper model loaded")
                self._model_status.setStyleSheet("color: #40c040; font-size: 12px;")
            
            # Show overlay
            if self._overlay:
                self._overlay.set_listening(True)
                self._overlay.show()
            
            # Update tray menu
            self._update_tray_menu_state(True)
            
        except Exception as e:
            logger.error(f"Error starting dictation: {e}")
            self._status_label.setText("Error starting dictation")
            self._is_listening = False
    
    def on_stop_dictation(self) -> None:
        """Stop voice dictation"""
        if not self._transcriber:
            return
        
        try:
            self._transcriber.stop()
            self._is_listening = False
            self._start_button.setEnabled(True)
            self._stop_button.setEnabled(False)
            self._status_label.setText("Ready")
            self._status_label.setStyleSheet("color: #a0a0a0; font-size: 13px; font-weight: 500;")
            self._status_indicator.set_status(False)
            
            # Hide overlay
            if self._overlay:
                self._overlay.set_listening(False)
            
            # Update tray menu
            self._update_tray_menu_state(False)
            
        except Exception as e:
            logger.error(f"Error stopping dictation: {e}")
    
    def _update_tray_menu_state(self, is_listening: bool) -> None:
        """Update tray menu action states"""
        if self._tray_icon and self._tray_icon.contextMenu():
            for action in self._tray_icon.contextMenu().actions():
                if action.text() == "Start Dictation":
                    action.setEnabled(not is_listening)
                elif action.text() == "Stop Dictation":
                    action.setEnabled(is_listening)
    
    def on_transcription_result(self, result: TranscriptionResult) -> None:
        """Handle transcription result"""
        if result.text:
            self._transcription_display.append(result.text + " ")
            
            # Scroll to end
            cursor = self._transcription_display.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self._transcription_display.setTextCursor(cursor)
            self._transcription_display.ensureCursorVisible()
    
    def on_overlay_transcription(self, text: str) -> None:
        """Handle overlay transcription"""
        if text:
            self._transcription_display.append(text + " ")
    
    def on_overlay_state_change(self, listening: bool) -> None:
        """Handle overlay state change"""
        self._is_listening = listening
        if listening:
            self._status_label.setText("Listening...")
            self._status_label.setStyleSheet("color: #40c040; font-size: 13px; font-weight: 500;")
            self._status_indicator.set_status(True)
            self._start_button.setEnabled(False)
            self._stop_button.setEnabled(True)
        else:
            self._status_label.setText("Ready")
            self._status_label.setStyleSheet("color: #a0a0a0; font-size: 13px; font-weight: 500;")
            self._status_indicator.set_status(False)
            self._start_button.setEnabled(True)
            self._stop_button.setEnabled(False)
    
    def on_copy_to_clipboard(self) -> None:
        """Copy transcription to clipboard"""
        text = self._transcription_display.toPlainText()
        if text:
            try:
                clipboard = get_clipboard()
                clipboard.set_text(text)
                self._status_label.setText("✓ Copied to clipboard")
                QTimer.singleShot(2000, lambda: self._status_label.setText("Ready"))
            except Exception as e:
                logger.error(f"Error copying to clipboard: {e}")
                self._status_label.setText("Error copying to clipboard")
    
    def on_settings(self) -> None:
        """Open settings dialog"""
        try:
            if self._settings_dialog is None:
                self._settings_dialog = SettingsDialog(self)
                self._settings_dialog.settings_saved.connect(self._on_settings_saved)
            
            self._settings_dialog.show()
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
        except Exception as e:
            logger.error(f"Error opening settings: {e}")
    
    def _on_settings_saved(self) -> None:
        """Handle settings saved event"""
        logger.info("Settings saved, reloading configuration...")
        self._config = config.get_config()
        # Could refresh UI elements here if needed
    
    def on_tray_activated(self, reason) -> None:
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()
            self.raise_()
    
    def update_clipboard(self) -> None:
        """Update clipboard display"""
        try:
            clipboard = get_clipboard()
            text = clipboard.get_text()
            
            if text:
                # Truncate if too long
                display_text = text
                if len(text) > 100:
                    display_text = text[:100] + "..."
                self._clipboard_text.setText(display_text)
            else:
                self._clipboard_text.setText("Empty")
        except Exception as e:
            logger.debug(f"Error updating clipboard: {e}")
            self._clipboard_text.setText("Unavailable")
    
    def closeEvent(self, event) -> None:
        """Handle close event"""
        # Stop transcription
        if self._transcriber:
            try:
                self._transcriber.stop()
            except Exception as e:
                logger.error(f"Error stopping transcriber: {e}")
        
        # Hide instead of close if configured
        try:
            if hasattr(self._config, 'ui') and hasattr(self._config.ui, 'minimize_to_tray') and self._config.ui.minimize_to_tray:
                event.ignore()
                self.hide()
            else:
                # Cleanup
                if self._tray_icon:
                    self._tray_icon.hide()
                event.accept()
        except AttributeError:
            # If minimize_to_tray attribute doesn't exist, just accept the close
            if self._tray_icon:
                self._tray_icon.hide()
            event.accept()
    
    def showEvent(self, event) -> None:
        """Handle show event"""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
    
    def keyPressEvent(self, event) -> None:
        """Handle key press events"""
        # Check for global hotkey
        if event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if event.key() == Qt.Key.Key_Space:
                if self._is_listening:
                    self.on_stop_dictation()
                else:
                    self.on_start_dictation()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_O:
                # Toggle overlay
                if self._overlay:
                    if self._overlay.isVisible():
                        self._overlay.hide()
                    else:
                        self._overlay.show()
                event.accept()
                return
        
        super().keyPressEvent(event)


# Global main window instance
_main_window: Optional[MainWindow] = None


def get_main_window() -> MainWindow:
    """Get the global main window instance"""
    global _main_window
    if _main_window is None:
        _main_window = MainWindow()
    return _main_window


def show_main_window() -> None:
    """Show the main window"""
    window = get_main_window()
    window.show()


def hide_main_window() -> None:
    """Hide the main window"""
    global _main_window
    if _main_window:
        _main_window.hide()
