"""WhatsApp messaging tool — send messages to known contacts via hermes-gateway."""
import json
import re
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool

WA_ENDPOINT = "http://localhost:3000/send"

# Known contacts — add more here as needed
CONTACTS = {
    "bea":   "34679205712@c.us",
    "me":    "34722556031@c.us",
    "glenn": "34722556031@c.us",
    "myself": "34722556031@c.us",
}


class WhatsAppTool(Tool):
    name        = "whatsapp"
    description = "Send WhatsApp messages to known contacts via hermes-gateway"
    triggers    = [
        "send whatsapp",
        "whatsapp to",
        "whatsapp bea",
        "message bea",
        "send message to bea",
        "text bea",
        "send to bea",
        "send bea",
        "whatsapp me",
        "send whatsapp to",
        "send a whatsapp",
    ]

    def _resolve_contact(self, query: str):
        """Return (name, chat_id) for the first contact found in query."""
        q = query.lower()
        for name, chat_id in CONTACTS.items():
            if name in q:
                return name.capitalize(), chat_id
        return None, None

    def _extract_message(self, query: str):
        """Pull the message body from phrases like 'saying X', 'that says X', 'tell her X'."""
        patterns = [
            r'saying[:\s]+"?(.+)"?$',
            r"saying[:\s]+'?(.+)'?$",
            r'that says[:\s]+"?(.+)"?$',
            r"that says[:\s]+'?(.+)'?$",
            r'tell (?:her|him|them)[:\s]+"?(.+)"?$',
            r"tell (?:her|him|them)[:\s]+'?(.+)'?$",
            r'message[:\s]+"?(.+)"?$',
            r"message[:\s]+'?(.+)'?$",
            r':\s+"?(.+)"?$',
            r':\s+(.+)$',
        ]
        for pat in patterns:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                return m.group(1).strip().strip('"').strip("'")
        return None

    def _send(self, chat_id: str, message: str):
        """POST to hermes-gateway, return (success, error_msg)."""
        payload = json.dumps({"chatId": chat_id, "message": message})
        try:
            result = subprocess.run(
                ["curl", "-sf", "-X", "POST",
                 "-H", "Content-Type: application/json",
                 "-d", payload,
                 WA_ENDPOINT],
                capture_output=True, text=True, timeout=10
            )
            resp = json.loads(result.stdout)
            if resp.get("success"):
                return True, None
            return False, resp.get("error", "unknown error")
        except Exception as e:
            return False, str(e)

    def execute(self, query: str, **kwargs) -> str:
        contact_name, chat_id = self._resolve_contact(query)
        if not chat_id:
            return (
                "I don't know that contact. Known contacts: "
                + ", ".join(k.capitalize() for k in CONTACTS if k not in ("me", "myself", "glenn"))
                + ". You can add more in alice-assistant/tools/whatsapp.py."
            )

        message = self._extract_message(query)
        if not message:
            return f"What do you want to say to {contact_name}? Try: 'send whatsapp to {contact_name} saying hello'"

        ok, err = self._send(chat_id, message)
        if ok:
            return f"Sent to {contact_name} on WhatsApp."
        return f"Couldn't send to {contact_name}: {err}. Is hermes-gateway running?"
