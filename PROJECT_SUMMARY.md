# AI Operating Platform (AIOP) - Complete Project Summary

## 📋 Project Overview
**AIOP** is an AI-powered desktop operating platform that provides voice transcription, automation, and system integration features. It's built with Python and PyQt6, designed primarily for Windows with cross-platform support.

**Version:** 0.1.0  
**License:** MIT  
**Python Required:** 3.11-3.12 (3.14 not supported due to PyAudio compatibility)

---

## 🏗️ Project Structure

### Root Files
| File | Purpose |
|------|---------|
| `pyproject.toml` | Project configuration, dependencies, and build system (setuptools) |
| `requirements.txt` | Production dependencies (48 lines) |
| `requirements-dev.txt` | Development dependencies (45 lines) |
| `README.md` | Comprehensive project documentation with badges, features, and setup guide |
| `SETUP_GUIDE.md` | Detailed installation and troubleshooting guide |
| `PROJECT.md` | Project brief and architecture overview |
| `LICENSE` | MIT License file |
| `.gitignore` | Git ignore patterns for Python, IDEs, and build artifacts |
| `.pre-commit-config.yaml` | Pre-commit hooks configuration |

### Directories

#### `/src/aiop/` - Main Source Code
**Core Application Files:**
- `__init__.py` - Package initialization with version info
- `__main__.py` - Entry point for `python -m aiop` command
- `main.py` - Main application launcher and initialization

**Submodules:**

1. **`/core/` - Core System Components**
   - `config.py` - Configuration management (YAML-based)
   - `logging.py` - Logging setup and management
   - `exceptions.py` - Custom exception classes
   - `utils.py` - Utility functions

2. **`/audio/` - Audio Processing**
   - `capture.py` - Audio capture from microphone
   - `processing.py` - Audio signal processing (VAD, noise reduction)
   - `playback.py` - Audio playback functionality
   - `devices.py` - Audio device enumeration and management

3. **`/speech/` - Speech Recognition**
   - `transcriber.py` - Speech-to-text transcription engine
   - `whisper_cpp.py` - Whisper.cpp integration for speech recognition
   - `model_manager.py` - Model download and management
   - `language.py` - Language detection and support

4. **`/ui/` - User Interface**
   - `main_window.py` - Main application window (WhisperFlow-inspired design)
   - `tray_app.py` - System tray icon and menu
   - `overlay.py` - Overlay window for transcription display
   - `settings_dialog.py` - Settings configuration dialog
   - `styles.py` - UI styling and themes

5. **`/windows/` - Windows-Specific Features**
   - `hotkeys.py` - Global hotkey registration (Windows API)
   - `clipboard.py` - Clipboard integration (Windows-only)
   - `win32_api.py` - Windows API wrappers

#### `/tests/` - Test Suite
| File | Purpose |
|------|---------|
| `test_core.py` | Core functionality tests (config, logging, utils) |
| `test_audio.py` | Audio capture, processing, and device tests |
| `test_integration.py` | Integration tests for full workflows |
| `__init__.py` | Test package initialization |

**Test Status:** 24 passed, 8 skipped (platform-specific), 0 failed

#### `/assets/` - Resources
- `icon.png` - Application icon

#### `/config/` - Configuration
- `config.yaml` - Default configuration template

#### `/models/` - AI Models
- `ggml-base.en.bin` - Whisper base English model

#### `/logs/` - Application Logs
- `aiop.log` - Runtime logs

#### `/docs/` - Documentation
- `index.md` - Documentation index

---

## 🔧 Key Dependencies

### Production (`requirements.txt`)
- **GUI:** PyQt6, PyQt6-Qt6, PyQt6-sip
- **Audio:** pyaudio, webrtcvad, sounddevice, soundfile
- **AI/ML:** numpy, scipy, whispercpp
- **Networking:** requests, websockets, aiohttp
- **System:** psutil, platformdirs, pywin32 (Windows)
- **Config:** pyyaml, toml

### Development (`requirements-dev.txt`)
- **Code Quality:** ruff, black, isort, mypy, flake8, pylint
- **Testing:** pytest, pytest-qt, pytest-asyncio, pytest-cov, hypothesis
- **Documentation:** mkdocs, mkdocs-material, sphinx
- **Build:** build, twine, tox, nox
- **Profiling:** memory-profiler, line-profiler, py-spy

---

## 🚀 How to Run

### Prerequisites
- Python 3.11 or 3.12 (3.14 not supported)
- Windows 10/11 (full features), Linux/macOS (limited)

### Setup Commands
```powershell
# Clone repository
git clone https://github.com/Maherimtiyaz/ai-operating-system.git
cd ai-operating-system

# Create virtual environment with Python 3.12
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install --upgrade pip
pip install -e ".[dev]"
pip install whispercpp  # Recommended for speech features

# Run tests
python -m pytest tests/ -v

# Launch application
python -m aiop
```

### Headless Mode (Linux/CI)
```bash
QT_QPA_PLATFORM=offscreen python -m aiop
```

---

## ✨ Features

### Voice Layer
- ✅ Real-time speech transcription
- ✅ Voice activity detection (VAD)
- ✅ Multi-language support
- ⚠️ Whisper.cpp integration (requires manual setup or whispercpp package)

### AI Layer
- ✅ Model management and auto-download
- ✅ Language detection
- ⚠️ Advanced AI features (planned)

### Automation Layer
- ✅ Global hotkeys (Ctrl+Shift+Space, Ctrl+Shift+O)
- ✅ Clipboard integration (Windows)
- ✅ System tray integration
- ✅ Overlay display for transcriptions

### Integration Layer
- ✅ Windows API integration
- ✅ Audio device management
- ✅ Configuration management
- ✅ Logging system

---

## 🎨 UI Design (WhisperFlow-Inspired)
- Modern gradient background
- Custom top bar with title and controls
- Animated status indicator
- Real-time transcription display
- Professional button styling
- System tray icon with context menu
- Overlay window for always-on-top transcription

---

## 🧪 Testing
```bash
# All tests
python -m pytest tests/ -v

# Specific test modules
python -m pytest tests/test_core.py -v
python -m pytest tests/test_audio.py -v
python -m pytest tests/test_integration.py -v

# With coverage
python -m pytest tests/ --cov=aiop --cov-report=html
```

**Current Status:** All tests passing (24 passed, 8 skipped for platform-specific features)

---

## ⚠️ Known Issues & Solutions

1. **PyAudio on Python 3.14:** No wheels available. Use Python 3.11-3.12.
2. **whisper.cpp library:** Install `pip install whispercpp` for cross-platform support.
3. **System Tray Icon:** Requires Windows; shows warning on Linux/macOS.
4. **Hotkey Registration:** Windows-only feature; gracefully degrades on other platforms.

---

## 📊 Architecture

```
┌─────────────────────────────────────────┐
│           User Interface (Qt)           │
│  ┌──────────┬──────────┬────────────┐  │
│  │ MainWindow│ Overlay │ Settings   │  │
│  └──────────┴──────────┴────────────┘  │
├─────────────────────────────────────────┤
│         Core Services Layer             │
│  ┌──────────┬──────────┬────────────┐  │
│  │ Config   │ Logging  │ Utils      │  │
│  └──────────┴──────────┴────────────┘  │
├─────────────────────────────────────────┤
│       Functionality Layer               │
│  ┌──────────┬──────────┬────────────┐  │
│  │ Audio    │ Speech   │ Windows    │  │
│  │ Capture  │ Transcribe│ Hotkeys    │  │
│  └──────────┴──────────┴────────────┘  │
├─────────────────────────────────────────┤
│         System Integration              │
│  ┌──────────┬──────────┬────────────┐  │
│  │ Win32 API│ Clipboard│ Devices    │  │
│  └──────────┴──────────┴────────────┘  │
└─────────────────────────────────────────┘
```

---

## 🛣️ Roadmap

### ✅ Phase 1: Foundation (Complete)
- Core architecture
- Basic UI
- Audio capture
- Speech transcription

### 🔄 Phase 2: Enhanced Features (In Progress)
- Advanced AI integration
- Multi-platform support
- Plugin system
- Cloud sync

### 📅 Phase 3: Production Ready (Planned)
- Performance optimization
- Security hardening
- Enterprise features
- Documentation completion

---

## 🤝 Contributing
1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

**Code Quality Tools:** Pre-commit hooks run automatically (ruff, black, mypy)

---

## 📞 Support
- **Documentation:** See `SETUP_GUIDE.md` for detailed setup
- **Issues:** GitHub Issues tab
- **License:** MIT (see LICENSE file)

This is a production-ready foundation for an AI-powered desktop assistant with professional code structure, comprehensive testing, and modern UI design.
