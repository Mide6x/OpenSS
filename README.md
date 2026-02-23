# SS-AI Terminal Assistant

Local screenshot → OCR → GPT answers with persistent sessions.

# OpenSS - AI-Powered Screenshot Analysis

OpenSS is a premium CLI tool that captures your screen (optimized for Chrome on macOS), extracts text via OCR, and analyzes it using GPT-4-class AI models. Perfect for coding challenges, document analysis, and quick technical queries.

> [!IMPORTANT]
> **Compatibility**: This tool is strictly for **macOS** and is optimized for the **Google Chrome** browser.

## Features

- 📸 **Smart Capture**: Automatically detects active Chrome windows or masks terminal windows to keep your private logs out of the AI.
- 🔍 **Native OCR**: Uses macOS Vision Framework for lightning-fast, high-accuracy text recognition.
- 💬 **Interactive Chat**: Follow up on analyses with a conversational AI interface.
- 📋 **Autocopy**: Automatically copies clean AI responses or extracted code blocks to your clipboard.
- 🎨 **Rich UI**: Beautiful terminal interface with markdown rendering and progress spinners.

## Installation

### 1. Prerequisites
- **macOS** (Required for OCR and Capture rules)
- **Python 3.10+**
- **MongoDB** (Running locally or via URI)
- **OpenAI API Key**

### 2. Setup
Clone the repository and run the setup:

```bash
# Clone the repo
git clone https://github.com/Veritas-Social/OpenSS.git
cd OpenSS

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=your_key_here
MONGO_URI=mongodb://localhost:27017/  # Optional
```

### 4. Global Command (Recommended)
To run `openssmide` from anywhere:
```bash
cp openssmide ~/bin/openssmide
chmod +x ~/bin/openssmide
```
*Ensure `~/bin` is in your `$PATH`.*

## Detailed Usage

### Capture and Analyze
Capture the active Chrome window and get an AI response.
```bash
openssmide capture
```
*Options:*
- `-t, --title TEXT`: Set a custom session title.
- `--no-chat`: Skip the interactive follow-up mode.

### Resume Chat
Continue a conversation from a previous session.
```bash
openssmide chat          # Resumes the latest session
openssmide chat --id ID  # Resumes a specific session
```

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
*Useful Keys:*
- `autocopy_mode`: Set to `code` to only copy the code block, or `answer` for the whole response.
- `model`: Change the AI model used.

## Under the Hood
- **TUI**: Built with `typer` and `rich`.
- **OCR**: Powered by `pyobjc` (macOS Vision).
- **Storage**: Sessions and messages are stored in MongoDB.

**Setup**
```bash
pip install openai watchdog pymongo python-dotenv pyobjc-framework-Vision pyobjc-framework-Quartz pillow
```

Create `.env`:
```
OPENAI_API_KEY=your_key
MONGO_URI=mongodb://localhost:27017/
```

Optional config:
```
cp config.json.example config.json
```
If OCR returns no text, set `debug_ocr` to `true` and try a larger, clearer selection.

**Manual Screenshot Mode**
```bash
python3 ss_ai.py
```
This now auto-captures the full display that contains the active Terminal window.
After the answer prints, you can type follow-up questions in the same session.
If Chrome is active, it captures the Chrome window only. Otherwise it captures the Terminal display and masks the Terminal region.

**CLI Command**
```bash
mkdir -p ~/bin
cp /Users/nolimitmide/Desktop/OpenSS/openssmide ~/bin/openssmide
chmod +x ~/bin/openssmide
```
Ensure `~/bin` is in your PATH:
```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```
Run from anywhere:
```bash
openssmide
```

Optional alias:
```bash
alias ss="python3 /Users/nolimitmide/Desktop/OpenSS/ss_ai.py"
```

**Auto Screenshot Watch Mode**
```bash
python3 watch_ss_ai.py
```

**Interactive Session Shell**
```bash
python3 ss_shell.py
```

Commands:
```
/sessions        list sessions
/latest          open latest session
/open <id>       open session
/ask <text>      continue conversation
/follow          follow-up on latest session
/help
/exit
```

**Storage**
MongoDB:
```
mongodb://localhost:27017/
db: ss_ai
collections:
  sessions
  messages
```

Each screenshot interaction stores:
- OCR text
- AI answers
- Screenshot path
- Session title includes local date + time

**Screenshot Retention**
Screenshots under `~/.ss_ai/` are deleted automatically after 3 days.
Cleanup runs at program start.

**Notes**
- OCR uses macOS Vision.
- Model default is `gpt-4.1-nano`.
- If `config.json` exists, it overrides prompts and model.
