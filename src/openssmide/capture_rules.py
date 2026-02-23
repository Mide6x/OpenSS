import subprocess
from pathlib import Path

import Quartz


def _list_onscreen_windows():
    return Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
    )


def _display_id_for_bounds(bounds):
    if not bounds:
        return Quartz.CGMainDisplayID()
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
    return display_id


def _find_window_by_owner(owner_names):
    windows = _list_onscreen_windows()
    for w in windows:
        if w.get("kCGWindowLayer", 0) != 0:
            continue
        if w.get("kCGWindowAlpha", 1) == 0:
            continue
        owner = (w.get("kCGWindowOwnerName") or "").lower()
        if owner not in owner_names:
            continue
        return w
    return None


def capture_active_chrome_window(out_path: Path):
    chrome_window = _find_window_by_owner(["google chrome", "chrome"])
    if not chrome_window:
        return False, "Chrome window not found. Open Chrome and try again."

    term_window = _find_window_by_owner(["terminal", "iterm2", "iterm"])
    if not term_window:
        return False, "Terminal window not found."

    chrome_bounds = chrome_window.get("kCGWindowBounds")
    term_bounds = term_window.get("kCGWindowBounds")
    chrome_display = _display_id_for_bounds(chrome_bounds)
    term_display = _display_id_for_bounds(term_bounds)

    if chrome_display != term_display:
        return (
            False,
            "Chrome and Terminal must be on the same display. Move them to the same screen and retry.",
        )

    win_id = chrome_window.get("kCGWindowNumber")
    if not win_id:
        return False, "Chrome window ID not found."

    subprocess.run(
        ["screencapture", "-x", "-l", str(win_id), str(out_path)],
        check=True,
    )
    return True, None
