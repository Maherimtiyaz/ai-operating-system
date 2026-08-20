# AI Operating Platform (AIOP)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-24%20passed-green.svg)]()
[![Status](https://img.shields.io/badge/status-building-orange.svg)]()

> **Next-Generation Cross-Platform AI Productivity Suite**

The world's first AI Operating Platform that combines voice recognition, AI agents, and automation in a seamless interface. Built with PyQt6, Whisper speech recognition, and extensible plugin architecture.

🚀 **Current Status**: Phase 1 Foundation Complete - MVP Ready  
📦 **Latest Version**: v0.1.0

---

## 🌟 Key Features

### 🎤 Voice Layer
- ✅ Real-time speech recognition with local Whisper models
- ✅ Voice dictation with inline editing overlay
- ✅ Voice commands for system and app control
- ✅ Wake word detection
- ✅ Noise removal and echo cancellation with WebRTC VAD
- ✅ Cross-platform audio capture (PyAudio)

### 🤖 AI Layer
- 🔄 Multi-model router supporting 20+ local and cloud models
- 🎯 Specialized AI agents (Coding, Research, Writing, etc.)
- 🧠 Agent orchestration and memory system
- 💬 Context-aware conversations
- 🔌 MCP (Model Context Protocol) integration ready

### ⚙️ Automation Layer
- 🛠️ Visual workflow builder
- 📋 100+ action types and 20+ trigger types
- 📦 Workflow templates and marketplace (coming soon)
- 🎙️ Voice-triggered automation

### 🔗 Integration Layer
- 🔌 Plugin system with Python, TypeScript, and Rust SDKs
- 🪟 Deep Windows integration (Win32, COM, .NET)
- 🌐 Cross-platform support (Windows, Linux, macOS)
- 📱 App integrations (Office, VS Code, browsers, etc.)

---

## 🚀 Quick Start

### Prerequisites

- **Python**: 3.11 or 3.12
- **OS**: Windows 10/11 (full features), Linux/macOS (core features)
- **Git**: For cloning the repository

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/Maherimtiyaz/ai-operating-system.git
cd ai-operating-system
```

#### 2. Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies

```bash
# Install all dependencies including dev tools
pip install -e ".[dev]"

# OR using requirements.txt
pip install -r requirements.txt
```

#### 4. Install Optional Speech Recognition (Recommended)

For full cross-platform speech transcription:

```bash
pip install whispercpp
```

This enables Whisper speech recognition without manual compilation.

### Running the Application

```bash
# Standard run
python -m aiop

# Or use the installed command
aiop

# Linux headless/server environment
QT_QPA_PLATFORM=offscreen python -m aiop

# Linux with Wayland
QT_QPA_PLATFORM=wayland python -m aiop
```

### First Use

1. **Launch** the application
2. **Configure** settings via system tray icon (Windows) or menu
3. **Start dictation** with `Ctrl+Shift+Space` (Windows)
4. **Speak naturally** - text appears in the overlay
5. **Use voice commands** like "Open Notepad" or "Search for AI news"

---

## 📦 Project Structure

```
ai-operating-system/
├── src/aiop/                 # Main source code
│   ├── __init__.py          # Package initialization
│   ├── __main__.py          # Entry point module
│   ├── main.py              # Application entry
│   ├── audio/               # Audio engine & processing
│   │   ├── audio_engine.py
│   │   └── webrtc_vad.py
│   ├── speech/              # Speech recognition
│   │   ├── transcriber.py
│   │   └── whisper_cpp.py
│   ├── ui/                  # User interface components
│   │   ├── main_window.py
│   │   ├── overlay.py
│   │   └── dialogs/
│   ├── windows/             # Windows integration
│   │   ├── win32_api.py
│   │   ├── clipboard.py
│   │   └── hotkeys.py
│   ├── ai/                  # AI agents & models
│   ├── automation/          # Workflow automation
│   ├── plugins/             # Plugin system
│   ├── mcp/                 # MCP integration
│   ├── core/                # Core utilities
│   └── config/              # Configuration management
├── tests/                   # Test suite
│   ├── test_audio.py
│   ├── test_core.py
│   └── test_integration.py
├── docs/                    # Documentation
├── assets/                  # Icons and resources
├── models/                  # AI models (downloaded)
├── config/                  # Default configuration
├── logs/                    # Application logs
├── requirements.txt         # Python dependencies
├── pyproject.toml          # Project configuration
├── README.md               # This file
└── SETUP_GUIDE.md          # Detailed setup instructions
```

---

## 🧪 Testing

Run the complete test suite:

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=aiop

# Run specific test file
python -m pytest tests/test_audio.py -v
```

**Expected Results:**
- ✅ 24+ tests passed
- ⏭️ 8 tests skipped (platform-specific features in headless environments)
- ❌ 0 failures

---

## 🛠️ Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/Maherimtiyaz/ai-operating-system.git
cd ai-operating-system
python -m venv .venv

# Activate virtual environment
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Code Quality Tools

```bash
# Linting
ruff check .

# Formatting
black .

# Type checking
mypy src/aiop

# Run all checks
pre-commit run --all-files
```

### Building from Source

```bash
# Build distribution packages
pip install build
python -m build

# Install locally
pip install -e .
```

---

## 🏗️ Architecture

### Core Components

| Component | Description | Status |
|-----------|-------------|--------|
| **Audio Engine** | PyAudio-based capture, WebRTC VAD | ✅ Complete |
| **Speech Engine** | Whisper.cpp / whispercpp integration | ✅ Complete |
| **UI Layer** | PyQt6 overlays, dialogs, system tray | ✅ Complete |
| **Windows Integration** | Win32 API, clipboard, hotkeys | ✅ Complete (Windows) |
| **Config System** | YAML-based configuration | ✅ Complete |
| **Logging** | Structured logging system | ✅ Complete |
| **Model Manager** | Automatic model download & verification | ✅ Complete |
| **AI Router** | Multi-model support | 🔄 In Progress |
| **Automation** | Workflow engine | 🔄 In Progress |
| **Plugin System** | Extensible architecture | 🔄 In Progress |

### Technology Stack

- **Language**: Python 3.11/3.12
- **UI Framework**: PyQt6
- **Audio**: PyAudio, WebRTC VAD
- **Speech**: Whisper.cpp, whispercpp (Python package)
- **AI Models**: Ollama, vLLM, Transformers (planned)
- **Windows API**: pywin32, ctypes
- **Protocol**: MCP (Model Context Protocol)
- **Testing**: pytest, pytest-cov
- **Code Quality**: ruff, black, mypy

---

## 📋 Roadmap

### Phase 1: Foundation (Weeks 1-12) - ✅ MVP Complete

- [x] Project setup and structure
- [x] Audio engine with PyAudio
- [x] Speech engine with Whisper integration
- [x] Voice activity detection (WebRTC VAD)
- [x] Windows integration layer
- [x] Basic UI with PyQt6 overlays
- [x] Configuration and logging systems
- [x] Model management and auto-download
- [x] Comprehensive test suite
- [x] Documentation and setup guides

### Phase 2: Core Features (Weeks 13-24)

- [ ] Multi-model router (20+ models)
- [ ] AI agents framework
- [ ] Automation engine
- [ ] Plugin system (Python/TS/Rust SDKs)
- [ ] MCP client implementation
- [ ] Advanced UI with workflow builder
- [ ] Voice command parsing
- [ ] Wake word detection

### Phase 3: Advanced Features (Weeks 25-36)

- [ ] Advanced AI agents with memory
- [ ] Complex workflow automation
- [ ] Advanced Windows automation
- [ ] Full MCP server implementation
- [ ] Plugin marketplace
- [ ] Cloud sync and backup

### Phase 4: Polish & Launch (Weeks 37-48)

- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] User documentation
- [ ] Packaging (installer, portable)
- [ ] Beta testing program
- [ ] Public launch

---

## 🔧 Configuration

Configuration files are stored automatically:

- **Windows**: `C:\Users\<User>\.config\aiop\`
- **Linux/macOS**: `~/.config/aiop/`

Logs location:
- **Windows**: `C:\Users\<User>\.config\aiop\logs\`
- **Linux/macOS**: `~/.config/aiop/logs/`

Edit `config/config.yaml` to customize:
- Audio devices and settings
- Speech recognition models
- Hotkey bindings
- UI preferences
- API keys for cloud services

---

## ⚠️ Platform Compatibility

### Windows 10/11 (Full Support)
✅ All features enabled  
✅ System tray integration  
✅ Clipboard operations  
✅ Global hotkeys  
✅ Win32 API integration  

### Linux (Core Support)
✅ Speech recognition  
✅ Audio processing  
✅ UI overlays  
⚠️ Clipboard (limited)  
⚠️ Hotkeys (limited)  
⚠️ No system tray in headless mode  

### macOS (Core Support)
✅ Speech recognition  
✅ Audio processing  
✅ UI overlays  
⚠️ Some Windows-specific features unavailable  

---

## 🐛 Troubleshooting

### Common Issues

#### "whisper.cpp library not found"
**Solution**: Install the Python whispercpp package:
```bash
pip install whispercpp
```

#### "Qt platform plugin error"
**Linux solution**:
```bash
QT_QPA_PLATFORM=offscreen python -m aiop
```

#### "No audio devices available"
- Normal in headless/container environments
- Audio features work when physical hardware is present
- Tests automatically skip in these environments

#### "Missing dependencies"
```bash
pip install -e ".[dev]"
```

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed troubleshooting.

---

## 📚 Documentation

- **[Setup Guide](SETUP_GUIDE.md)**: Detailed installation and running instructions
- **[Project Documentation](docs/)**: Technical documentation
- **[Configuration](config/config.yaml)**: Default configuration examples

---

## 🤝 Contributing

We welcome contributions! Here's how to help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** your changes
4. **Run** tests and linting (`pytest`, `ruff check`, `black .`)
5. **Commit** your changes (`git commit -m 'Add amazing feature'`)
6. **Push** to your fork (`git push origin feature/amazing-feature`)
7. **Open** a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write tests for new features
- Update documentation as needed
- Use type hints for function signatures
- Keep commits atomic and well-described

---

## 📄 License

Distributed under the **Apache License 2.0**. See [LICENSE](LICENSE) for details.

---

## 🌐 Community & Support

- **GitHub**: [Issues](https://github.com/Maherimtiyaz/ai-operating-system/issues)
- **Documentation**: [docs/](docs/) directory
- **Twitter**: [@AIOP_Platform](https://twitter.com/AIOP_Platform)
- **Discord**: Coming soon

---

## 📬 Stay Updated

Star this repository to get notifications about updates and new releases!

---

**Built with ❤️ by Maherimtiyaz**  
**Version**: 0.1.0 | **Status**: 🚀 Building Phase
