"""
Dictation overlay for AIOP
"""

import time
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QTextCursor
from typing import Optional, Callable
from ..core import logging
from ..speech import TranscriptionResult

logger = logging.get_logger(__name__)


class DictationOverlay(QWidget):
    """Floating overlay for voice dictation"""
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self._setup_ui()
        self._setup_styles()
        self._setup_position()
        
        # State
        self._is_listening = False
        self._last_activity_time = 0
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.timeout.connect(self._on_auto_hide)
        self._auto_hide_timer.setSingleShot(True)
        
        # Callbacks
        self._on_transcription_callbacks = []
        self._on_state_change_callbacks = []
    
    def _setup_ui(self) -> None:
        """Set up UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        self._status_label = QLabel("Ready")
        self._status_label.setFont(QFont("Segoe UI", 10))
        self._status_label.setStyleSheet("color: #a0a0a0;")
        header_layout.addWidget(self._status_label)
        
        header_layout.addStretch()
        
        self._close_button = QPushButton("×")
        self._close_button.setFixedSize(24, 24)
        self._close_button.setStyleSheet(
            "QPushButton { background-color: transparent; color: #a0a0a0; border: none; font-size: 16px; }"
            "QPushButton:hover { color: #e0e0e0; }"
        )
        self._close_button.clicked.connect(self.hide)
        header_layout.addWidget(self._close_button)
        
        layout.addLayout(header_layout)
        
        # Transcription area
        self._transcription_edit = QTextEdit()
        self._transcription_edit.setReadOnly(True)
        self._transcription_edit.setFont(QFont("Segoe UI", 11))
        self._transcription_edit.setStyleSheet(
            "QTextEdit { background-color: #252525; color: #e0e0e0; border: 1px solid #404040; border-radius: 4px; padding: 8px; }"
        )
        self._transcription_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._transcription_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._transcription_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self._transcription_edit)
        
        # Footer
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(8)
        
        self._hint_label = QLabel("Press Ctrl+Shift+Space to start")
        self._hint_label.setFont(QFont("Segoe UI", 9))
        self._hint_label.setStyleSheet("color: #606060;")
        footer_layout.addWidget(self._hint_label)
        
        footer_layout.addStretch()
        
        self._clear_button = QPushButton("Clear")
        self._clear_button.setFixedSize(60, 24)
        self._clear_button.setStyleSheet(
            "QPushButton { background-color: #303030; color: #a0a0a0; border: 1px solid #404040; border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { background-color: #404040; }"
        )
        self._clear_button.clicked.connect(self.clear)
        footer_layout.addWidget(self._clear_button)
        
        layout.addLayout(footer_layout)
    
    def _setup_styles(self) -> None:
        """Set up styles"""
        self.setStyleSheet(
            "DictationOverlay { background-color: #1e1e1e; border: 1px solid #404040; border-radius: 8px; }"
        )
    
    def _setup_position(self) -> None:
        """Set up initial position"""
        # Position at bottom right of primary screen
        screen = self.screen()
        if screen:
            screen_geometry = screen.geometry()
            width = 400
            height = 200
            x = screen_geometry.width() - width - 20
            y = screen_geometry.height() - height - 20
            self.setGeometry(x, y, width, height)
    
    def set_position(self, position: str, offset: tuple = (20, 20)) -> None:
        """Set overlay position"""
        screen = self.screen()
        if not screen:
            return
        
        screen_geometry = screen.geometry()
        width = self.width()
        height = self.height()
        
        if position == "top_left":
            x, y = offset
        elif position == "top_right":
            x = screen_geometry.width() - width - offset[0]
            y = offset[1]
        elif position == "bottom_left":
            x = offset[0]
            y = screen_geometry.height() - height - offset[1]
        elif position == "bottom_right":
            x = screen_geometry.width() - width - offset[0]
            y = screen_geometry.height() - height - offset[1]
        elif position == "center":
            x = (screen_geometry.width() - width) // 2
            y = (screen_geometry.height() - height) // 2
        else:
            return
        
        self.move(x, y)
    
    def set_listening(self, listening: bool) -> None:
        """Set listening state"""
        self._is_listening = listening
        
        if listening:
            self._status_label.setText("Listening...")
            self._status_label.setStyleSheet("color: #40c040;")
            self._hint_label.setText("Speak now...")
            self._hint_label.setStyleSheet("color: #40c040;")
        else:
            self._status_label.setText("Ready")
            self._status_label.setStyleSheet("color: #a0a0a0;")
            self._hint_label.setText("Press Ctrl+Shift+Space to start")
            self._hint_label.setStyleSheet("color: #606060;")
        
        # Notify callbacks
        for callback in self._on_state_change_callbacks:
            try:
                callback(listening)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
    
    def is_listening(self) -> bool:
        """Check if currently listening"""
        return self._is_listening
    
    def append_text(self, text: str) -> None:
        """Append text to transcription"""
        cursor = self._transcription_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._transcription_edit.setTextCursor(cursor)
        self._transcription_edit.insertPlainText(text)
        
        # Scroll to end
        self._transcription_edit.ensureCursorVisible()
        
        # Update activity time
        self._last_activity_time = time.time()
        self._auto_hide_timer.start(3000)  # Auto-hide after 3 seconds of inactivity
    
    def set_text(self, text: str) -> None:
        """Set transcription text"""
        self._transcription_edit.setPlainText(text)
        self._last_activity_time = time.time()
        self._auto_hide_timer.start(3000)
    
    def clear(self) -> None:
        """Clear transcription"""
        self._transcription_edit.clear()
        self._last_activity_time = time.time()
    
    def get_text(self) -> str:
        """Get current transcription text"""
        return self._transcription_edit.toPlainText()
    
    def _on_auto_hide(self) -> None:
        """Handle auto-hide timer"""
        if not self._is_listening and time.time() - self._last_activity_time >= 3.0:
            self.hide()
    
    def show(self) -> None:
        """Show overlay"""
        super().show()
        self.activateWindow()
        self._auto_hide_timer.stop()
    
    def hide(self) -> None:
        """Hide overlay"""
        super().hide()
        self._auto_hide_timer.stop()
    
    def toggle(self) -> None:
        """Toggle overlay visibility"""
        if self.isVisible():
            self.hide()
        else:
            self.show()
    
    def add_transcription_callback(self, callback: Callable[[str], None]) -> None:
        """Add callback for transcription updates"""
        self._on_transcription_callbacks.append(callback)
    
    def add_state_change_callback(self, callback: Callable[[bool], None]) -> None:
        """Add callback for state changes"""
        self._on_state_change_callbacks.append(callback)
    
    def on_transcription_result(self, result: TranscriptionResult) -> None:
        """Handle transcription result"""
        if result.text:
            self.append_text(result.text + " ")
        
        # Notify callbacks
        for callback in self._on_transcription_callbacks:
            try:
                callback(result.text)
            except Exception as e:
                logger.error(f"Error in transcription callback: {e}")
    
    def set_hint_text(self, text: str) -> None:
        """Set hint text"""
        self._hint_label.setText(text)
    
    def resize_overlay(self, width: int, height: int) -> None:
        """Resize overlay"""
        self.resize(width, height)
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse press for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.globalPosition().toPoint()
            self._window_start_position = self.pos()
            event.accept()
    
    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_start_position'):
            delta = event.globalPosition().toPoint() - self._drag_start_position
            self.move(self._window_start_position + delta)
            event.accept()
    
    def enterEvent(self, event) -> None:
        """Handle mouse enter"""
        self._auto_hide_timer.stop()
        super().enterEvent(event)
    
    def leaveEvent(self, event) -> None:
        """Handle mouse leave"""
        if not self._is_listening:
            self._auto_hide_timer.start(3000)
        super().leaveEvent(event)


# Global overlay instance
_overlay: Optional[DictationOverlay] = None


def get_overlay() -> DictationOverlay:
    """Get the global dictation overlay instance"""
    global _overlay
    if _overlay is None:
        _overlay = DictationOverlay()
    return _overlay


def show_overlay() -> None:
    """Show the dictation overlay"""
    get_overlay().show()


def hide_overlay() -> None:
    """Hide the dictation overlay"""
    get_overlay().hide()


def toggle_overlay() -> None:
    """Toggle the dictation overlay"""
    get_overlay().toggle()


def set_overlay_listening(listening: bool) -> None:
    """Set overlay listening state"""
    get_overlay().set_listening(listening)


def append_to_overlay(text: str) -> None:
    """Append text to overlay"""
    get_overlay().append_text(text)


def clear_overlay() -> None:
    """Clear overlay text"""
    get_overlay().clear()
