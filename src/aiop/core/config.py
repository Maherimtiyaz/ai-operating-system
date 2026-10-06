"""
Configuration management for AIOP
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, fields
from . import logging, utils

logger = logging.get_logger(__name__)


@dataclass
class AudioConfig:
    """Audio configuration"""
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    format: str = "int16"
    device_index: Optional[int] = None
    

@dataclass
class SpeechConfig:
    """Speech recognition configuration"""
    model_path: str = "models/ggml-base.en.bin"
    language: str = "en"
    beam_size: int = 5
    temperature: float = 0.0
    use_vad: bool = True
    vad_aggressiveness: int = 3
    

@dataclass
class WindowsConfig:
    """Windows integration configuration"""
    hotkey_dictation: str = "Ctrl+Shift+Space"
    hotkey_ai_assistant: str = "Ctrl+Shift+A"
    hotkey_workflows: str = "Ctrl+Shift+W"
    start_on_boot: bool = True
    run_in_tray: bool = True
    minimize_to_tray: bool = True
    hold_to_talk: bool = True
    

@dataclass
class AIConfig:
    """AI configuration"""
    default_model: str = "llama3:8b"
    local_models_dir: str = "models"
    cloud_providers: List[str] = field(default_factory=lambda: ["openai", "anthropic"])
    max_context: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    # OpenAI-compatible endpoint for workflow prompt steps. The API key is
    # always user-supplied: it defaults empty, is never shipped, and can come
    # from the OPENAI_API_KEY environment variable instead.
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    

@dataclass
class AutomationConfig:
    """Automation configuration"""
    workflows_dir: str = "workflows"
    max_concurrent_workflows: int = 5
    timeout_seconds: int = 300
    

@dataclass
class PluginConfig:
    """Plugin configuration"""
    plugins_dir: str = "plugins"
    auto_load: bool = True
    sandbox_enabled: bool = True
    allowed_permissions: List[str] = field(default_factory=lambda: [
        "read:files",
        "write:files",
        "execute:code",
        "access:network",
    ])
    

@dataclass
class MCPConfig:
    """MCP configuration"""
    servers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    auto_discover: bool = True
    timeout_seconds: int = 30
    

@dataclass
class UIConfig:
    """UI configuration"""
    theme: str = "system"
    font_size: int = 12
    overlay_position: str = "bottom_right"
    overlay_width: int = 400
    overlay_height: int = 200
    show_tray_icon: bool = True


@dataclass
class ProfileConfig:
    """Local profile created during first-run onboarding."""
    name: str = ""
    email: str = ""
    completed: bool = False
    

@dataclass
class AIOPConfig:
    """Main AIOP configuration"""
    audio: AudioConfig = field(default_factory=AudioConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    windows: WindowsConfig = field(default_factory=WindowsConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    automation: AutomationConfig = field(default_factory=AutomationConfig)
    plugin: PluginConfig = field(default_factory=PluginConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    profile: ProfileConfig = field(default_factory=ProfileConfig)
    

class ConfigManager:
    """Configuration manager for AIOP"""
    
    def __init__(self, config_dir: Optional[str] = None, config_name: str = "config.yaml"):
        # Defaults to the per-user config directory so settings resolve the
        # same regardless of the working directory the app was launched from.
        self.config_dir = Path(config_dir) if config_dir else utils.get_config_dir()
        self.config_name = config_name
        self.config_path = self.config_dir / config_name
        self.config: AIOPConfig = AIOPConfig()
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                    if config_data:
                        self._update_config(config_data)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
        else:
            self._seed_config_from_template()
            self._save_config()

    def _seed_config_from_template(self) -> None:
        """Adopt the bundled config template on first run.

        Keeps existing settings such as the onboarding profile when the app is
        first run from a checkout that ships a populated config.yaml.
        """
        template_path = utils.get_project_root() / "config" / self.config_name
        if not template_path.exists():
            return
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            if config_data:
                self._update_config(config_data)
                logger.info("Seeded configuration from %s", template_path)
        except Exception as e:
            logger.error(f"Failed to seed config from template: {e}")
    
    def _update_config(self, config_data: Dict[str, Any]) -> None:
        """Update configuration from dictionary.

        Keys the current build no longer defines are dropped rather than
        raising, so a config written by an older or newer version still loads.
        """
        sections = {
            'audio': AudioConfig,
            'speech': SpeechConfig,
            'windows': WindowsConfig,
            'ai': AIConfig,
            'automation': AutomationConfig,
            'plugin': PluginConfig,
            'mcp': MCPConfig,
            'ui': UIConfig,
            'profile': ProfileConfig,
        }
        for name, section_type in sections.items():
            values = config_data.get(name)
            if not isinstance(values, dict):
                continue
            known = {item.name for item in fields(section_type)}
            unknown = [key for key in values if key not in known]
            if unknown:
                logger.warning(
                    "Ignoring unknown '%s' config keys: %s",
                    name,
                    ", ".join(sorted(unknown)),
                )
                values = {key: value for key, value in values.items() if key in known}
            setattr(self.config, name, section_type(**values))
    
    def _save_config(self) -> None:
        """Save configuration to file"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        config_data = {
            'audio': self.config.audio.__dict__,
            'speech': self.config.speech.__dict__,
            'windows': self.config.windows.__dict__,
            'ai': self.config.ai.__dict__,
            'automation': self.config.automation.__dict__,
            'plugin': self.config.plugin.__dict__,
            'mcp': self.config.mcp.__dict__,
            'ui': self.config.ui.__dict__,
            'profile': self.config.profile.__dict__,
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get_config(self) -> AIOPConfig:
        """Get the current configuration"""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """Update configuration values"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                obj = getattr(self.config, key)
                # Handle nested config objects (dataclasses)
                if isinstance(value, dict) and hasattr(obj, '__dataclass_fields__'):
                    for subkey, subvalue in value.items():
                        if hasattr(obj, subkey):
                            setattr(obj, subkey, subvalue)
                else:
                    setattr(self.config, key, value)
        self._save_config()
    
    def reload(self) -> None:
        """Reload configuration from file"""
        self._load_config()
    
    def reset(self) -> None:
        """Reset configuration to defaults"""
        self.config = AIOPConfig()
        self._save_config()


# Global config manager
_config_manager: Optional[ConfigManager] = None


def get_config() -> AIOPConfig:
    """Get the global configuration"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.get_config()


def get_config_manager() -> ConfigManager:
    """Get the global config manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def reload_config() -> None:
    """Reload the global configuration"""
    global _config_manager
    if _config_manager:
        _config_manager.reload()
