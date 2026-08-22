# AI Operating Platform (AIOP) - Setup and Running Guide

## Overview
AIOP is a Next-Generation Windows AI Productivity Suite that combines voice recognition, AI agents, and automation in a seamless platform.

## Prerequisites
- Python 3.11 or 3.12
- pip (Python package manager)
- Git

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/Maherimtiyaz/ai-operating-system.git
cd ai-operating-system
```

### 2. Verify requirements.txt

The project includes a `requirements.txt` file with all necessary dependencies. If it doesn't exist, it will be created automatically during installation.

### 3. Create a Virtual Environment (Recommended)

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

**Option A: Using requirements.txt**
```bash
pip install -r requirements.txt
```

**Option B: Using pip editable install (recommended for development)**
```bash
pip install -e ".[dev]"
```

This installs the package in editable mode along with development dependencies.

**Option C: Using Poetry (if you prefer)**
```bash
pip install poetry
poetry install
```

### 5. Install Optional Speech Recognition (Recommended)

For full speech transcription features, install the whispercpp package:

```bash
pip install whispercpp
```

This provides cross-platform speech recognition without needing to compile whisper.cpp manually.

## Running the Application

### Basic Run

```bash
# From the project directory
python -m aiop

# Or use the installed command
aiop
```

### Running on Different Platforms

**Windows (Full Features):**
```bash
python -m aiop
```

**Linux/macOS (Limited Features):**
```bash
# Use offscreen mode for headless environments
QT_QPA_PLATFORM=offscreen python -m aiop

# Or for desktop environments
python -m aiop
```

**Docker/Container:**
```bash
QT_QPA_PLATFORM=offscreen python -m aiop
```

## Expected Output

When the application starts successfully, you should see:

```
aiop - INFO - AIOP v0.1.0 initializing...
aiop - INFO - AI Operating Platform starting...
aiop - INFO - Config directory: /path/to/config
aiop - INFO - Log directory: /path/to/logs
aiop - INFO - whispercpp Python package is available
```

### Platform-Specific Messages

**Windows:**
- Full clipboard and hotkey functionality
- System tray icon displayed
- All features enabled

**Linux/macOS:**
- Warning messages about clipboard and hotkeys (Windows-only features)
- System tray may not display in headless environments
- Core functionality still works

## Troubleshooting

### Missing Dependencies

If you see "Missing dependencies" error:
```bash
pip install -e ".[dev]"
```

### whisper.cpp Library Not Found

**Solution 1 (Recommended):** Install Python package
```bash
pip install whispercpp
```

**Solution 2:** Download native library
1. Visit https://github.com/ggerganov/whisper.cpp
2. Download and build whisper.cpp
3. Place `whisper.dll` (Windows) or `libwhisper.so` (Linux) in the models directory

### Qt Platform Plugin Issues

**Linux headless environment:**
```bash
QT_QPA_PLATFORM=offscreen python -m aiop
```

**Linux with Wayland:**
```bash
QT_QPA_PLATFORM=wayland python -m aiop
```

### Audio Device Errors

If tests show "No audio devices available":
- This is normal in headless/container environments
- Audio features will work when physical audio hardware is present
- Tests are automatically skipped in these environments

## Testing

Run the test suite:
```bash
python -m pytest tests/ -v
```

Expected results:
- 24+ tests passed
- 8 tests skipped (platform-specific features)
- 0 failures

## Project Structure

```
aiop/
├── src/aiop/              # Main source code
│   ├── main.py           # Entry point
│   ├── audio/            # Audio processing
│   ├── speech/           # Speech recognition
│   ├── ui/               # User interface
│   ├── windows/          # Windows integration
│   ├── ai/               # AI agents
│   ├── core/             # Core utilities
│   └── ...
├── tests/                # Test suite
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project configuration
└── README.md            # Documentation
```

## Configuration

Configuration files are stored in:
- **Windows:** `C:\Users\<User>\.config\aiop\`
- **Linux/macOS:** `~/.config/aiop/`

Logs are stored in:
- **Windows:** `C:\Users\<User>\.config\aiop\logs\`
- **Linux/macOS:** `~/.config/aiop/logs/`

## Features Status

✅ **Working:**
- Speech recognition (with whispercpp)
- Audio capture and processing
- Voice activity detection (VAD)
- Configuration management
- Logging system
- Model management
- UI components (overlay, dialogs)

⚠️ **Platform-Limited:**
- Clipboard operations (Windows only)
- Hotkey registration (Windows only)
- System tray icon (requires desktop environment)
- Win32 API integration (Windows only)

## Next Steps

1. Configure your settings via the system tray menu
2. Press `Ctrl+Shift+Space` to start voice dictation (Windows)
3. Explore AI agents and automation features
4. Check the docs/ directory for detailed documentation

## Support

- Documentation: See `docs/` directory
- Issues: GitHub Issues
- License: Apache 2.0
