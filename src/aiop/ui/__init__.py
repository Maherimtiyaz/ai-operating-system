"""
UI components for AIOP

Note: UI modules require PyQt6 and related libraries.
Import individual modules directly if you want to avoid loading the full UI.
"""

try:
    from .main_window import MainWindow, get_main_window, show_main_window, hide_main_window
    from .tray_app import TrayApp, run_tray_app
    from .overlay import DictationOverlay, get_overlay
    from .settings_dialog import SettingsDialog, show_settings_dialog
    from . import styles
    
    __all__ = [
        "MainWindow",
        "get_main_window",
        "show_main_window",
        "hide_main_window",
        "TrayApp",
        "run_tray_app",
        "DictationOverlay",
        "get_overlay",
        "SettingsDialog",
        "show_settings_dialog",
        "styles",
    ]
except ImportError as e:
    # PyQt6 or related libraries not available
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"UI modules not available: {e}")
    __all__ = []
