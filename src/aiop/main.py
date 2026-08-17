#!/usr/bin/env python3
"""
Main entry point for AI Operating Platform
"""

import sys
import os
from pathlib import Path
from typing import Optional
from .core import logging, config, utils
from .ui import TrayApp, run_tray_app

logger = logging.get_logger(__name__)


def setup_environment() -> None:
    """Set up environment for AIOP"""
    # Ensure required directories exist
    utils.ensure_directories()
    
    # Set up logging
    log_dir = utils.get_logs_dir()
    logging.setup_logging(log_dir=str(log_dir), log_level="INFO")
    
    # Load configuration
    config_dir = utils.get_config_dir()
    config_manager = config.get_config_manager()
    
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
    """Check if whisper.cpp library is available"""
    from .speech.whisper_cpp import WhisperCPP
    
    try:
        whisper = WhisperCPP()
        return True
    except Exception as e:
        logger.warning(f"whisper.cpp library not available: {e}")
        return False


def main() -> int:
    """Main entry point"""
    # Setup environment
    setup_environment()
    
    # Check dependencies
    if not check_dependencies():
        print("Error: Missing dependencies. Please install required packages.")
        print("Run: pip install -e .[dev]")
        return 1
    
    # Check whisper library
    if not check_whisper_library():
        print("Warning: whisper.cpp library not found.")
        print("Please download from https://github.com/ggerganov/whisper.cpp")
        print("and place whisper.dll in the models directory.")
    
    # Run application
    try:
        return run_tray_app()
    except Exception as e:
        logger.error(f"Application error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
