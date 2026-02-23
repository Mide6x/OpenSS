import os
import re
import subprocess
import time
from pathlib import Path

from openai import OpenAI
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from dotenv import load_dotenv

from .config import load_config
from .cleanup import cleanup_old_screens
from .db import add_message, create_session

# --- CONFIG ---
CONFIG = load_config()
MODEL = CONFIG["model"]
SCREENSHOT_DIR = Path.home() / "Desktop"

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
cleanup_old_screens()

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


def ask(text: str) -> str:
    prompt = CONFIG["prompt_watch"].format(text=text)
    r = client.responses.create(model=MODEL, input=prompt)
    return r.output_text.strip()


def extract_first_code_block(text: str) -> str:
    matches = re.findall(r"```(?:[a-zA-Z0-9_+-]+)?\\n(.*?)```", text, re.DOTALL)
    return matches[0].strip() if matches else ""


def copy_to_clipboard(text: str):
    if not text:
        return
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)


class Handler(FileSystemEventHandler):
    def on_created(self, event):
        p = Path(event.src_path)
        if not p.name.lower().startswith("screenshot"):
            return
        time.sleep(0.3)

        print("\n--- Screenshot detected ---")
        txt = ocr_image(p)
        if not txt.strip():
            print("No text.")
            return

        session_id = create_session(time.strftime("Screenshot session %Y-%m-%d %H:%M:%S"))
        add_message(session_id, "user", txt, str(p))

        if CONFIG["debug_ocr"]:
            size = p.stat().st_size if p.exists() else 0
            print(f"[OCR DEBUG] image={p} bytes={size}")

        print("\n[OCR]\n", txt[: CONFIG["max_ocr_preview"]])
        print("\n[AI]\n")
        ans = ask(txt)
        print(ans)
        add_message(session_id, "assistant", ans)
        code_block = extract_first_code_block(ans)
        if code_block:
            print("\n[CODE DETECTED]\n")
            print(code_block)

        if CONFIG["autocopy"]:
            payload = code_block if (CONFIG["autocopy_mode"] == "code" and code_block) else ans
            copy_to_clipboard(payload)
            print("\n[CLIPBOARD] copied.\n")
        print("\n--------------------------")


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY")

    obs = Observer()
    obs.schedule(Handler(), str(SCREENSHOT_DIR), recursive=False)
    obs.start()

    print("Watching screenshots...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()


if __name__ == "__main__":
    main()
