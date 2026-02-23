import subprocess
from pathlib import Path

import Quartz
from PIL import Image, ImageDraw


def _list_onscreen_windows():
    return Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
    )


def capture_active_chrome_window(out_path: Path) -> bool:
    windows = _list_onscreen_windows()
    for w in windows:
        if w.get("kCGWindowLayer", 0) != 0:
            continue
        if w.get("kCGWindowAlpha", 1) == 0:
            continue
        owner = (w.get("kCGWindowOwnerName") or "").lower()
        if "chrome" not in owner:
            continue
        win_id = w.get("kCGWindowNumber")
        if not win_id:
            continue
        subprocess.run(
            ["screencapture", "-x", "-l", str(win_id), str(out_path)],
            check=True,
        )
        return True
    return False


def _find_terminal_window_rect_and_display():
    windows = _list_onscreen_windows()

    term_window = None
    for w in windows:
        owner = (w.get("kCGWindowOwnerName") or "").lower()
        if owner in ["terminal", "iterm2", "iterm"]:
            if w.get("kCGWindowLayer", 0) != 0:
                continue
            if w.get("kCGWindowAlpha", 1) == 0:
                continue
            term_window = w
            break

    if not term_window:
        return Quartz.CGMainDisplayID(), None

    bounds = term_window.get("kCGWindowBounds")
    rect = Quartz.CGRectMake(
        bounds["X"], bounds["Y"], bounds["Width"], bounds["Height"]
    )

    display_id = Quartz.CGMainDisplayID()
    try:
        result = Quartz.CGGetDisplaysWithRect(rect, 1, None)
        if isinstance(result, tuple) and len(result) >= 3:
            _, count, displays = result
            if count and displays:
                display_id = displays[0]
        elif isinstance(result, tuple) and len(result) == 2:
            count, displays = result
            if count and displays:
                display_id = displays[0]
    except Exception:
        pass

    return display_id, bounds


def capture_terminal_display_then_mask_terminal(out_path: Path) -> None:
    display_id, term_bounds = _find_terminal_window_rect_and_display()

    display_idx = 1
    try:
        display_idx = Quartz.CGDisplayIDToOpenGLDisplayMask(display_id).bit_length()
    except Exception:
        display_idx = 1
    subprocess.run(
        ["screencapture", "-x", "-D", str(display_idx), str(out_path)],
        check=True,
    )

    if not term_bounds:
        return

    db = Quartz.CGDisplayBounds(display_id)
    display_origin_x = db.origin.x
    display_origin_y = db.origin.y

    x = int(term_bounds["X"] - display_origin_x)
    y = int(term_bounds["Y"] - display_origin_y)
    w = int(term_bounds["Width"])
    h = int(term_bounds["Height"])

    img = Image.open(out_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle([x, y, x + w, y + h], fill=(0, 0, 0))
    img.save(out_path)
