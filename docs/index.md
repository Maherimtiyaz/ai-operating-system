# AI Operating Platform Documentation

Welcome to the AI Operating Platform (AIOP) documentation!

## Overview

AIOP is a next-generation Windows AI productivity suite that combines voice recognition, AI agents, and workflow automation into a single, cohesive platform.

## Features

### Voice Layer
- Real-time speech recognition with local Whisper models
- Voice dictation with inline editing
- Voice commands for system and app control
- Wake word detection
- Noise removal and echo cancellation

### AI Layer
- Multi-model router (20+ local and cloud models)
- 11 specialized AI agents
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
- Deep Windows integration
- App integrations

## Getting Started

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Maherimtiyaz/ai-operating-system.git
   cd ai-operating-system
   ```

2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Run the application:
   ```bash
   python -m aiop
   ```

### First Run

On first run, AIOP will:
1. Create necessary directories in your AppData folder
2. Download the default speech recognition model (base.en)
3. Set up the system tray icon
4. Register global hotkeys

### Basic Usage

- **Start Dictation**: Press `Ctrl+Shift+Space` or click "Start Dictation" in the main window
- **Stop Dictation**: Press `Ctrl+Shift+Space` again or click "Stop Dictation"
- **View Transcription**: Text appears in the overlay and main window
- **Copy to Clipboard**: Click "Copy to Clipboard" to copy transcription

## Configuration

AIOP uses a YAML configuration file located in `%APPDATA%\aiop\config\config.yaml`.

### Main Configuration Options

```yaml
audio:
  sample_rate: 16000
  channels: 1
  chunk_size: 1024

speech:
  model_path: models/ggml-base.en.bin
  model_type: whisper-1
  language: en
  use_vad: true
  vad_aggressiveness: 3

windows:
  hotkey_dictation: Ctrl+Shift+Space
  hotkey_ai_assistant: Ctrl+Shift+A
  start_on_boot: true
  run_in_tray: true
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

### Directory Structure

```
%APPDATA%\aiop\
├── config\
│   └── config.yaml
├── models\
│   └── ggml-base.en.bin
├── plugins\
├── workflows\
├── logs\
│   └── aiop.log
└── cache\
```

## Development

### Setting Up Development Environment

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
4. Install pre-commit hooks:
   ```bash
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

## Troubleshooting

### Common Issues

#### whisper.cpp library not found

Download the whisper.cpp library from [https://github.com/ggerganov/whisper.cpp](https://github.com/ggerganov/whisper.cpp) and place `whisper.dll` in the models directory.

#### No audio input device found

Check that your microphone is properly connected and configured in Windows sound settings.

#### Model download failed

Check your internet connection and ensure you have write permissions to the models directory.

## API Reference

### Python API

```python
from aiop import get_transcriber, get_clipboard

# Start transcription
transcriber = get_transcriber()
transcriber.start()

# Get clipboard text
clipboard = get_clipboard()
text = clipboard.get_text()
```

### Command Line

```bash
# Start the application
aiop

# Start with tray only
aiop --tray-only
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Commit your changes
6. Push to your fork
7. Open a Pull Request

## License

Apache License 2.0

## Support

- GitHub Issues: [https://github.com/Maherimtiyaz/ai-operating-system/issues](https://github.com/Maherimtiyaz/ai-operating-system/issues)
- Documentation: [https://aiop.dev](https://aiop.dev) (coming soon)
