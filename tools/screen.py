"""Screen awareness tool — take screenshots for Alice to analyze."""
import subprocess
import os
from tools.base import Tool

SCREENSHOT_PATH = '/tmp/alice_screenshot.png'
SCREENSHOT_COMPRESSED = '/tmp/alice_screenshot_small.png'
MAX_SIZE_BYTES = 4 * 1024 * 1024  # 4MB — stay under hermes 5MB limit


def take_screenshot() -> tuple[bool, str]:
    """Take a screenshot with grim. Returns (success, file_path_or_error)."""
    try:
        result = subprocess.run(
            ['grim', SCREENSHOT_PATH],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return False, f"grim failed: {result.stderr}"
        if not os.path.exists(SCREENSHOT_PATH):
            return False, "Screenshot file not created"
        return True, SCREENSHOT_PATH
    except FileNotFoundError:
        return False, "grim not installed"
    except Exception as e:
        return False, str(e)


def compress_screenshot(path: str) -> str:
    """Compress screenshot to under MAX_SIZE_BYTES if needed. Returns path to use."""
    if not os.path.exists(path):
        return path
    size = os.path.getsize(path)
    if size <= MAX_SIZE_BYTES:
        return path

    # Resize to 50% using ImageMagick convert (already used by hermes internally)
    try:
        result = subprocess.run(
            ['convert', path, '-resize', '50%', '-quality', '85', SCREENSHOT_COMPRESSED],
            capture_output=True, timeout=10
        )
        if result.returncode == 0 and os.path.exists(SCREENSHOT_COMPRESSED):
            return SCREENSHOT_COMPRESSED
    except Exception:
        pass
    return path  # return original if compress fails


class ScreenTool(Tool):
    name = "screen"
    description = "Take a screenshot (without analysis)"
    triggers = [
        "take a screenshot", "take screenshot", "grab a screenshot",
        "save screenshot", "capture screen", "capture my screen",
    ]

    def execute(self, query: str) -> str:
        ok, result = take_screenshot()
        if not ok:
            return f"Screenshot failed: {result}"
        return f"Screenshot saved to {result}"
