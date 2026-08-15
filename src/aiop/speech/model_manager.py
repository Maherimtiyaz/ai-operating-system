"""
Model management for speech recognition
"""

import os
import hashlib
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from ..core import logging, utils
from .language import LanguageInfo, get_language, LANGUAGES

logger = logging.get_logger(__name__)


@dataclass
class ModelInfo:
    """Model information"""
    name: str
    display_name: str
    description: str
    size: str  # e.g., "base", "small", "medium", "large"
    parameters: int  # Number of parameters
    file_size: int  # File size in bytes
    file_name: str
    url: str
    sha256: str
    languages: List[str]  # Supported language codes
    is_multilingual: bool = False
    is_quantized: bool = True
    quantization: str = "q4_0"  # Quantization type
    

@dataclass
class LocalModel:
    """Local model information"""
    path: Path
    info: ModelInfo
    is_downloaded: bool = False
    is_loaded: bool = False


class ModelManager:
    """Manager for speech recognition models"""
    
    # Whisper.cpp model information
    WHISPER_MODELS = {
        "tiny.en": {
            "display_name": "Tiny English",
            "description": "Tiny English-only model",
            "size": "tiny",
            "parameters": 39,
            "file_size": 75 * 1024 * 1024,  # 75MB
            "file_name": "ggml-tiny.en.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin",
            "sha256": "a3d2a127064202d2971a172c6f32394b57c9d73812f7551d4b6a1d6d8a7c31f1",
            "languages": ["en"],
            "is_multilingual": False,
        },
        "tiny": {
            "display_name": "Tiny Multilingual",
            "description": "Tiny multilingual model",
            "size": "tiny",
            "parameters": 39,
            "file_size": 75 * 1024 * 1024,
            "file_name": "ggml-tiny.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
            "sha256": "d2b3e7ff54453dfa058f41564259542157003670668038d37463166239587593",
            "languages": [lang.code for lang in LANGUAGES.values() if lang.code != "en"],
            "is_multilingual": True,
        },
        "base.en": {
            "display_name": "Base English",
            "description": "Base English-only model",
            "size": "base",
            "parameters": 74,
            "file_size": 142 * 1024 * 1024,
            "file_name": "ggml-base.en.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin",
            "sha256": "c17d159a9695c71e68493846b33890a5a067385832923a353f640a5a1b8d1234",
            "languages": ["en"],
            "is_multilingual": False,
        },
        "base": {
            "display_name": "Base Multilingual",
            "description": "Base multilingual model",
            "size": "base",
            "parameters": 74,
            "file_size": 142 * 1024 * 1024,
            "file_name": "ggml-base.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
            "sha256": "4a2236d91789f7565d733a958456c36252f6884929ca936571397e824588034a",
            "languages": [lang.code for lang in LANGUAGES.values()],
            "is_multilingual": True,
        },
        "small.en": {
            "display_name": "Small English",
            "description": "Small English-only model",
            "size": "small",
            "parameters": 244,
            "file_size": 466 * 1024 * 1024,
            "file_name": "ggml-small.en.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin",
            "sha256": "175138e73c1b646686875131319437565896934c87999b5a4568134351f53513",
            "languages": ["en"],
            "is_multilingual": False,
        },
        "small": {
            "display_name": "Small Multilingual",
            "description": "Small multilingual model",
            "size": "small",
            "parameters": 244,
            "file_size": 466 * 1024 * 1024,
            "file_name": "ggml-small.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
            "sha256": "32d247d81943568439403321728843a4d456e742841d159438727e1626985135",
            "languages": [lang.code for lang in LANGUAGES.values()],
            "is_multilingual": True,
        },
        "medium.en": {
            "display_name": "Medium English",
            "description": "Medium English-only model",
            "size": "medium",
            "parameters": 769,
            "file_size": 1481 * 1024 * 1024,
            "file_name": "ggml-medium.en.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.en.bin",
            "sha256": "5184334533933792172e12890399786895341012833572539733259372458321",
            "languages": ["en"],
            "is_multilingual": False,
        },
        "medium": {
            "display_name": "Medium Multilingual",
            "description": "Medium multilingual model",
            "size": "medium",
            "parameters": 769,
            "file_size": 1481 * 1024 * 1024,
            "file_name": "ggml-medium.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
            "sha256": "913694523579957698359124455493211859079283619839226735899195541",
            "languages": [lang.code for lang in LANGUAGES.values()],
            "is_multilingual": True,
        },
        "large-v1": {
            "display_name": "Large v1",
            "description": "Large v1 model (legacy)",
            "size": "large",
            "parameters": 1550,
            "file_size": 2953 * 1024 * 1024,
            "file_name": "ggml-large-v1.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v1.bin",
            "sha256": "2a64429706949d43a72a153c4f567e7b931692483d36749d8189987134148131",
            "languages": [lang.code for lang in LANGUAGES.values()],
            "is_multilingual": True,
        },
        "large-v2": {
            "display_name": "Large v2",
            "description": "Large v2 model",
            "size": "large",
            "parameters": 1550,
            "file_size": 2953 * 1024 * 1024,
            "file_name": "ggml-large-v2.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v2.bin",
            "sha256": "815277523722418644847793554986631925399019979199389939137470194",
            "languages": [lang.code for lang in LANGUAGES.values()],
            "is_multilingual": True,
        },
        "large-v3": {
            "display_name": "Large v3",
            "description": "Large v3 model (latest)",
            "size": "large",
            "parameters": 1550,
            "file_size": 2953 * 1024 * 1024,
            "file_name": "ggml-large-v3.bin",
            "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
            "sha256": "913376094479958898359124455493211859079283619839226735899195541",
            "languages": [lang.code for lang in LANGUAGES.values()],
            "is_multilingual": True,
        },
    }
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models: Dict[str, ModelInfo] = {}
        self.local_models: Dict[str, LocalModel] = {}
        self._load_model_definitions()
        self._scan_local_models()
    
    def _load_model_definitions(self) -> None:
        """Load model definitions"""
        for name, info in self.WHISPER_MODELS.items():
            model_info = ModelInfo(
                name=name,
                display_name=info["display_name"],
                description=info["description"],
                size=info["size"],
                parameters=info["parameters"],
                file_size=info["file_size"],
                file_name=info["file_name"],
                url=info["url"],
                sha256=info["sha256"],
                languages=info["languages"],
                is_multilingual=info["is_multilingual"],
            )
            self.models[name] = model_info
    
    def _scan_local_models(self) -> None:
        """Scan for locally available models"""
        if not self.models_dir.exists():
            self.models_dir.mkdir(parents=True, exist_ok=True)
            return
        
        for model_name, model_info in self.models.items():
            model_path = self.models_dir / model_info.file_name
            if model_path.exists():
                self.local_models[model_name] = LocalModel(
                    path=model_path,
                    info=model_info,
                    is_downloaded=True,
                    is_loaded=False,
                )
    
    def list_models(self) -> List[ModelInfo]:
        """List all available models"""
        return list(self.models.values())
    
    def list_local_models(self) -> List[LocalModel]:
        """List locally available models"""
        return list(self.local_models.values())
    
    def get_model(self, model_name: str) -> Optional[ModelInfo]:
        """Get model information by name"""
        return self.models.get(model_name)
    
    def get_local_model(self, model_name: str) -> Optional[LocalModel]:
        """Get local model by name"""
        return self.local_models.get(model_name)
    
    def is_model_downloaded(self, model_name: str) -> bool:
        """Check if model is downloaded"""
        return model_name in self.local_models
    
    def download_model(self, model_name: str, progress_callback: callable = None) -> bool:
        """
        Download a model
        
        Args:
            model_name: Name of the model to download
            progress_callback: Optional callback for download progress
        
        Returns:
            True if download succeeded, False otherwise
        """
        model_info = self.models.get(model_name)
        if not model_info:
            logger.error(f"Model not found: {model_name}")
            return False
        
        if self.is_model_downloaded(model_name):
            logger.info(f"Model already downloaded: {model_name}")
            return True
        
        try:
            self.models_dir.mkdir(parents=True, exist_ok=True)
            model_path = self.models_dir / model_info.file_name
            
            logger.info(f"Downloading model: {model_name} ({utils.format_bytes(model_info.file_size)})")
            
            # Download with progress
            response = requests.get(model_info.url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            # Verify checksum
            if not self._verify_checksum(model_path, model_info.sha256):
                logger.error(f"Checksum verification failed for {model_name}")
                model_path.unlink()
                return False
            
            # Add to local models
            self.local_models[model_name] = LocalModel(
                path=model_path,
                info=model_info,
                is_downloaded=True,
                is_loaded=False,
            )
            
            logger.info(f"Model downloaded successfully: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download model {model_name}: {e}")
            return False
    
    def _verify_checksum(self, file_path: Path, expected_sha256: str) -> bool:
        """Verify file checksum"""
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return sha256.hexdigest() == expected_sha256
        except Exception as e:
            logger.error(f"Checksum verification error: {e}")
            return False
    
    def delete_model(self, model_name: str) -> bool:
        """Delete a downloaded model"""
        local_model = self.local_models.get(model_name)
        if not local_model:
            return False
        
        try:
            local_model.path.unlink()
            del self.local_models[model_name]
            logger.info(f"Model deleted: {model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete model {model_name}: {e}")
            return False
    
    def get_model_path(self, model_name: str) -> Optional[Path]:
        """Get path to a model file"""
        local_model = self.local_models.get(model_name)
        if local_model:
            return local_model.path
        
        # Check if file exists directly
        model_info = self.models.get(model_name)
        if model_info:
            model_path = self.models_dir / model_info.file_name
            if model_path.exists():
                return model_path
        
        return None
    
    def get_best_model_for_language(self, language_code: str) -> Optional[str]:
        """Get the best model for a specific language"""
        # Prefer English-only models for English
        if language_code == "en":
            for size in ["large-v3", "medium.en", "small.en", "base.en", "tiny.en"]:
                if size in self.models:
                    return size
        
        # For other languages, prefer multilingual models
        for size in ["large-v3", "medium", "small", "base", "tiny"]:
            model_info = self.models.get(size)
            if model_info and (model_info.is_multilingual or language_code in model_info.languages):
                return size
        
        return None
    
    def get_models_for_language(self, language_code: str) -> List[str]:
        """Get all models that support a specific language"""
        models = []
        for name, info in self.models.items():
            if info.is_multilingual or language_code in info.languages:
                models.append(name)
        return models


# Global model manager instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get the global model manager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


def list_models() -> List[ModelInfo]:
    """List all available models"""
    return get_model_manager().list_models()


def list_local_models() -> List[LocalModel]:
    """List locally available models"""
    return get_model_manager().list_local_models()


def download_model(model_name: str, progress_callback: callable = None) -> bool:
    """Download a model"""
    return get_model_manager().download_model(model_name, progress_callback)


def get_model_path(model_name: str) -> Optional[Path]:
    """Get path to a model file"""
    return get_model_manager().get_model_path(model_name)
