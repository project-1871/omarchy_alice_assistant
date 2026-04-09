#!/usr/bin/env python
"""Called by hermes alice-voice plugin to speak text via Alice's running TTS.

If Alice's GUI is running, writes to the IPC file and Alice speaks it
using her already-loaded KittenTTS (no VRAM conflict).
If Alice is not running, loads TTS directly as fallback.
"""
import sys
import os
import time

SPEAK_FILE = "/tmp/alice_speak_request.txt"
ALICE_DIR = os.path.dirname(os.path.abspath(__file__))


def alice_is_running() -> bool:
    """Check if Alice's GUI process is alive."""
    try:
        import subprocess
        # Must match a python process running main.py inside the alice directory specifically
        result = subprocess.run(
            ['pgrep', '-f', f'python.*{ALICE_DIR}/main\\.py'],
            capture_output=True
        )
        return result.returncode == 0
    except Exception:
        return False


def speak_via_alice(text: str):
    """Write text to IPC file for Alice to pick up and speak."""
    with open(SPEAK_FILE, 'w') as f:
        f.write(text)
    # Wait up to 5s for Alice to consume the file (confirms it was picked up)
    for _ in range(50):
        time.sleep(0.1)
        if not os.path.exists(SPEAK_FILE):
            return
    # File still there — Alice didn't pick it up, clean up
    try:
        os.remove(SPEAK_FILE)
    except Exception:
        pass


def speak_direct(text: str):
    """Fallback: load TTS directly when Alice isn't running."""
    os.chdir(ALICE_DIR)
    sys.path.insert(0, ALICE_DIR)
    from core.tts import TTS
    tts = TTS()
    tts.speak(text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(0)
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        sys.exit(0)

    if alice_is_running():
        speak_via_alice(text)
    else:
        speak_direct(text)
