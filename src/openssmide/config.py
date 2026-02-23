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
    "prompt_general": (
        "User question: {question}\n\n"
        "Answer clearly and concisely."
    ),
}

AVAILABLE_MODELS = [
    {"id": "gpt-4o-mini", "name": "GPT-4o mini", "desc": "Fast, smart, and extremely cheap (Best for most tasks)"},
    {"id": "gpt-4o", "name": "GPT-4o", "desc": "Flagship model. High performance, standard cost"},
    {"id": "o3-mini", "name": "o3-mini", "desc": "Latest reasoning model. Fast & very smart"},
    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "desc": "Reliable older flagship. More expensive"},
]


def load_config():
    path = Path(__file__).resolve().parents[2] / "config.json"
    if not path.exists():
        return DEFAULT_CONFIG
    try:
        user_cfg = json.loads(path.read_text())
        return {**DEFAULT_CONFIG, **user_cfg}
    except Exception:
        return DEFAULT_CONFIG


def save_config(new_config):
    path = Path(__file__).resolve().parents[2] / "config.json"
    path.write_text(json.dumps(new_config, indent=4))
