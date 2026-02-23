# OpenSS – AI-Powered Screenshot Analysis

OpenSS is a CLI tool that captures your screen (optimized for Chrome on macOS), extracts text via OCR, and analyzes it using GPT-4-class AI models. Built for coding challenges, document analysis, and quick technical queries.

> [!IMPORTANT]
> **Compatibility**: This tool is strictly for **macOS** and is optimized for the **Google Chrome** browser.
> **Chrome + Terminal must be on the same display** for capture to work.

## Features

- **Smart Capture** – Captures your active Chrome window.
- **Native OCR** – Uses macOS Vision Framework for lightning-fast, high-accuracy text recognition.
- **Interactive Chat** – Follow up on analyses with a conversational AI interface.
- **Native Voice-to-Text** – Ask questions with your voice using macOS native speech recognition (type `/v` in chat or use `--voice` flag).
- **Autocopy** – Automatically copies clean AI responses or extracted code blocks to your clipboard.
- **Rich UI** – Beautiful terminal interface with markdown rendering and progress spinners.
- **Model Switcher** – Swap between GPT-4o, GPT-4o mini, o3-mini on the fly.

## Installation

### 1. Prerequisites

- **macOS** (Required for OCR and Capture rules)
- **Python 3.10+**
- **MongoDB** (Running locally or via URI)
- **OpenAI API Key**

### 2. Quick Setup

Run this single command to clone, set up, and link OpenSS:

```bash
git clone https://github.com/Mide6x/OpenSS.git && cd OpenSS && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && mkdir -p ~/bin && ln -sf "$(pwd)/openssmide" ~/bin/openssmide
```

### 3. Environment Variables

Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=your_key_here
MONGO_URI=mongodb://localhost:27017/  # Optional
```

### 4. Global Command

To run `openssmide` from anywhere, you **must** use a symlink (do not just copy the file, or it won't find the virtual environment):

```bash
mkdir -p ~/bin
ln -sf "$(pwd)/openssmide" ~/bin/openssmide
```

Ensure `~/bin` is in your `$PATH`. If you use Zsh, add this to `~/.zshrc`:

```bash
export PATH="$HOME/bin:$PATH"
```

## Usage

### Capture and Analyze

Capture the active Chrome window and get an AI response.

```bash
openssmide capture
```

**Options:**
- `-t, --title TEXT` – Set a custom session title.
- `--chat / --no-chat` – Enter or skip interactive follow-up mode (Default: chat).
- `-v, --voice` – Use voice input to ask a question about the screenshot immediately.

### Voice Question

Ask the AI a question verbally and get an instant response.

```bash
openssmide voice
```

**Options:**
- `-d, --duration INTEGER` – Seconds to record (Default: 5).
- `--chat / --no-chat` – Enter or skip interactive follow-up mode (Default: chat).

> Uses native AVFoundation for recording and a stable transcription engine to avoid macOS Speech framework crashes.

### Ask AI

Directly ask the AI a question from the terminal.

```bash
openssmide ask "What is the capital of France?"
```

**Options:**
- `--chat / --no-chat` – Enter or skip interactive follow-up mode (Default: chat).

### Resume Chat

Continue a conversation from a previous session.

```bash
openssmide chat          # Resumes the latest session
openssmide chat --id ID  # Resumes a specific session
```

Inside Chat:
- Type `/v` or `/voice` for voice input.
- Type `/model` to switch AI models.
- Type `/m` for multiline paste mode.

### Model Switcher

Switch between OpenAI models interactively.

```bash
openssmide model
```

Or type `/model` inside any chat session.

### View History

See a list of recent analysis sessions.

```bash
openssmide history
```

### Configuration

View or update your settings.

```bash
openssmide config                  # View all config
openssmide config <key> <value>    # Update a key
```

**Useful Keys:**
- `autocopy_mode` – Set to `code` to only copy the code block, or `answer` for the whole response.
- `model` – Change the AI model (e.g., `gpt-4o`).

### Update

Pull latest code and update dependencies.

```bash
openssmide update
```

### Setup

Run initial setup or redo it anytime. Prompts for your OpenAI API key and optional MongoDB URI. Credentials are stored locally in your install directory.

```bash
openssmide setup
```

### Change API Key

Update your OpenAI API key without re-running full setup.

```bash
openssmide apikey
```

### MongoDB

Set, change, or clear your MongoDB URI anytime.

```bash
openssmide mongo
```

### Uninstall

Completely remove OpenSS from your system (deletes `~/.openss` and the `~/bin/openssmide` symlink).

```bash
openssmide uninstall
```

### Interfaces

See `INTERFACES.md` for available interfaces and entry points.

## Security and Privacy

- The `.env` file and `config.json` are ignored by git to protect your API keys and local settings.
- Only the Chrome window is captured. Terminal must be on the same display as Chrome.

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.
