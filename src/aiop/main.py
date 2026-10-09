#!/usr/bin/env python3
"""
Main entry point for AI Operating Platform
"""

import os
import sys
import ctypes
import traceback
from .core import logging, config, utils
from .ui import run_tray_app

logger = logging.get_logger(__name__)

ERROR_ALREADY_EXISTS = 183
_instance_mutex: object = None


def acquire_single_instance_lock() -> bool:
    """Hold a named mutex for the lifetime of this process.

    A second launch used to fail later with Windows error 1409 because the
    hotkeys and tray icon were already owned by the first instance.
    """
    global _instance_mutex

    if os.name != "nt":
        return True
    if _instance_mutex is not None:
        return True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    # HANDLE is a pointer; the default c_int restype truncates it on x64.
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.CreateMutexW(None, False, "Local\\AIOP_SingleInstance")
    if not handle:
        logger.warning("Could not create instance mutex (error %s)", ctypes.get_last_error())
        return True
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _instance_mutex = handle
    return True


def setup_environment() -> None:
    """Set up environment for AIOP"""
    # Ensure required directories exist
    utils.ensure_directories()
    
    # Set up logging
    log_dir = utils.get_logs_dir()
    log_level = os.environ.get("AIOP_LOG_LEVEL", "INFO")
    logging.setup_logging(log_dir=str(log_dir), log_level=log_level)
    
    # Load configuration
    config_dir = utils.get_config_dir()
    config.get_config_manager()
    
    logger.info("AI Operating Platform starting...")
    logger.info(f"Config directory: {config_dir}")
    logger.info(f"Log directory: {log_dir}")


def check_dependencies() -> bool:
    """Check if all dependencies are available"""
    required_packages = [
        "PyQt6",
        "pyaudio",
        "webrtcvad",
        "numpy",
        "yaml",  # PyYAML package
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        return False
    
    return True


def check_whisper_library() -> bool:
    """Check for a usable whisper.cpp backend and report which one it is."""
    try:
        from .speech.whisper_cpp import WhisperCPP
    except Exception as error:
        logger.warning("whisper backend unavailable: %s", error)
        return False

    try:
        whisper = WhisperCPP()
    except Exception as error:
        logger.warning("whisper.cpp library not available: %s", error)
        print("Speech transcription is unavailable: whisper.dll was not found.")
        print("Place whisper.dll, ggml.dll, ggml-cpu-*.dll and ggml-base.en.bin in models/.")
        return False

    if whisper.lib is None and whisper.cli_path is None:
        logger.warning("Neither whisper.dll nor whisper-cli.exe is usable")
        print("Speech transcription is unavailable: no usable whisper backend in models/.")
        print("Place whisper.dll and its ggml-*.dll dependencies in models/.")
        return False

    logger.info("whisper backend: %s", "whisper.dll" if whisper.lib else "whisper-cli.exe")
    return True


def diagnostic_report() -> int:
    """Print the resolved runtime paths and exit, for packaged-build support."""
    from .core import utils as path_util
    from .speech import model_manager

    print("frozen:", path_util.is_frozen())
    print("python:", sys.version.split()[0])
    print("application dir:", path_util.get_project_root())
    print("bundled models:", path_util.get_bundled_models_dir())
    print("writable models:", path_util.get_models_dir())
    print("config dir:", path_util.get_config_dir())

    manager = model_manager.get_model_manager()
    for name in ("base.en", "tiny.en", "base"):
        model = manager.get_model(name)
        if not model:
            continue
        local = manager.get_model_path(name)
        print(f"model[{name}]: {local if local else 'not downloaded'}")

    print("backend: ", end="")
    try:
        from .speech.whisper_cpp import WhisperCPP

        whisper = WhisperCPP()
        if whisper.lib is not None:
            print("whisper.dll")
        elif whisper.cli_path is not None:
            print("whisper-cli.exe")
        else:
            print("none")
    except Exception as error:
        print(f"unavailable ({error})")
    return 0


def main() -> int:
    """Main entry point"""
    if any(flag in sys.argv for flag in ("--check", "-c")):
        return diagnostic_report()

    if not acquire_single_instance_lock():
        logger.info("Another instance is already running; exiting")
        print("AI Operating Platform is already running.")
        return 0

    # Setup environment
    setup_environment()
    
    # Check dependencies
    if not check_dependencies():
        print("Error: Missing dependencies. Please install required packages.")
        print("Run: pip install -e .[dev]")
        return 1
    
    # Check whisper library
    check_whisper_library()
    
    # Run application
    try:
        return run_tray_app()
    except Exception as e:
        logger.error(f"Application error: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
