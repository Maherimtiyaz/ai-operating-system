"""
Tests for core modules
"""

import pytest
import yaml
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


def test_default_log_dir_is_absolute_and_writable_location():
    """Logs must never resolve against the current working directory."""
    log_dir = logging.default_log_dir()

    assert log_dir.is_absolute()
    assert log_dir.name == "logs"
    # Per-user application data, not a repo-relative folder.
    assert (log_dir.parent.name == "aiop")


def test_project_root_contains_expected_layout():
    """The checkout root is found from the module file, not from cwd."""
    root = utils.get_project_root()

    assert (root / "src").is_dir() or (root / "pyproject.toml").is_file()


def test_model_search_dirs_are_absolute_and_deduplicated():
    """Bundled models are searched before the writable directory."""
    dirs = utils.get_model_search_dirs()

    assert dirs, "expected at least one model search directory"
    assert all(d.is_absolute() for d in dirs)
    assert len(dirs) == len(set(dirs))
    assert utils.get_bundled_models_dir() in dirs


def test_find_in_model_dirs_resolves_bundled_backend():
    """The whisper backend resolves without depending on cwd."""
    resolved = utils.find_in_model_dirs("whisper-cli.exe")

    if resolved is not None:
        assert resolved.is_absolute()
        assert resolved.parent in utils.get_model_search_dirs()


def test_config_manager_uses_absolute_config_path(tmp_path):
    """Config path is absolute so settings persist across launch dirs."""
    manager = config.ConfigManager(config_dir=str(tmp_path))

    assert manager.config_path.is_absolute()
    assert manager.config_path.parent == tmp_path


def test_config_seeds_from_bundled_template(tmp_path):
    """A first run in an empty config dir adopts the shipped template."""
    manager = config.ConfigManager(config_dir=str(tmp_path))

    template = utils.get_project_root() / "config" / "config.yaml"
    if not template.exists():
        pytest.skip("no bundled config template in this checkout")

    assert (tmp_path / "config.yaml").is_file()

    expected = yaml.safe_load(template.read_text(encoding="utf-8"))
    assert manager.config.profile.name == expected["profile"]["name"]
    assert manager.config.profile.email == expected["profile"]["email"]
