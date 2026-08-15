"""
UI components for AIOP

Note: UI modules require PyQt6 and related libraries.
Import individual modules directly if you want to avoid loading the full UI.
"""

try:
    from .main_window import MainWindow
    from .tray_app import TrayApp
    from .overlay import DictationOverlay
    from .settings_dialog import SettingsDialog
    from . import widgets, styles
    
    __all__ = [
        "MainWindow",
        "TrayApp",
        "DictationOverlay",
        "SettingsDialog",
        "widgets",
        "styles",
    ]
except ImportError as e:
    # PyQt6 or related libraries not available
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"UI modules not available: {e}")
    __all__ = []
