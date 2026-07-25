"""
Main window for AIOP
"""

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QTextEdit, QSystemTrayIcon, QMenu, QApplication
)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, QSize, QTimer
from typing import Optional
from ..core import logging, config
from ..speech import SpeechTranscriber, TranscriptionResult
from ..windows import get_clipboard, get_win32_api
from .overlay import DictationOverlay, get_overlay
from .styles import apply_theme, Colors

logger = logging.get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Operating Platform")
        self.setWindowIcon(QIcon(":/assets/icon.png"))
        self.resize(800, 600)
        
        # Configuration
        self._config = config.get_config()
        
        # Components
        self._transcriber: Optional[SpeechTranscriber] = None
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._overlay: Optional[DictationOverlay] = None
        
        # Setup
        self._setup_ui()
        self._setup_tray()
        self._setup_connections()
        self._setup_styles()
    
    def _setup_ui(self) -> None:
        """Set up main UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create stacked widget for different views
        self._stacked_widget = QStackedWidget()
        layout.addWidget(self._stacked_widget)
        
        # Main view
        self._main_view = QWidget()
        self._setup_main_view()
        self._stacked_widget.addWidget(self._main_view)
        
        # Settings view (placeholder)
        self._settings_view = QWidget()
        self._stacked_widget.addWidget(self._settings_view)
        
        # Show main view by default
        self._stacked_widget.setCurrentWidget(self._main_view)
    
    def _setup_main_view(self) -> None:
        """Set up main view"""
        layout = QVBoxLayout(self._main_view)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Header
        header = QHBoxLayout()
        
        self._title_label = QLabel("AI Operating Platform")
        self._title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #e0e0e0;")
        header.addWidget(self._title_label)
        
        header.addStretch()
        
        # Control buttons
        self._minimize_button = QPushButton("_")
        self._minimize_button.setFixedSize(32, 32)
        self._minimize_button.setStyleSheet(
            "QPushButton { background-color: #303030; color: #a0a0a0; border: none; font-size: 16px; }"
            "QPushButton:hover { background-color: #404040; }"
        )
        self._minimize_button.clicked.connect(self.showMinimized)
        header.addWidget(self._minimize_button)
        
        self._close_button = QPushButton("×")
        self._close_button.setFixedSize(32, 32)
        self._close_button.setStyleSheet(
            "QPushButton { background-color: #303030; color: #a0a0a0; border: none; font-size: 16px; }"
            "QPushButton:hover { background-color: #e04040; }"
        )
        self._close_button.clicked.connect(self.close)
        header.addWidget(self._close_button)
        
        layout.addLayout(header)
        
        # Status
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(self._status_label)
        
        # Transcription area
        self._transcription_edit = QTextEdit()
        self._transcription_edit.setReadOnly(True)
        self._transcription_edit.setStyleSheet(
            "QTextEdit { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 8px; }"
        )
        layout.addWidget(self._transcription_edit)
        
        # Control buttons
        controls = QHBoxLayout()
        controls.setSpacing(8)
        
        self._start_button = QPushButton("Start Dictation (Ctrl+Shift+Space)")
        self._start_button.setFixedHeight(40)
        self._start_button.setStyleSheet(
            "QPushButton { background-color: #2a82e4; color: white; border: none; border-radius: 4px; font-size: 12px; padding: 0 16px; }"
            "QPushButton:hover { background-color: #3a92f4; }"
            "QPushButton:pressed { background-color: #1a62c4; }"
        )
        self._start_button.clicked.connect(self.on_start_dictation)
        controls.addWidget(self._start_button)
        
        self._stop_button = QPushButton("Stop Dictation")
        self._stop_button.setFixedHeight(40)
        self._stop_button.setStyleSheet(
            "QPushButton { background-color: #303030; color: #a0a0a0; border: 1px solid #404040; border-radius: 4px; font-size: 12px; padding: 0 16px; }"
            "QPushButton:hover { background-color: #404040; }"
        )
        self._stop_button.clicked.connect(self.on_stop_dictation)
        self._stop_button.setEnabled(False)
        controls.addWidget(self._stop_button)
        
        layout.addLayout(controls)
        
        # Clipboard section
        clipboard_group = QHBoxLayout()
        clipboard_group.setSpacing(8)
        
        self._clipboard_label = QLabel("Clipboard:")
        self._clipboard_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        clipboard_group.addWidget(self._clipboard_label)
        
        self._clipboard_text = QLabel()
        self._clipboard_text.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        self._clipboard_text.setWordWrap(True)
        clipboard_group.addWidget(self._clipboard_text, stretch=1)
        
        self._copy_button = QPushButton("Copy to Clipboard")
        self._copy_button.setFixedHeight(30)
        self._copy_button.setStyleSheet(
            "QPushButton { background-color: #303030; color: #a0a0a0; border: 1px solid #404040; border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { background-color: #404040; }"
        )
        self._copy_button.clicked.connect(self.on_copy_to_clipboard)
        clipboard_group.addWidget(self._copy_button)
        
        layout.addLayout(clipboard_group)
    
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
        """Set up styles"""
        self.setStyleSheet(
            "MainWindow { background-color: #282828; }"
            "QLabel { color: #e0e0e0; }"
        )
    
    def on_start_dictation(self) -> None:
        """Start voice dictation"""
        if not self._transcriber:
            return
        
        self._transcriber.start()
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        self._status_label.setText("Listening...")
        self._status_label.setStyleSheet("color: #40c040;")
        
        # Show overlay
        self._overlay.set_listening(True)
        self._overlay.show()
        
        # Update tray menu
        if self._tray_icon and self._tray_icon.contextMenu():
            for action in self._tray_icon.contextMenu().actions():
                if action.text() == "Start Dictation":
                    action.setEnabled(False)
                elif action.text() == "Stop Dictation":
                    action.setEnabled(True)
    
    def on_stop_dictation(self) -> None:
        """Stop voice dictation"""
        if not self._transcriber:
            return
        
        self._transcriber.stop()
        self._start_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._status_label.setText("Ready")
        self._status_label.setStyleSheet("color: #a0a0a0;")
        
        # Hide overlay
        self._overlay.set_listening(False)
        
        # Update tray menu
        if self._tray_icon and self._tray_icon.contextMenu():
            for action in self._tray_icon.contextMenu().actions():
                if action.text() == "Start Dictation":
                    action.setEnabled(True)
                elif action.text() == "Stop Dictation":
                    action.setEnabled(False)
    
    def on_transcription_result(self, result: TranscriptionResult) -> None:
        """Handle transcription result"""
        if result.text:
            self._transcription_edit.append(result.text + " ")
            
            # Scroll to end
            cursor = self._transcription_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._transcription_edit.setTextCursor(cursor)
            self._transcription_edit.ensureCursorVisible()
    
    def on_overlay_transcription(self, text: str) -> None:
        """Handle overlay transcription"""
        if text:
            self._transcription_edit.append(text + " ")
    
    def on_overlay_state_change(self, listening: bool) -> None:
        """Handle overlay state change"""
        if listening:
            self._status_label.setText("Listening...")
            self._status_label.setStyleSheet("color: #40c040;")
        else:
            self._status_label.setText("Ready")
            self._status_label.setStyleSheet("color: #a0a0a0;")
    
    def on_copy_to_clipboard(self) -> None:
        """Copy transcription to clipboard"""
        text = self._transcription_edit.toPlainText()
        if text:
            clipboard = get_clipboard()
            clipboard.set_text(text)
            self._status_label.setText("Copied to clipboard")
            QTimer.singleShot(2000, lambda: self._status_label.setText("Ready"))
    
    def on_settings(self) -> None:
        """Open settings"""
        self._stacked_widget.setCurrentWidget(self._settings_view)
    
    def on_tray_activated(self, reason) -> None:
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()
    
    def update_clipboard(self) -> None:
        """Update clipboard display"""
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
    
    def closeEvent(self, event) -> None:
        """Handle close event"""
        # Stop transcription
        if self._transcriber:
            self._transcriber.stop()
        
        # Hide instead of close if configured
        if self._config.ui.minimize_to_tray:
            event.ignore()
            self.hide()
        else:
            # Cleanup
            if self._tray_icon:
                self._tray_icon.hide()
            event.accept()
    
    def showEvent(self, event) -> None:
        """Handle show event"""
        super().showEvent(event)
        self.activateWindow()
    
    def keyPressEvent(self, event) -> None:
        """Handle key press events"""
        # Check for global hotkey
        if event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if event.key() == Qt.Key.Key_Space:
                if self._transcriber and self._transcriber.is_running():
                    self.on_stop_dictation()
                else:
                    self.on_start_dictation()
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
