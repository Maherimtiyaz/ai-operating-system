"""
Styles for AIOP UI
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPalette
from PyQt6.QtWidgets import QApplication


# Color palette
class Colors:
    PRIMARY = QColor(42, 130, 228)
    PRIMARY_LIGHT = QColor(100, 180, 255)
    PRIMARY_DARK = QColor(20, 80, 180)
    
    SECONDARY = QColor(50, 50, 50)
    SECONDARY_LIGHT = QColor(100, 100, 100)
    SECONDARY_DARK = QColor(20, 20, 20)
    
    SUCCESS = QColor(40, 180, 40)
    WARNING = QColor(255, 180, 0)
    ERROR = QColor(255, 60, 60)
    INFO = QColor(40, 180, 255)
    
    BACKGROUND = QColor(30, 30, 30)
    BACKGROUND_LIGHT = QColor(45, 45, 45)
    BACKGROUND_DARK = QColor(15, 15, 15)
    
    TEXT = QColor(220, 220, 220)
    TEXT_SECONDARY = QColor(150, 150, 150)
    TEXT_DISABLED = QColor(100, 100, 100)
    
    BORDER = QColor(60, 60, 60)
    BORDER_LIGHT = QColor(80, 80, 80)
    
    TRANSPARENT = QColor(0, 0, 0, 0)
    OVERLAY = QColor(0, 0, 0, 200)


# Fonts
class Fonts:
    REGULAR = QFont("Segoe UI", 10)
    SMALL = QFont("Segoe UI", 8)
    MEDIUM = QFont("Segoe UI", 12)
    LARGE = QFont("Segoe UI", 14)
    TITLE = QFont("Segoe UI", 16, QFont.Weight.Bold)
    MONOSPACE = QFont("Consolas", 10)


# Stylesheets
class Styles:
    MAIN_WINDOW = """
    QMainWindow {
        background-color: #282828;
        color: #e0e0e0;
        border: none;
    }
    """
    
    BUTTON = """
    QPushButton {
        background-color: #3a3a3a;
        color: #e0e0e0;
        border: 1px solid #4a4a4a;
        padding: 8px 16px;
        border-radius: 4px;
        font-size: 12px;
    }
    
    QPushButton:hover {
        background-color: #4a4a4a;
        border-color: #6a6a6a;
    }
    
    QPushButton:pressed {
        background-color: #2a2a2a;
    }
    
    QPushButton:disabled {
        color: #606060;
        background-color: #303030;
    }
    """
    
    PRIMARY_BUTTON = """
    QPushButton {
        background-color: #2a82e4;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-size: 12px;
    }
    
    QPushButton:hover {
        background-color: #3a92f4;
    }
    
    QPushButton:pressed {
        background-color: #1a62c4;
    }
    """
    
    TEXT_EDIT = """
    QTextEdit {
        background-color: #252525;
        color: #e0e0e0;
        border: 1px solid #404040;
        border-radius: 4px;
        padding: 8px;
        font-size: 12px;
    }
    
    QTextEdit:read-only {
        background-color: #1e1e1e;
        border-color: #303030;
    }
    """
    
    LINE_EDIT = """
    QLineEdit {
        background-color: #252525;
        color: #e0e0e0;
        border: 1px solid #404040;
        border-radius: 4px;
        padding: 6px 8px;
        font-size: 12px;
    }
    
    QLineEdit:focus {
        border-color: #2a82e4;
    }
    """
    
    LABEL = """
    QLabel {
        color: #e0e0e0;
        font-size: 12px;
    }
    
    QLabel[disabled="true"] {
        color: #606060;
    }
    """
    
    COMBO_BOX = """
    QComboBox {
        background-color: #252525;
        color: #e0e0e0;
        border: 1px solid #404040;
        border-radius: 4px;
        padding: 6px 8px;
        font-size: 12px;
    }
    
    QComboBox QAbstractItemView {
        background-color: #252525;
        color: #e0e0e0;
        selection-background-color: #2a82e4;
    }
    
    QComboBox::drop-down {
        border: none;
    }
    """
    
    CHECK_BOX = """
    QCheckBox {
        spacing: 8px;
        color: #e0e0e0;
        font-size: 12px;
    }
    
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
    }
    
    QCheckBox::indicator:checked {
        background-color: #2a82e4;
        border: 1px solid #2a82e4;
    }
    """
    
    SCROLL_BAR = """
    QScrollBar:vertical {
        background-color: #252525;
        width: 12px;
        border: none;
    }
    
    QScrollBar::handle:vertical {
        background-color: #404040;
        border-radius: 6px;
        min-height: 20px;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    """
    
    GROUP_BOX = """
    QGroupBox {
        border: 1px solid #404040;
        border-radius: 4px;
        margin-top: 12px;
        padding: 8px;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        color: #e0e0e0;
        font-size: 13px;
        font-weight: bold;
    }
    """
    
    TAB_WIDGET = """
    QTabWidget {
        background-color: #252525;
        color: #e0e0e0;
    }
    
    QTabWidget::pane {
        border: 1px solid #404040;
        border-radius: 4px;
    }
    
    QTabBar::tab {
        background-color: #303030;
        color: #e0e0e0;
        padding: 8px 16px;
        border: none;
        border-radius: 4px 4px 0 0;
    }
    
    QTabBar::tab:selected {
        background-color: #2a82e4;
    }
    """
    
    STATUS_BAR = """
    QStatusBar {
        background-color: #202020;
        color: #a0a0a0;
        font-size: 11px;
        padding: 4px 8px;
    }
    """
    
    OVERLAY = """
    QWidget[overlay="true"] {
        background-color: rgba(0, 0, 0, 200);
        border: 1px solid #404040;
        border-radius: 8px;
        padding: 12px;
    }
    """
    
    DARK_THEME = """
    QApplication {
        palette: dark;
    }
    """


def apply_theme(app: QApplication) -> None:
    """Apply dark theme to application"""
    # Set dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, Colors.BACKGROUND)
    palette.setColor(QPalette.ColorRole.WindowText, Colors.TEXT)
    palette.setColor(QPalette.ColorRole.Base, Colors.BACKGROUND_LIGHT)
    palette.setColor(QPalette.ColorRole.AlternateBase, Colors.BACKGROUND_DARK)
    palette.setColor(QPalette.ColorRole.ToolTipBase, Colors.BACKGROUND_LIGHT)
    palette.setColor(QPalette.ColorRole.ToolTipText, Colors.TEXT)
    palette.setColor(QPalette.ColorRole.Text, Colors.TEXT)
    palette.setColor(QPalette.ColorRole.Button, Colors.BACKGROUND_LIGHT)
    palette.setColor(QPalette.ColorRole.ButtonText, Colors.TEXT)
    palette.setColor(QPalette.ColorRole.BrightText, Colors.TEXT)
    palette.setColor(QPalette.ColorRole.Link, Colors.PRIMARY)
    palette.setColor(QPalette.ColorRole.Highlight, Colors.PRIMARY)
    palette.setColor(QPalette.ColorRole.HighlightedText, Colors.BACKGROUND)
    
    palette.setColor(QPalette.ColorRole.Disabled, QPalette.ColorRole.Text, Colors.TEXT_DISABLED)
    palette.setColor(QPalette.ColorRole.Disabled, QPalette.ColorRole.ButtonText, Colors.TEXT_DISABLED)
    
    app.setPalette(palette)
    app.setStyleSheet(Styles.DARK_THEME)


def apply_styles(widget) -> None:
    """Apply styles to widget and its children"""
    widget.setStyleSheet(
        Styles.BUTTON + "\n" +
        Styles.PRIMARY_BUTTON + "\n" +
        Styles.TEXT_EDIT + "\n" +
        Styles.LINE_EDIT + "\n" +
        Styles.LABEL + "\n" +
        Styles.COMBO_BOX + "\n" +
        Styles.CHECK_BOX + "\n" +
        Styles.SCROLL_BAR + "\n" +
        Styles.GROUP_BOX + "\n" +
        Styles.TAB_WIDGET + "\n" +
        Styles.STATUS_BAR
    )
