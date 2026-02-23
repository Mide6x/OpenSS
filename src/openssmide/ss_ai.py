import os
import re
import subprocess
import time
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

from .config import load_config
from .cleanup import cleanup_old_screens
from .capture_rules import (
    capture_active_chrome_window,
    capture_terminal_display_then_mask_terminal,
)
from .db import add_message, create_session, get_session_messages

# --- CONFIG ---
CONFIG = load_config()
MODEL = CONFIG["model"]
WORK_DIR = Path.home() / ".ss_ai"
WORK_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
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
def ask_gpt(text: str) -> str:
    prompt = CONFIG["prompt_main"].format(text=text)
    resp = client.responses.create(
        model=MODEL,
        input=prompt,
    )
    return resp.output_text.strip()


def ask_followup(context: str, question: str) -> str:
    prompt = CONFIG["prompt_followup"].format(context=context, question=question)
    resp = client.responses.create(
        model=MODEL,
        input=prompt,
    )
    return resp.output_text.strip()


def general_ask(question: str) -> str:
    prompt = CONFIG["prompt_general"].format(question=question)
    resp = client.responses.create(
        model=MODEL,
        input=prompt,
    )
    return resp.output_text.strip()


# -------- Screenshot --------


def take_ss(out: Path):
    if capture_active_chrome_window(out):
        return
    capture_terminal_display_then_mask_terminal(out)


def extract_first_code_block(text: str) -> str:
    # Look for code blocks with any language or no language specifier
    matches = re.findall(r"```(?:\w+)?\n(.*?)\n```", text, re.DOTALL)
    if not matches:
        # Fallback for blocks that might not have a trailing newline before the closing backticks
        matches = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    return matches[0].strip() if matches else ""


def copy_to_clipboard(text: str):
    if not text:
        return
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)


def build_context(session_id) -> str:
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
def take_screenshot_and_analyze(session_title=None):
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY first")

    img = WORK_DIR / f"ss_{int(time.time())}.png"
    take_ss(img)

    text = ocr_image(img)

    if not text.strip():
        return None, "No text detected. Try a clearer or larger selection."

    title = session_title or time.strftime("Screenshot session %Y-%m-%d %H:%M:%S")
    session_id = create_session(title)
    add_message(session_id, "user", text, str(img))

    ans = ask_gpt(text)
    add_message(session_id, "assistant", ans)
    
    return session_id, (text, ans, img)


def handle_ai_response(ans: str, console=None):
    """Unified handler for AI responses: prints Markdown, extracts code, and handles autocopy."""
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

    # 2. Extract and Print Code
    code_block = extract_first_code_block(ans)
    if code_block:
        console.print(Panel(code_block, title="Extracted Code", border_style="bold yellow"))

    # 3. Handle Autocopy
    if cfg.get("autocopy", False):
        mode = cfg.get("autocopy_mode", "answer")
        payload = code_block if (mode == "code" and code_block) else ans
        
        if payload:
            copy_to_clipboard(payload)
            msg = "Code copied" if mode == "code" and code_block else "Answer copied"
            console.print(f"[dim italic]({msg} to clipboard)[/dim italic]")


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY first")

    print("\n[CAPTURE] Taking screenshot...")
    session_id, result = take_screenshot_and_analyze()
    if not session_id:
        print(result)
        return

    text, ans, img = result

    print("\n[OCR TEXT]\n")
    print(text[: CONFIG["max_ocr_preview"]])
    print("\n[AI ANSWERS]\n")
    print(ans)
    
    code_block = extract_first_code_block(ans)
    if code_block:
        print("\n[CODE DETECTED]\n")
        print(code_block)

    if CONFIG["autocopy"]:
        payload = code_block if (CONFIG["autocopy_mode"] == "code" and code_block) else ans
        copy_to_clipboard(payload)
        print("\n[CLIPBOARD] copied.\n")

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
