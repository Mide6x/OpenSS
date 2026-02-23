import json
from pathlib import Path


DEFAULT_CONFIG = {
    "model": "gpt-4.1-nano",
    "autocopy": True,
    "autocopy_mode": "answer",  # "answer" or "code"
    "max_ocr_preview": 800,
    "max_context_chars": 8000,
    "ocr_languages": ["en-US"],
    "ocr_recognition_level": "accurate",  # "accurate" or "fast"
    "debug_ocr": False,
    "prompt_main": (
        "OCR TEXT:\n{text}\n\n"
        "TASK:\n"
        "- Detect all questions (coding, MCQ, theory, math).\n"
        "- Respond ONLY with a numbered list of answers.\n"
        "- Do NOT rewrite the questions.\n"
        "- Keep answers concise and neat.\n"
        "- For coding tasks, provide code only.\n"
        "- For MCQ, give option letter/number plus a short reason.\n"
        "- If missing info, say \"Missing info: ...\".\n"
    ),
    "prompt_watch": (
        "OCR TEXT:\n{text}\n\n"
        "TASK:\n"
        "- Respond ONLY with a numbered list of answers.\n"
        "- Do NOT rewrite the questions.\n"
        "- Keep answers concise and neat.\n"
        "- For coding tasks, provide code only.\n"
        "- For MCQ, give option letter/number plus a short reason.\n"
        "- If missing info, say \"Missing info: ...\".\n"
    ),
    "prompt_followup": (
        "Conversation so far:\n{context}\n\n"
        "User follow-up:\n{question}\n\n"
        "Answer clearly and concisely."
    ),
}


def load_config() -> dict:
    path = Path(__file__).with_name("config.json")
    if not path.exists():
        return DEFAULT_CONFIG.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_CONFIG.copy()
    cfg = DEFAULT_CONFIG.copy()
    cfg.update({k: v for k, v in data.items() if v is not None})
    return cfg
