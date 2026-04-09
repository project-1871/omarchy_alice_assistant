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
from tools.news import fetch_news_briefing

TODO_FILE = Path.home() / ".local/share/calcurse/todo"


def get_time_greeting() -> str:
    """Get appropriate greeting for time of day."""
    hour = datetime.now().hour
    if hour < 12:
        return "Morning handsome"
    elif hour < 17:
        return "Hey there"
    elif hour < 21:
        return "Good evening"
    else:
        return "Hey night owl"


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

    import re
    today_md = today.strftime("%m/%d")  # month/day for yearly match

    with open(apts_file, 'r') as f:
        for line in f:
            line = line.strip()
            date_match = re.match(r'(\d{2}/\d{2})/\d{4}', line)
            if not date_match:
                continue
            line_md = date_match.group(1)
            is_today = line.startswith(today_str)
            is_yearly_today = False
            if not is_today and line_md == today_md and '|' in line:
                raw_desc = line.split('|', 1)[1]
                if raw_desc.startswith('YEARLY:'):
                    is_yearly_today = True

            if is_today or is_yearly_today:
                if '|' in line:
                    desc = line.split('|', 1)[1]
                    if desc.startswith('YEARLY:'):
                        desc = desc[7:]
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


def get_pending_todos() -> int:
    """Count pending (uncompleted) todo items."""
    if not TODO_FILE.exists():
        return 0
    count = 0
    try:
        for line in TODO_FILE.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            import re
            match = re.match(r'\[(\d+)\]', line)
            if match:
                count += 1
    except Exception:
        pass
    return count


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
            # For YEARLY events, compute days_until ignoring year
            desc = line.split('|', 1)[1]
            is_yearly = desc.startswith('YEARLY:')
            if is_yearly:
                # Check month/day match for current or next year
                this_year_date = event_date.replace(year=today.year)
                next_year_date = event_date.replace(year=today.year + 1)
                days_until_this = (this_year_date.date() - today.date()).days
                days_until_next = (next_year_date.date() - today.date()).days
                days_until = days_until_this if 1 <= days_until_this <= days else (days_until_next if 1 <= days_until_next <= days else -1)
                check_date = this_year_date if 1 <= days_until_this <= days else next_year_date
            else:
                days_until = (event_date.date() - today.date()).days
                check_date = event_date
            if 1 <= days_until <= days:
                if is_yearly:
                    desc = desc[7:]
                day_name = check_date.strftime("%A")
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

    # To-do items
    pending_todos = get_pending_todos()
    if pending_todos == 1:
        greeting += " You've got 1 thing on your to-do list."
    elif pending_todos > 1:
        greeting += f" You've got {pending_todos} things on your to-do list."

    # News briefing — fetch in background and append if successful
    try:
        news = fetch_news_briefing(limit_each=1)
        if news:
            greeting += f" {news}"
    except Exception:
        pass

    # The signature ending - warm but cheeky
    greeting += " Alright, let's make today a good one."

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
