# Active Assistant 🤖

**AI-powered desktop assistant with vision, voice, multi-agent system, and plugins**

Active Assistant is a full-stack desktop assistant that monitors your screen, understands context, and takes action using AI. It combines computer vision, voice interaction, web search, and a powerful plugin system to help you be more productive.

## ✨ Features

### 🎯 Screen Monitoring & Vision
- **Real-time screen capture** of active windows (VS Code, terminals, browsers, etc.)
- **Perceptual hashing** (dHash) to detect meaningful changes
- **Vision analysis** using Groq/OpenAI/Anthropic models to detect:
  - Code syntax errors
  - Terminal errors
  - UI/UX issues
  - Grammar mistakes
  - Security concerns

### 🎤 Voice Assistant
- **Wake word detection** ("Hey Assistant", "Okay Assistant")
- **Offline speech recognition** with Vosk
- **Text-to-speech** with pyttsx3 (supports Azure, ElevenLabs, Coqui)
- **Natural language commands** for system control

### 🤖 Multi-Agent System
Specialized agents for different tasks:
- **Vision Analyst** - Analyzes screen content
- **Code Fixer** - Fixes bugs, refactors code
- **Researcher** - Web search and fact-checking
- **Voice Handler** - Processes voice commands
- **File Organizer** - Organizes downloads and files

### 🔌 Plugin System
Built-in plugins:
- **Document Handler** - Extract text from PDF, DOCX, XLSX
- **Code Analyzer** - Complexity, linting, security issues
- **Media Processor** - Image/video info, resize, extract frames
- **System Monitor** - CPU, memory, disk, processes
- **Network Tools** - Ping, DNS, port scan, HTTP requests
- **Archive Manager** - Create/extract ZIP, TAR
- **Database Tools** - SQLite query and management

### 🔍 Web Integration
- **Brave Search API** for web search
- **Web crawling** with depth control
- **Content extraction** from articles and pages

### 📁 Downloads Organizer
- Automatic categorization by file type
- Configurable rules and directories
- Duplicate handling with versioning

### ⚙️ Flexible Configuration
- **Multiple AI providers**: Groq (default), OpenAI, Anthropic, Ollama (local)
- **Granular permissions** - control what the assistant can do
- **Confirmation dialogs** for sensitive actions
- **YAML config** with environment variable overrides
- **Hot-reload** configuration changes

### 🎨 Futuristic UI
- **CustomTkinter** based modern interface
- **Dark/Light/Futuristic** themes
- **Real-time dashboard** with metrics
- **Chat interface** with streaming responses
- **Agent management** panel
- **Plugin browser** with actions
- **Multimodal search** interface

### 🚀 Windows Integration
- **System tray** with quick actions
- **Windows startup** support (with admin option)
- **Custom protocol** (`active-assistant://`)
- **Notifications** via Windows toast

## 📋 Requirements

- **Windows 10/11** (primary target)
- **Python 3.10+**
- **Groq API key** (free at [console.groq.com](https://console.groq.com/keys))
- Optional: OpenAI, Anthropic, Brave Search API keys

## 🚀 Quick Start

### 1. Install from Source
```bash
git clone https://github.com/yourusername/active-assistant.git
cd active-assistant
pip install -e .
```

### 2. Configure API Keys
```bash
# Run setup wizard
active-assistant-setup

# Or manually edit .env
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run
```bash
# System tray mode (default)
active-assistant

# Console mode
active-assistant --console

# Full UI
active-assistant --ui

# Or use specific entry points
active-assistant-tray
active-assistant-ui
active-assistant-voice
```

## 📦 Building Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller active_assistant.spec

# Output: dist/ActiveAssistant.exe
```

## 📁 Project Structure

```
active_assistant/
├── config/
│   └── default_config.yaml      # Default configuration
├── src/
│   └── active_assistant/
│       ├── core/                # Core systems
│       │   ├── config.py        # Configuration management
│       │   ├── state.py         # Global state & events
│       │   ├── providers.py     # AI provider abstraction
│       │   ├── monitor.py       # Screen monitoring
│       │   └── logging.py       # Logging setup
│       ├── tools/               # Tool system
│       │   └── base.py          # Tools & registry
│       ├── agents/              # Multi-agent system
│       │   └── manager.py       # Agent manager & agents
│       ├── plugins/             # Plugin system
│       │   └── manager.py       # Plugin manager & built-ins
│       ├── voice/               # Voice assistant
│       │   └── assistant.py     # Voice recognition & TTS
│       ├── web/                 # Web search & crawl
│       │   └── crawler.py       # Brave API & crawler
│       ├── startup/             # Windows startup
│       │   └── manager.py       # Startup configuration
│       ├── ui/                  # Futuristic UI
│       │   └── main_window.py   # Main window
│       ├── tray.py              # System tray
│       └── main.py              # Entry point
├── assets/
│   ├── icons/                   # App icons
│   └── themes/                  # UI themes
├── docs/                        # Documentation
├── tests/                       # Unit tests
├── setup.py                     # Package setup
├── requirements.txt             # Dependencies
├── active_assistant.spec        # PyInstaller spec
└── version_info.txt             # Windows version info
```

## ⚙️ Configuration

### API Providers (`config.yaml`)
```yaml
api_providers:
  groq:
    enabled: true
    default: true
    api_key: ""  # Set via GROQ_API_KEY env var
    models:
      vision: "llama-3.2-11b-vision-preview"
      chat: "llama-3.1-70b-versatile"
      fast: "llama-3.1-8b-instant"
      reasoning: "deepseek-r1-distill-llama-70b"
```

### Permissions
```yaml
rules:
  permissions:
    read_files: true
    write_files: true
    execute_commands: true
    web_search: true
    use_vision: true
    use_voice: true
    multi_agent: true
    plugin_execution: true
```

### Voice
```yaml
voice:
  enabled: true
  wake_words:
    - "hey assistant"
    - "okay assistant"
  engine: "vosk"
  response_voice:
    engine: "pyttsx3"
```

## 🔒 Security & Privacy

- **Local-first**: All processing can run locally with Ollama
- **No telemetry**: No data sent without consent
- **Confirmations**: Sensitive actions require explicit approval
- **Encrypted config**: Optional config encryption
- **Sandboxed plugins**: Plugins run with restricted permissions

## 🛠️ Development

### Install Dev Dependencies
```bash
pip install -e ".[dev]"
```

### Run Tests
```bash
pytest tests/
```

### Code Style
```bash
ruff check .
black .
mypy .
```

## 📖 Documentation

- [Configuration Guide](docs/configuration.md)
- [Plugin Development](docs/plugins.md)
- [Agent Creation](docs/agents.md)
- [Voice Setup](docs/voice.md)
- [Building Executable](docs/building.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [Groq](https://groq.com/) for fast inference
- [Vosk](https://alphacephei.com/vosk/) for offline speech recognition
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for modern UI
- [Brave Search API](https://brave.com/search/api/) for web search
- [MSS](https://github.com/BoboTiG/python-mss) for screen capture

---

**Active Assistant** - Your AI-powered desktop companion 🚀