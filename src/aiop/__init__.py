"""
AI Operating Platform (AIOP)

Next-Generation Windows AI Productivity Suite
"""

__version__ = "0.1.0"
__author__ = "Mahi Maher"
__license__ = "Apache-2.0"

from .core import config, logging
from . import audio, speech, windows, ui

# Note: ai, automation, plugins, and mcp modules are planned for future phases
# from . import ai, automation, plugins, mcp

# Initialize logging
logger = logging.get_logger(__name__)
logger.info(f"AIOP v{__version__} initializing...")
