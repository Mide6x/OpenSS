import subprocess
from pathlib import Path

import Quartz

TARGET_OWNERS = {
    "chrome": ["google chrome", "chrome"],
    "powerpoint": ["microsoft powerpoint", "powerpoint"],
    "word": ["microsoft word", "word"],
}


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


def _normalize_target(target: str) -> str:
    key = (target or "").strip().lower()
    if key not in TARGET_OWNERS:
        supported = ", ".join(sorted(TARGET_OWNERS))
        raise ValueError(f"Unsupported capture target '{target}'. Supported: {supported}.")
    return key


def _is_usable_window(window_info):
    if window_info.get("kCGWindowLayer", 0) != 0:
        return False
    if window_info.get("kCGWindowAlpha", 1) == 0:
        return False
    bounds = window_info.get("kCGWindowBounds") or {}
    width = bounds.get("Width", 0)
    height = bounds.get("Height", 0)
    if width < 320 or height < 240:
        return False
    return True


def _owner_matches(window_info, owner_names):
    owner = (window_info.get("kCGWindowOwnerName") or "").lower()
    return owner in owner_names


def _find_window_by_owner(owner_names, prefer_title_contains=None):
    windows = _list_onscreen_windows()
    candidates = []
    for w in windows:
        if not _is_usable_window(w):
            continue
        if not _owner_matches(w, owner_names):
            continue
        candidates.append(w)

    if not candidates:
        return None

    if prefer_title_contains:
        look_for = prefer_title_contains.lower()
        for w in candidates:
            title = (w.get("kCGWindowName") or "").lower()
            if look_for in title:
                return w

    # Choose the largest visible window to avoid tiny helper/palette windows.
    def area(w):
        bounds = w.get("kCGWindowBounds") or {}
        return bounds.get("Width", 0) * bounds.get("Height", 0)

    candidates.sort(key=area, reverse=True)
    return candidates[0]


def _process_running(owner_names):
    windows = _list_onscreen_windows()
    for w in windows:
        if _owner_matches(w, owner_names):
            return True
    return False

def detect_active_target() -> str:
    """Detects which of the supported apps is currently open."""
    for target_key, owner_names in TARGET_OWNERS.items():
        if _process_running(owner_names):
            return target_key
    return "chrome"  # fallback default


def capture_active_window(out_path: Path, target="chrome", full_slide=False):
    target_key = _normalize_target(target)
    owner_names = TARGET_OWNERS[target_key]
    if target_key == "powerpoint":
        target_display_name = "PowerPoint"
    elif target_key == "word":
        target_display_name = "Word"
    else:
        target_display_name = "Chrome"

    if not _process_running(owner_names):
        return (
            False,
            f"{target_display_name} process/window not found. Open {target_display_name} and try again.",
        )

    preferred_title = "slide show" if target_key == "powerpoint" and full_slide else None
    app_window = _find_window_by_owner(owner_names, prefer_title_contains=preferred_title)
    if not app_window:
        return (
            False,
            f"{target_display_name} window not found. Ensure the target window is visible on screen.",
        )

    if target_key == "powerpoint" and full_slide:
        title = (app_window.get("kCGWindowName") or "").lower()
        if "slide show" not in title:
            return (
                False,
                "No PowerPoint Slide Show window found. Start Slide Show mode to capture full-slide view.",
            )

    term_window = _find_window_by_owner(["terminal", "iterm2", "iterm"])
    if not term_window:
        return False, "Terminal window not found."

    app_bounds = app_window.get("kCGWindowBounds")
    term_bounds = term_window.get("kCGWindowBounds")
    app_display = _display_id_for_bounds(app_bounds)
    term_display = _display_id_for_bounds(term_bounds)

    if app_display != term_display:
        return (
            False,
            f"{target_display_name} and Terminal must be on the same display. Move them to the same screen and retry.",
        )

    win_id = app_window.get("kCGWindowNumber")
    if not win_id:
        return False, f"{target_display_name} window ID not found."

    subprocess.run(
        ["screencapture", "-x", "-l", str(win_id), str(out_path)],
        check=True,
    )
    return True, None


def capture_active_chrome_window(out_path: Path):
    return capture_active_window(out_path, target="chrome", full_slide=False)


def capture_active_powerpoint_window(out_path: Path, full_slide=False):
    return capture_active_window(out_path, target="powerpoint", full_slide=full_slide)
