# OpenSS - AI-Powered Screenshot Analysis

OpenSS is a premium CLI tool that captures your screen (optimized for Chrome on macOS), extracts text via OCR, and analyzes it using GPT-4-class AI models. Perfect for coding challenges, document analysis, and quick technical queries.

> [!IMPORTANT]
> **Compatibility**: This tool is strictly for **macOS** and is optimized for the **Google Chrome** browser.

## Features

- 📸 **Smart Capture**: Automatically detects active Chrome windows or masks terminal windows to keep your private logs out of the AI.
- 🔍 **Native OCR**: Uses macOS Vision Framework for lightning-fast, high-accuracy text recognition.
- 💬 **Interactive Chat**: Follow up on analyses with a conversational AI interface.
- 🎙️ **Native Voice-to-Text**: Ask questions with your voice using macOS native speech recognition (type `/v` in chat or use `--voice` flag).
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
git clone https://github.com/Mide6x/OpenSS.git
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

### 4. Global Command (Required for Voice & Portability)
To run `openssmide` from anywhere, you **must** use a symlink (do not just copy the file, or it won't find the virtual environment):
```bash
mkdir -p ~/bin
ln -sf "$(pwd)/openssmide" ~/bin/openssmide
```
Ensure `~/bin` is in your `$PATH`. If you use Zsh, add this to `~/.zshrc`:
```bash
export PATH="$HOME/bin:$PATH"
```

## Detailed Usage

### Capture and Analyze
Capture the active Chrome window and get an AI response.
```bash
openssmide capture
```
*Options:*
- `-t, --title TEXT`: Set a custom session title.
- `--chat / --no-chat`: Enter or skip interactive follow-up mode (Default: chat).
- `-v, --voice`: Use voice input to ask a question about the screenshot immediately.

### Voice Question
Ask the AI a question verbally and get an instant response.
```bash
openssmide voice
```
*Options:*
- `-d, --duration INTEGER`: Seconds to record (Default: 5).
- `--chat / --no-chat`: Enter or skip interactive follow-up mode (Default: chat).
*Note: Uses native AVFoundation for recording and a stable transcription engine to avoid macOS Speech framework crashes.*

### Ask AI
Directly ask the AI a question from the terminal.
```bash
openssmide ask "What is the capital of France?"
```
*Options:*
- `--chat / --no-chat`: Enter or skip interactive follow-up mode (Default: chat).

### Resume Chat
Continue a conversation from a previous session.
```bash
openssmide chat          # Resumes the latest session
openssmide chat --id ID  # Resumes a specific session
```
*Inside Chat:*
- Type `/v` or `/voice` to trigger a 5-second voice recording for your next question.

### View History
See a list of recent analysis sessions in a beautiful table.
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
- `model`: Change the AI model (e.g., `gpt-4o`).

## Security & Privacy
- **.gitignore**: The `.env` file and `config.json` are ignored by git to protect your API keys and local settings.
- **Terminal Masking**: When not using Chrome, the tool automatically masks the terminal window in the screenshot to prevent sensitive command history from being sent to the AI.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
