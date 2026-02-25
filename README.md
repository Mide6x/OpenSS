# OpenSS – AI-Powered Screenshot Analysis

OpenSS is a CLI tool that captures your screen (Chrome or PowerPoint on macOS), extracts text via OCR, and analyzes it using GPT-4-class AI models. Built for coding challenges, document analysis, and quick technical queries.

> [!IMPORTANT]
> **Compatibility**: This tool is strictly for **macOS**.
> **Capture targets**: `chrome`, `powerpoint`, and `word`.
> **Target app + Terminal must be on the same display** for capture to work.

## Features

- **Smart Capture (Auto-Detect)** – Automatically detects and captures your active Chrome, PowerPoint, or Word window without needing explicit flags.
- **Multimodal AI Vision & Native OCR** – Passes the actual screenshot directly to GPT-4o or Claude 3.5 Sonnet to perfectly read complex layouts, images, and diagrams, while using macOS OCR as a fallback.
- **Interactive Chat** – Follow up on analyses contextually. Now supports continuous editing of Word documents!
- **Native Voice-to-Text** – Ask questions with your voice using macOS native speech recognition (type `/v` in chat or use `--voice` flag).
- **Autocopy** – Automatically copies clean AI responses or extracted code blocks to your clipboard.
- **Rich UI** – Beautiful terminal interface with markdown rendering and progress spinners.
- **Model Switcher** – Swap between OpenAI and Claude models on the fly.

## Installation

### 1. Prerequisites

- **macOS** (Required for OCR and Capture rules)
- **Python 3.10+**
- **MongoDB** (Running locally or via URI)
- **OpenAI API Key**
- **Anthropic API Key** (optional, for Claude models)

### 2. Quick Setup

Run this single command to clone, set up, and link OpenSS:

```bash
git clone https://github.com/Mide6x/OpenSS.git && cd OpenSS && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && mkdir -p ~/bin && ln -sf "$(pwd)/openssmide" ~/bin/openssmide
```

### 3. Environment Variables

Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
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

Capture the active app window and get an AI response.

```bash
openssmide capture
```

**Options:**
- `-t, --title TEXT` – Set a custom session title.
- `--chat / --no-chat` – Enter or skip interactive follow-up mode (Default: chat).
- `-v, --voice` – Use voice input to ask a question about the screenshot immediately.
- `-a, --target TEXT` – Capture target: `chrome`, `powerpoint`, or `word`.
- `--full-slide / --window` – With `--target powerpoint`, require Slide Show mode for full-slide capture.

### Microsoft Word Automation

Read, question, write, or AI-edit the currently open Word document.

```bash
openssmide word --action read
openssmide word --action ask --instruction "Summarize this contract in 5 bullet points"
openssmide word --action edit --instruction "Rewrite this into a professional project proposal"
openssmide word --action write --text "New full document text"
```

Optional:
- `-f, --file PATH` – Open a specific Word file before running the action.

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

### Write to Word (Interactive)

Interactively ask the AI to generate content and write it directly into your active Microsoft Word document.

```bash
openssmide write
```
*The command will prompt you with "What do you want to write?" before generating and pasting the response. It then leaves a chat session open so you can interactively tell the AI to re-write, summarize, or edit your content continuously!*

### Summarize Word Document

Read the currently active Microsoft Word document and generate a comprehensive AI summary in the terminal.

```bash
openssmide summarize
```

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

Switch between OpenAI and Claude models interactively.

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

Run initial setup or redo it anytime. Prompts for OpenAI/Anthropic API keys and optional MongoDB URI. Credentials are stored locally in your install directory.

```bash
openssmide setup
```

### Change API Key

Update your OpenAI API key without re-running full setup.

```bash
openssmide apikey
```

### Change Anthropic Key

Update your Anthropic API key without re-running full setup.

```bash
openssmide anthropic
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
- Only the selected target window is captured. Terminal must be on the same display as the target app.

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.
