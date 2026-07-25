"""
Configuration management for AIOP
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from . import logging

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
    model_type: str = "whisper-1"
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
    

@dataclass
class AIConfig:
    """AI configuration"""
    default_model: str = "llama3:8b"
    local_models_dir: str = "models"
    cloud_providers: List[str] = field(default_factory=lambda: ["openai", "anthropic"])
    max_context: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    

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
    

class ConfigManager:
    """Configuration manager for AIOP"""
    
    def __init__(self, config_dir: str = "config", config_name: str = "config.yaml"):
        self.config_dir = Path(config_dir)
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
            self._save_config()
    
    def _update_config(self, config_data: Dict[str, Any]) -> None:
        """Update configuration from dictionary"""
        if 'audio' in config_data:
            self.config.audio = AudioConfig(**config_data['audio'])
        if 'speech' in config_data:
            self.config.speech = SpeechConfig(**config_data['speech'])
        if 'windows' in config_data:
            self.config.windows = WindowsConfig(**config_data['windows'])
        if 'ai' in config_data:
            self.config.ai = AIConfig(**config_data['ai'])
        if 'automation' in config_data:
            self.config.automation = AutomationConfig(**config_data['automation'])
        if 'plugin' in config_data:
            self.config.plugin = PluginConfig(**config_data['plugin'])
        if 'mcp' in config_data:
            self.config.mcp = MCPConfig(**config_data['mcp'])
        if 'ui' in config_data:
            self.config.ui = UIConfig(**config_data['ui'])
    
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
