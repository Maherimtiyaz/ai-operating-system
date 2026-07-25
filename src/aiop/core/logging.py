"""
Logging configuration for AIOP
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

# Log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Default log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class AIOPLogger:
    """Custom logger for AIOP with file and console handlers"""

    def __init__(
        self,
        name: str,
        log_dir: str = "logs",
        log_level: str = "INFO",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Set up logger with file and console handlers"""
        logger = logging.getLogger(self.name)
        logger.setLevel(self.log_level)

        # Prevent duplicate handlers
        if logger.handlers:
            return logger

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # File handler with rotation
        log_file = self.log_dir / f"{self.name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(
            logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        )

        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def get_logger(self) -> logging.Logger:
        """Get the configured logger"""
        return self.logger


# Global logger instance
_logger: Optional[AIOPLogger] = None


def get_logger(name: str = "aiop") -> logging.Logger:
    """
    Get a logger instance for AIOP

    Args:
        name: Logger name (default: 'aiop')

    Returns:
        Configured logger instance
    """
    global _logger
    if _logger is None:
        _logger = AIOPLogger(name)
    return _logger.get_logger()


def set_log_level(level: str):
    """Set the global log level"""
    global _logger
    if _logger:
        _logger.log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
        for handler in _logger.logger.handlers:
            handler.setLevel(_logger.log_level)


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """
    Set up global logging configuration

    Args:
        log_dir: Directory for log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
    """
    global _logger
    _logger = AIOPLogger("aiop", log_dir, log_level, max_bytes, backup_count)


# Initialize default logging
setup_logging()
