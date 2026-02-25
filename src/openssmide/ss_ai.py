import os
import re
import subprocess
import time
from pathlib import Path

from anthropic import Anthropic
from openai import OpenAI
from dotenv import load_dotenv

import base64
import mimetypes

from .config import load_config
from .cleanup import cleanup_old_screens
from .capture_rules import capture_active_window
from .db import add_message, create_session, get_session_messages

# --- CONFIG ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_config()
MODEL = CONFIG["model"]
WORK_DIR = Path.home() / ".ss_ai"
WORK_DIR.mkdir(parents=True, exist_ok=True)

_openai_client = None
_anthropic_client = None


def _provider_from_model(model_id: str) -> str:
    m = (model_id or "").lower()
    return "anthropic" if m.startswith("claude") else "openai"


def _active_provider(cfg=None) -> str:
    cfg = cfg or load_config()
    return _provider_from_model(cfg.get("model", ""))


def require_api_key(provider=None):
    provider = provider or _active_provider()
    load_dotenv(PROJECT_ROOT / ".env")
    if provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "\n  ✗ ANTHROPIC_API_KEY not set.\n"
                "  Run: openssmide setup\n"
            )
    else:
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit(
                "\n  ✗ OPENAI_API_KEY not set.\n"
                "  Run: openssmide setup\n"
            )


def get_client(provider=None):
    """Lazy-init the selected provider client. Only called when needed."""
    provider = provider or _active_provider()
    global _openai_client, _anthropic_client
    load_dotenv(PROJECT_ROOT / ".env")

    if provider == "anthropic":
        if _anthropic_client is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise SystemExit(
                    "\n  ✗ ANTHROPIC_API_KEY not set.\n"
                    "  Run: openssmide setup\n"
                )
            _anthropic_client = Anthropic(api_key=api_key)
        return _anthropic_client

    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit(
                "\n  ✗ OPENAI_API_KEY not set.\n"
                "  Run: openssmide setup\n"
            )
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def _ask_model(prompt: str, model_id: str, image_path: Path = None) -> str:
    provider = _provider_from_model(model_id)
    
    # 1. Prepare base64 image if provided
    base64_image = None
    media_type = None
    if image_path and image_path.exists():
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")
        media_type = mimetypes.guess_type(image_path)[0] or "image/png"

    if provider == "anthropic":
        # Build Anthropic content block
        content = [{"type": "text", "text": prompt}]
        if base64_image:
            content.insert(0, {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64_image,
                },
            })
            
        resp = get_client("anthropic").messages.create(
            model=model_id,
            max_tokens=1600,
            messages=[{"role": "user", "content": content}],
        )
        blocks = []
        for part in resp.content or []:
            text = getattr(part, "text", None)
            if text:
                blocks.append(text)
        return "\n".join(blocks).strip()

    # Build OpenAI content block
    content = [{"type": "text", "text": prompt}]
    if base64_image:
        content.insert(0, {
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{base64_image}"
            }
        })
        
    resp = get_client("openai").chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": content}],
    )
    return resp.choices[0].message.content.strip()


def ask_prompt(prompt: str, model_id: str = None) -> str:
    cfg = load_config()
    return _ask_model(prompt, model_id or cfg["model"])

cleanup_old_screens()

# -------- OCR (macOS Vision) --------
from Foundation import NSURL
from Vision import (
    VNRecognizeTextRequest,
    VNImageRequestHandler,
    VNRequestTextRecognitionLevelAccurate,
    VNRequestTextRecognitionLevelFast,
)


def ocr_image(path: Path) -> str:
    """
    Extracts text from an image located at the given path using the macOS Vision framework.
    
    Supports configuring recognition level (accurate or fast) and languages via config.

    Args:
        path (Path): Path to the image file to run OCR on.

    Returns:
        str: The text extracted from the image.
    """
    lines = []

    def handler(req, err):
        if err and CONFIG["debug_ocr"]:
            print("[OCR ERROR]", err)
        if err:
            return
        for obs in req.results() or []:
            cand = obs.topCandidates_(1)
            if cand:
                lines.append(str(cand[0].string()))

    req = VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
    level = CONFIG.get("ocr_recognition_level", "accurate")
    if level == "fast":
        req.setRecognitionLevel_(VNRequestTextRecognitionLevelFast)
    else:
        req.setRecognitionLevel_(VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(True)
    langs = CONFIG.get("ocr_languages")
    if langs:
        req.setRecognitionLanguages_(langs)

    url = NSURL.fileURLWithPath_(str(path))
    h = VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    h.performRequests_error_([req], None)

    return "\n".join(lines)


# -------- OpenAI ask --------
def ask_gpt(text: str, image_path: Path = None) -> str:
    """
    Asks the configured AI model a question based on OCR-extracted text and the exact screenshot image.

    Args:
        text (str): The OCR-extracted fallback text.
        image_path (Path, optional): Path to the screenshot image file that will be analyzed natively by the model.

    Returns:
        str: The AI's response.
    """
    cfg = load_config()
    
    # We include both the OCR extracted text and the image itself giving the AI maximum context
    prompt = cfg["prompt_main"].format(text=text)
    return _ask_model(prompt, cfg["model"], image_path=image_path)


def ask_followup(context: str, question: str) -> str:
    """
    Sends a follow-up question to the AI, maintaining conversation context.

    Args:
        context (str): The previous conversation context (messages).
        question (str): The user's new question.

    Returns:
        str: The AI's response to the follow-up question.
    """
    cfg = load_config()
    prompt = cfg["prompt_followup"].format(context=context, question=question)
    return _ask_model(prompt, cfg["model"])


def general_ask(question: str) -> str:
    """
    Asks the AI a general question without screenshot context.

    Args:
        question (str): The question to ask.

    Returns:
        str: The AI's response.
    """
    cfg = load_config()
    prompt = cfg["prompt_general"].format(question=question)
    return _ask_model(prompt, cfg["model"])


# -------- Screenshot --------


def take_ss(out: Path, target=None, full_slide=False):
    """
    Captures a screenshot of the target active window and saves it to a file.

    Args:
        out (Path): The output file path for the screenshot.
        target (str, optional): The target application (e.g., 'chrome', 'powerpoint'). Defaults to None.
        full_slide (bool, optional): If True and target is 'powerpoint', requires Slide Show mode to capture the full slide. Defaults to False.

    Raises:
        RuntimeError: If capturing the window fails.
    """
    capture_target = (target or CONFIG.get("capture_target", "chrome")).lower()
    ok, err = capture_active_window(out, target=capture_target, full_slide=full_slide)
    if not ok:
        raise RuntimeError(err or f"Failed to capture {capture_target} window.")


def extract_first_code_block(text: str) -> str:
    """
    Extracts the content of the first markdown code block from a text string.

    Args:
        text (str): The text containing markdown code blocks.

    Returns:
        str: The extracted code block content, or an empty string if none are found.
    """
    # Look for code blocks with any language or no language specifier
    matches = re.findall(r"```(?:\w+)?\n(.*?)\n```", text, re.DOTALL)
    if not matches:
        # Fallback for blocks that might not have a trailing newline before the closing backticks
        matches = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    return matches[0].strip() if matches else ""


def copy_to_clipboard(text: str):
    """
    Copies the given text to the macOS clipboard using the `pbcopy` utility.

    Args:
        text (str): The text to copy.
    """
    if not text:
        return
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)


def build_context(session_id) -> str:
    """
    Builds a formatted string of the conversation history for a given session.

    Truncates the context to a configurable maximum number of characters to fit within AI token limits.

    Args:
        session_id (ObjectId): The ID of the database session.

    Returns:
        str: The formatted conversation context.
    """
    msgs = get_session_messages(session_id)
    lines = []
    for m in msgs:
        role = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{role}: {m['text']}")
    ctx = "\n".join(lines)
    max_chars = CONFIG.get("max_context_chars", 8000)
    if len(ctx) > max_chars:
        ctx = ctx[-max_chars:]
    return ctx


# -------- Main --------
def take_screenshot_and_analyze(session_title=None, target=None, full_slide=False):
    """
    Main workflow to capture a screenshot, run OCR, save to a database session, and ask the AI.

    Args:
        session_title (str, optional): Custom title for the session. Defaults to None.
        target (str, optional): The target application to capture. Defaults to None.
        full_slide (bool, optional): Whether to capture PowerPoint in full slide mode. Defaults to False.

    Returns:
        tuple: (session_id, (extracted_text, ai_response, image_path)) if successful, or (None, error_message) if it fails.
    """
    require_api_key()

    img = WORK_DIR / f"ss_{int(time.time())}.png"
    try:
        take_ss(img, target=target, full_slide=full_slide)
    except Exception as e:
        return None, str(e)

    text = ocr_image(img)

    if not text.strip():
        text = "(No text detected via macOS OCR, but the image will still be processed visually by the Language Model)"

    title = session_title or time.strftime("Screenshot session %Y-%m-%d %H:%M:%S")
    session_id = create_session(title)
    add_message(session_id, "user", text, str(img))

    # We now pass the exact screenshot image for multimodal reasoning alongside the backup OCR text.
    ans = ask_gpt(text, image_path=img)
    add_message(session_id, "assistant", ans)
    
    return session_id, (text, ans, img)


def handle_ai_response(ans: str, console=None):
    """
    Unified handler for organizing AI responses. Prints to the terminal as Markdown and manages code auto-copying.
    
    Args:
        ans (str): The response string from the AI.
        console (rich.console.Console, optional): Configured Rich console instance. Defaults to None.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from .ss_ai import extract_first_code_block, copy_to_clipboard
    from .config import load_config

    if console is None:
        console = Console()
        
    cfg = load_config()

    # 1. Print Main Answer
    console.print(Panel(Markdown(ans), title="AI Analysis", border_style="green"))

    # 2. Handle Autocopy
    if cfg.get("autocopy", False):
        mode = cfg.get("autocopy_mode", "answer")
        code_block = extract_first_code_block(ans)
        payload = code_block if (mode == "code" and code_block) else ans
        
        if payload:
            copy_to_clipboard(payload)
            msg = "Code copied" if mode == "code" and code_block else "Answer copied"
            console.print(f"[dim italic]({msg} to clipboard)[/dim italic]")


def main():
    """
    Entry point for running the screenshot analysis interactively without CLI arguments.
    """
    require_api_key()

    print("\n[CAPTURE] Analyzing...")
    session_id, result = take_screenshot_and_analyze()
    if not session_id:
        print(result)
        return

    text, ans, img = result
    handle_ai_response(ans)

    while True:
        try:
            q = input("Follow-up (blank to finish): ").strip()
        except EOFError:
            break
        if not q:
            break
        ctx = build_context(session_id)
        follow_ans = ask_followup(ctx, q)
        print("\n[AI FOLLOW-UP]\n")
        print(follow_ans)
        add_message(session_id, "user", q)
        add_message(session_id, "assistant", follow_ans)


if __name__ == "__main__":
    main()
