"""
Dictation overlay for AIOP
"""

import time
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPalette, QTextCursor, QPainter, QPen, QBrush
from typing import Optional, Callable
from ..core import logging
from ..speech import TranscriptionResult

logger = logging.get_logger(__name__)


class ListeningButton(QPushButton):
    """Custom-painted microphone control with a calm listening pulse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._listening = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self.setFixedSize(58, 58)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_listening(self, listening: bool) -> None:
        self._listening = listening
        if listening:
            self._timer.start(32)
        else:
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def _advance(self) -> None:
        self._phase = (self._phase + 0.08) % 6.283
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().center()

        if self._listening:
            pulse = 2.0 + (1.0 + __import__("math").sin(self._phase)) * 2.0
            painter.setPen(QPen(QColor(232, 112, 102, 90), 2.0))
            painter.drawEllipse(center, int(27 + pulse), int(27 + pulse))
            fill = QColor("#e07066")
            icon = QColor("#ffffff")
        else:
            fill = QColor("#27313a")
            icon = QColor("#dce5ec")

        painter.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
        painter.setBrush(QBrush(fill))
        painter.drawEllipse(center, 27, 27)

        painter.setPen(QPen(icon, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawRoundedRect(center.x() - 6, center.y() - 14, 12, 21, 6, 6)
        painter.drawArc(center.x() - 12, center.y() - 7, 24, 22, 200 * 16, 140 * 16)
        painter.drawLine(center.x(), center.y() + 15, center.x(), center.y() + 20)
        painter.drawLine(center.x() - 7, center.y() + 20, center.x() + 7, center.y() + 20)


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
        self._on_toggle_callbacks = []
        self._opacity_effect = QGraphicsOpacityEffect(self._listen_button)
        self._listen_button.setGraphicsEffect(self._opacity_effect)
        self._pulse_animation = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._pulse_animation.setDuration(900)
        self._pulse_animation.setStartValue(0.65)
        self._pulse_animation.setEndValue(1.0)
        self._pulse_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_animation.setLoopCount(-1)
    
    def _setup_ui(self) -> None:
        """Set up UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)
        
        self._listen_button = ListeningButton()
        self._listen_button.setToolTip("Start listening")
        self._listen_button.clicked.connect(self._emit_toggle)
        layout.addWidget(self._listen_button)

        self._status_label = QLabel("Ready")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("color: #9aa0a6; font-size: 11px; font-weight: 600;")
        self._status_label.hide()
        layout.addWidget(self._status_label)
        self._hint_label = QLabel()
        self._hint_label.hide()
        self._transcription_edit = QTextEdit()
        self._transcription_edit.hide()
        self._close_button = QPushButton()
        self._close_button.hide()
        self._clear_button = QPushButton()
        self._clear_button.hide()
    
    def _setup_styles(self) -> None:
        """Set up styles"""
        self.setStyleSheet(
            "DictationOverlay { background-color: #202124; border: 1px solid #4a4d52; border-radius: 38px; }"
            "QPushButton { background-color: #30343a; color: #d9dde3; border: 2px solid #58616d; border-radius: 26px; font-size: 22px; }"
            "QPushButton:hover { background-color: #3b4048; color: #ffffff; }"
        )
    
    def _setup_position(self) -> None:
        """Set up initial position"""
        # Position at bottom right of primary screen
        screen = self.screen()
        if screen:
            screen_geometry = screen.geometry()
            width = 64
            height = 64
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
        self._status_label.hide()
        self._resize_control(64, 64)
        self._listen_button.set_listening(listening)
        
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

        self._listen_button.setToolTip("Stop listening" if listening else "Start listening")
        self._set_button_style("#d95f59" if listening else "#30343a", "#ffffff" if listening else "#d9dde3")
        if listening:
            self._pulse_animation.start()
        else:
            self._pulse_animation.stop()
            self._opacity_effect.setOpacity(1.0)
        
        # Notify callbacks
        for callback in self._on_state_change_callbacks:
            try:
                callback(listening)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    def set_state(self, state: str, message: str = "") -> None:
        """Show a transient processing or execution state."""
        self._is_listening = False
        self._pulse_animation.stop()
        self._opacity_effect.setOpacity(1.0)
        self._status_label.setText(message or state.title())
        color = "#5dcf8b" if state == "success" else "#e06b66" if state == "error" else "#75c7c5"
        self._status_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600;")
        self._status_label.show()
        self._resize_control(190, 64)
        self._listen_button.setToolTip(message or state.title())
        self._set_button_style("#30343a", "#75c7c5")

    def _resize_control(self, width: int, height: int) -> None:
        self.setFixedSize(width, height)
        screen = self.screen()
        if screen:
            geometry = screen.availableGeometry()
            self.move(geometry.right() - width - 20, geometry.bottom() - height - 20)

    def _set_button_style(self, background: str, foreground: str) -> None:
        self._listen_button.setStyleSheet("QPushButton { background: transparent; border: none; }")
    
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

    def add_toggle_callback(self, callback: Callable[[], None]) -> None:
        """Add callback for the listening button."""
        self._on_toggle_callbacks.append(callback)

    def set_feedback(self, message: str, success: bool = True) -> None:
        """Show the latest action result without opening a foreground panel."""
        self.set_state("success" if success else "error", message)
        self._listen_button.setToolTip(message)
        color = "#5dcf8b" if success else "#e06b66"
        self._set_button_style(color, "#ffffff")
        QTimer.singleShot(1800, lambda: self.set_listening(False))

    def _emit_toggle(self) -> None:
        for callback in self._on_toggle_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in toggle callback: {e}")
    
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
