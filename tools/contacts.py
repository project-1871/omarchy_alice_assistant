"""Contacts manager — loads/saves ~/.alice_contacts.json"""
import json
from pathlib import Path

CONTACTS_FILE = Path.home() / ".alice_contacts.json"

DEFAULT_CONTACTS = {
    "contacts": [
        {"name": "Bea",   "whatsapp": "34679205712", "emoji": "❤️"},
        {"name": "Me",    "whatsapp": "34722556031", "emoji": "👤"},
    ],
    "quick_messages": [
        "On my way 🚶",
        "Be home soon",
        "Call me when you can",
        "Good morning! ☀️",
        "Miss you ❤️",
        "Can you call me?",
        "All good here!",
    ]
}


def load():
    if not CONTACTS_FILE.exists():
        save(DEFAULT_CONTACTS)
        return DEFAULT_CONTACTS
    with open(CONTACTS_FILE) as f:
        return json.load(f)


def save(data: dict):
    with open(CONTACTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_contact(name: str, whatsapp: str, emoji: str = "👤"):
    data = load()
    # Update if exists, else append
    for c in data["contacts"]:
        if c["name"].lower() == name.lower():
            c["whatsapp"] = whatsapp
            c["emoji"] = emoji
            save(data)
            return
    data["contacts"].append({"name": name, "whatsapp": whatsapp, "emoji": emoji})
    save(data)


def import_google_csv(csv_path: str) -> int:
    """
    Import contacts from a Google Contacts CSV export.
    Returns number of contacts imported.
    Export from: contacts.google.com → Export → Google CSV
    """
    import csv
    data = load()
    existing_names = {c["name"].lower() for c in data["contacts"]}
    imported = 0

    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "").strip()
            if not name:
                continue
            # Try multiple phone columns Google CSV uses
            phone = ""
            for col in row:
                if "phone" in col.lower() and row[col].strip():
                    phone = row[col].strip()
                    break
            if not phone:
                continue

            # Normalise phone: strip +, spaces, dashes
            phone = phone.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if not phone.isdigit():
                continue

            if name.lower() not in existing_names:
                data["contacts"].append({"name": name, "whatsapp": phone, "emoji": "👤"})
                existing_names.add(name.lower())
                imported += 1

    save(data)
    return imported
