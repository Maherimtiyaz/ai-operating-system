"""
Utility functions for AIOP
"""

import os
import sys
import time
import hashlib
import json
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from . import logging

logger = logging.get_logger(__name__)


def get_app_data_dir(app_name: str = "aiop") -> Path:
    """Get the application data directory"""
    if platform.system() == "Windows":
        app_data = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        return Path(app_data) / app_name
    elif platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    else:  # Linux
        return Path.home() / ".config" / app_name


def get_cache_dir(app_name: str = "aiop") -> Path:
    """Get the cache directory"""
    if platform.system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        return Path(local_app_data) / app_name / "cache"
    elif platform.system() == "Darwin":
        return Path.home() / "Library" / "Caches" / app_name
    else:  # Linux
        return Path.home() / ".cache" / app_name


def get_models_dir() -> Path:
    """Get the models directory"""
    return get_app_data_dir() / "models"


def get_plugins_dir() -> Path:
    """Get the plugins directory"""
    return get_app_data_dir() / "plugins"


def get_workflows_dir() -> Path:
    """Get the workflows directory"""
    return get_app_data_dir() / "workflows"


def get_config_dir() -> Path:
    """Get the config directory"""
    return get_app_data_dir() / "config"


def get_logs_dir() -> Path:
    """Get the logs directory"""
    return get_app_data_dir() / "logs"


def ensure_directories() -> None:
    """Ensure all required directories exist"""
    directories = [
        get_app_data_dir(),
        get_cache_dir(),
        get_models_dir(),
        get_plugins_dir(),
        get_workflows_dir(),
        get_config_dir(),
        get_logs_dir(),
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def generate_id(prefix: str = "", length: int = 8) -> str:
    """Generate a unique ID"""
    import uuid
    if prefix:
        return f"{prefix}_{uuid.uuid4().hex[:length]}"
    return uuid.uuid4().hex[:length]


def hash_text(text: str, algorithm: str = "sha256") -> str:
    """Hash text using the specified algorithm"""
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(text.encode("utf-8"))
    return hash_obj.hexdigest()


def read_json_file(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """Read a JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read JSON file {file_path}: {e}")
        return None


def write_json_file(file_path: Union[str, Path], data: Dict[str, Any]) -> bool:
    """Write a JSON file"""
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to write JSON file {file_path}: {e}")
        return False


def read_text_file(file_path: Union[str, Path]) -> Optional[str]:
    """Read a text file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read text file {file_path}: {e}")
        return None


def write_text_file(file_path: Union[str, Path], content: str) -> bool:
    """Write a text file"""
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Failed to write text file {file_path}: {e}")
        return False


def get_file_extension(file_path: Union[str, Path]) -> str:
    """Get file extension"""
    return Path(file_path).suffix.lower()


def get_file_name(file_path: Union[str, Path]) -> str:
    """Get file name without extension"""
    return Path(file_path).stem


def get_file_size(file_path: Union[str, Path]) -> int:
    """Get file size in bytes"""
    try:
        return Path(file_path).stat().st_size
    except Exception:
        return 0


def is_windows() -> bool:
    """Check if running on Windows"""
    return platform.system() == "Windows"


def is_mac() -> bool:
    """Check if running on macOS"""
    return platform.system() == "Darwin"


def is_linux() -> bool:
    """Check if running on Linux"""
    return platform.system() == "Linux"


def get_python_version() -> Tuple[int, int, int]:
    """Get Python version as tuple"""
    return sys.version_info[:3]


def check_python_version(min_version: Tuple[int, int, int]) -> bool:
    """Check if Python version meets minimum requirement"""
    return sys.version_info >= min_version


def format_bytes(size: int) -> str:
    """Format bytes to human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def format_time(seconds: float) -> str:
    """Format seconds to human-readable string"""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def parse_hotkey(hotkey: str) -> Tuple[int, int]:
    """
    Parse hotkey string to modifiers and key code
    
    Args:
        hotkey: Hotkey string (e.g., "Ctrl+Shift+Space")
    
    Returns:
        Tuple of (modifiers, virtual key code)
    """
    from .windows.hotkeys import parse_hotkey_string
    return parse_hotkey_string(hotkey)


def get_timestamp() -> str:
    """Get current timestamp"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def get_date_string() -> str:
    """Get current date string"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def get_time_string() -> str:
    """Get current time string"""
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max"""
    return max(min_val, min(max_val, value))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation"""
    return a + (b - a) * t


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Smoothstep function"""
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# Initialize directories on import
ensure_directories()
