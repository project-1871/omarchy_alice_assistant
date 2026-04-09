"""Spam tool — send repeated themed WhatsApp messages to a contact."""
import json
import random
import subprocess
import threading
import time
from pathlib import Path

SPAM_MESSAGES_FILE = Path.home() / ".alice_spam_messages.json"
WA_ENDPOINT = "http://localhost:3000/send"

# Keyword → theme mapping for fuzzy matching
THEME_KEYWORDS = {
    "romantic_spanish_pokemon": ["pokemon", "pokémon", "poki", "pikachu", "romantic spanish", "español pokémon"],
    "romantic_spanish":         ["romantic", "love", "amor", "español", "spanish", "quiero"],
    "funny_spanish":            ["funny", "gracioso", "humor", "joke"],
}


def load_messages(theme: str = None) -> list:
    """Load messages for a given theme. Falls back to romantic_spanish_pokemon."""
    try:
        with open(SPAM_MESSAGES_FILE) as f:
            data = json.load(f)
        themes = data.get("themes", {})
    except Exception:
        return []

    if theme and theme in themes:
        return themes[theme]

    # Fuzzy theme match
    if theme:
        theme_lower = theme.lower()
        for key, keywords in THEME_KEYWORDS.items():
            if any(kw in theme_lower for kw in keywords):
                return themes.get(key, [])

    return themes.get("romantic_spanish_pokemon", [])


def list_themes() -> list:
    """Return available theme names."""
    try:
        with open(SPAM_MESSAGES_FILE) as f:
            return list(json.load(f).get("themes", {}).keys())
    except Exception:
        return []


def send_one(chat_id: str, message: str) -> bool:
    """Send a single WhatsApp message. Returns True on success."""
    payload = json.dumps({"chatId": chat_id, "message": message})
    try:
        r = subprocess.run(
            ["curl", "-sf", "-X", "POST",
             "-H", "Content-Type: application/json",
             "-d", payload, WA_ENDPOINT],
            capture_output=True, text=True, timeout=10
        )
        return json.loads(r.stdout).get("success", False)
    except Exception:
        return False


class SpamSession:
    """
    Runs a spam loop in a background thread.
    Control via start() / stop().
    Callbacks: on_sent(count, total, message), on_done(count).
    """

    def __init__(self, chat_id: str, messages: list, count: int, interval: int,
                 on_sent=None, on_done=None):
        self.chat_id  = chat_id
        self.messages = messages[:]
        random.shuffle(self.messages)
        self.count    = count      # total messages to send
        self.interval = interval   # seconds between sends
        self.on_sent  = on_sent
        self.on_done  = on_done
        self._stop    = threading.Event()
        self._thread  = None
        self.sent     = 0

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        pool = self.messages[:]
        random.shuffle(pool)
        idx = 0

        for i in range(self.count):
            if self._stop.is_set():
                break

            msg = pool[idx % len(pool)]
            idx += 1
            if idx >= len(pool):
                pool = self.messages[:]
                random.shuffle(pool)
                idx = 0

            send_one(self.chat_id, msg)
            self.sent += 1

            if self.on_sent:
                self.on_sent(self.sent, self.count, msg)

            # Wait interval, but check stop every second
            for _ in range(self.interval):
                if self._stop.is_set():
                    break
                time.sleep(1)

        if self.on_done:
            self.on_done(self.sent)
