#!/usr/bin/env python3
"""Alice startup greeting - runs at boot."""
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.tts import TTS
from tools.calendar import CalendarTool


def get_time_greeting() -> str:
    """Get appropriate greeting for time of day."""
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    elif hour < 21:
        return "Good evening"
    else:
        return "Hey there, night owl"


def get_day_with_suffix(day: int) -> str:
    """Get day number with ordinal suffix."""
    if 11 <= day <= 13:
        return f"{day}th"
    suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return f"{day}{suffix}"


def get_todays_events() -> list[str]:
    """Get calendar events for today."""
    cal = CalendarTool()
    today = datetime.now()

    apts_file = cal.apts_file
    if not apts_file.exists():
        return []

    events = []
    today_str = today.strftime("%m/%d/%Y")

    with open(apts_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith(today_str):
                # Extract description
                if '|' in line:
                    desc = line.split('|', 1)[1]
                    # Extract time if present
                    import re
                    time_match = re.search(r'@ (\d{2}):(\d{2})', line)
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = time_match.group(2)
                        ampm = "AM" if hour < 12 else "PM"
                        if hour > 12:
                            hour -= 12
                        elif hour == 0:
                            hour = 12
                        events.append(f"{desc} at {hour}:{minute} {ampm}")
                    else:
                        events.append(desc)

    return events


def get_upcoming_events(days: int = 5) -> list[tuple[str, str]]:
    """Get events for the next N days (excluding today)."""
    cal = CalendarTool()

    apts_file = cal.apts_file
    if not apts_file.exists():
        return []

    events = []
    today = datetime.now()

    with open(apts_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or '|' not in line:
                continue

            # Parse date from line
            import re
            date_match = re.match(r'(\d{2})/(\d{2})/(\d{4})', line)
            if not date_match:
                continue

            month, day, year = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            try:
                event_date = datetime(year, month, day)
            except ValueError:
                continue

            # Check if within next N days (but not today)
            days_until = (event_date.date() - today.date()).days
            if 1 <= days_until <= days:
                desc = line.split('|', 1)[1]
                day_name = event_date.strftime("%A")
                events.append((day_name, desc))

    return events


def build_greeting() -> str:
    """Build the full greeting text."""
    now = datetime.now()

    # Time-appropriate greeting
    time_greeting = get_time_greeting()

    # Day info
    day_name = now.strftime("%A")  # Monday, Tuesday, etc.
    day_number = get_day_with_suffix(now.day)
    month_name = now.strftime("%B")

    # Start building greeting
    greeting = f"{time_greeting} Glenn. It's {day_name}, {month_name} {day_number}."

    # Today's events
    todays_events = get_todays_events()
    if todays_events:
        if len(todays_events) == 1:
            greeting += f" You have one thing on your calendar today: {todays_events[0]}."
        else:
            events_text = ", ".join(todays_events[:-1]) + f", and {todays_events[-1]}"
            greeting += f" You have {len(todays_events)} things on your calendar today: {events_text}."
    else:
        greeting += " Your calendar is clear for today."

    # Upcoming events
    upcoming = get_upcoming_events(5)
    if upcoming:
        greeting += " Coming up in the next few days: "
        upcoming_parts = []
        for day_name, desc in upcoming[:3]:  # Limit to 3 to keep it concise
            upcoming_parts.append(f"{desc} on {day_name}")
        greeting += ", ".join(upcoming_parts) + "."

    # The signature ending
    greeting += " So Glenn, what are you trying to fuck up today?"

    return greeting


def main():
    """Run the startup greeting."""
    # Small delay to let audio system initialize
    import time
    time.sleep(2)

    greeting = build_greeting()
    print(f"Alice: {greeting}")

    # Speak it
    tts = TTS()
    tts.speak_raw(greeting)


if __name__ == "__main__":
    main()
