"""
Tests for core modules
"""

import pytest
from aiop.core import config, logging, utils


def test_config_manager():
    """Test configuration manager"""
    manager = config.ConfigManager()
    cfg = manager.get_config()
    
    assert cfg is not None
    assert cfg.audio is not None
    assert cfg.speech is not None
    assert cfg.windows is not None


def test_utils_directories():
    """Test utility directory functions"""
    app_data = utils.get_app_data_dir()
    assert app_data.exists() or app_data.parent.exists()
    
    models_dir = utils.get_models_dir()
    assert models_dir.exists() or models_dir.parent.exists()


def test_utils_id_generation():
    """Test ID generation"""
    id1 = utils.generate_id()
    id2 = utils.generate_id()
    
    assert id1 != id2
    assert len(id1) == 8


def test_utils_hash():
    """Test hashing"""
    text = "test"
    hash1 = utils.hash_text(text)
    hash2 = utils.hash_text(text)
    
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hash length


def test_utils_platform():
    """Test platform detection"""
    assert utils.is_windows() or utils.is_mac() or utils.is_linux()


def test_logging():
    """Test logging setup"""
    logger = logging.get_logger("test")
    assert logger is not None
    
    # This should not raise an exception
    logger.info("Test log message")
    logger.error("Test error message")
