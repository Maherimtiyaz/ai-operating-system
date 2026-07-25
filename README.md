# AI Operating Platform (AIOP)

> **Next-Generation Windows AI Productivity Suite**

The world's first AI Operating Platform for Windows, where voice, AI agents, and automation work together seamlessly to make computers more human, more powerful, and more accessible to everyone.

## Features

### Voice Layer
- Real-time speech recognition with local Whisper models
- Voice dictation with inline editing
- Voice commands for system and app control
- Wake word detection
- Noise removal and echo cancellation

### AI Layer
- Multi-model router (20+ local and cloud models)
- 11 specialized AI agents (Coding, Research, Writing, etc.)
- Agent orchestration and memory system
- Context-aware conversations

### Automation Layer
- Visual workflow builder
- 100+ action types and 20+ trigger types
- Workflow templates and marketplace
- Voice-triggered automation

### Integration Layer
- MCP (Model Context Protocol) client and server
- Plugin system with Python, TypeScript, and Rust SDKs
- Deep Windows integration (Win32, COM, .NET)
- App integrations (Office, VS Code, browsers, etc.)

## Quick Start

### Installation

```bash
git clone https://github.com/Maherimtiyaz/ai-operating-system.git
cd ai-operating-system
pip install -e ".[dev]"
```

### Running

```bash
# Start the application
python -m aiop

# Or use the installed command
aiop
```

### Usage

1. Press `Ctrl+Shift+Space` to start voice dictation
2. Speak naturally - your words appear in the overlay
3. Use voice commands like "Open Notepad" or "Search for AI news"
4. Access settings from the system tray icon

## Project Structure

```
aiop/
├── src/
│   └── aiop/
│       ├── __init__.py
│       ├── main.py          # Entry point
│       ├── audio/           # Audio engine
│       ├── speech/          # Speech recognition
│       ├── windows/         # Windows integration
│       ├── ui/              # User interface
│       ├── ai/              # AI agents and models
│       ├── automation/      # Workflow automation
│       ├── plugins/         # Plugin system
│       ├── mcp/             # MCP integration
│       ├── core/            # Core utilities
│       └── config/          # Configuration
├── tests/
├── docs/
└── assets/
```

## Development

### Prerequisites

- Python 3.11 or 3.12
- Windows 10 or 11
- Git

### Setup

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Linting
ruff check .

# Formatting
black .

# Type checking
mypy aiop
```

## Architecture

### Core Components

1. **Audio Engine**: Handles audio capture, processing, and playback
2. **Speech Engine**: Manages speech recognition using Whisper.cpp
3. **Windows Integration**: Provides Win32 API access, clipboard, and hotkeys
4. **UI Layer**: PyQt6-based interface with system tray
5. **AI Layer**: Multi-model router and AI agents
6. **Automation Engine**: Workflow execution and triggers
7. **Plugin System**: Extensible architecture for third-party integrations
8. **MCP Client**: Model Context Protocol integration

### Technology Stack

- **Language**: Python 3.11/3.12
- **UI Framework**: PyQt6
- **Audio**: PortAudio, WASAPI
- **Speech**: Whisper.cpp with GGUF models
- **AI**: Ollama, vLLM, Transformers
- **Windows**: PyWin32, ctypes
- **MCP**: Official MCP SDK

## Roadmap

### Phase 1: Foundation (Weeks 1-12) - MVP
- [x] Project setup
- [ ] Audio engine
- [ ] Speech engine
- [ ] Windows integration
- [ ] Basic UI
- [ ] Integration & testing

### Phase 2: Core Features (Weeks 13-24)
- [ ] Multi-model router
- [ ] AI agents framework
- [ ] Automation engine
- [ ] Plugin system
- [ ] MCP client
- [ ] Advanced UI

### Phase 3: Advanced Features (Weeks 25-36)
- [ ] Advanced AI agents
- [ ] Advanced automation
- [ ] Advanced Windows automation
- [ ] Advanced MCP
- [ ] Advanced plugin system

### Phase 4: Polish & Launch (Weeks 37-48)
- [ ] Testing
- [ ] Documentation
- [ ] Packaging
- [ ] Marketing
- [ ] Launch

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Commit your changes
6. Push to your fork
7. Open a Pull Request

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

## Community

- GitHub Discussions
- Discord (coming soon)
- Twitter: [@AIOP_Platform](https://twitter.com/AIOP_Platform)

---

**Documentation**: [https://aiop.dev](https://aiop.dev) (coming soon)

**Status**: 🚀 Building Phase (Research Complete)
