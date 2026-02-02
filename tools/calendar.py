"""Calendar tool for calcurse integration."""
import subprocess
import os
import sys
import re
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool


class CalendarTool(Tool):
    """Manage calendar events via calcurse."""

    name = "calendar"
    description = "Add and view calendar events"
    triggers = [
        "add to calendar", "put on calendar", "calendar event",
        "schedule", "add event", "add appointment",
        "remind me on", "reminder on", "remind me about",
        "what's on my calendar", "show calendar", "calendar for",
        "what do i have", "any events", "my schedule"
    ]

    def __init__(self):
        self.calcurse_dir = Path.home() / ".local/share/calcurse"
        self.apts_file = self.calcurse_dir / "apts"
        self._ensure_calcurse_dir()

    def _ensure_calcurse_dir(self):
        """Ensure calcurse directory exists."""
        self.calcurse_dir.mkdir(parents=True, exist_ok=True)
        if not self.apts_file.exists():
            self.apts_file.touch()

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # Check if listing/viewing events (only if clearly a query, not an add request)
        add_triggers = ["add", "put", "schedule", "set", "create", "remind"]
        is_add_request = any(query_lower.startswith(t) for t in add_triggers)

        if not is_add_request and any(t in query_lower for t in ["what's on", "show calendar",
                                           "what do i have", "any events", "my schedule", "calendar for"]):
            return self._list_events(query)

        # Otherwise, add event
        return self._add_event(query)

    def _parse_date(self, query: str) -> datetime | None:
        """Parse date from natural language."""
        query_lower = query.lower()
        today = datetime.now()

        # Relative days
        if "today" in query_lower:
            return today
        if "tomorrow" in query_lower:
            return today + timedelta(days=1)
        if "day after tomorrow" in query_lower:
            return today + timedelta(days=2)

        # Days of week
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(days):
            if day in query_lower:
                current_day = today.weekday()
                days_ahead = i - current_day
                if days_ahead <= 0:
                    days_ahead += 7
                return today + timedelta(days=days_ahead)

        # Next week
        if "next week" in query_lower:
            return today + timedelta(days=7)

        # Specific date patterns
        patterns = [
            # February 10th, Feb 10, etc.
            (r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
             r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|'
             r'dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?', 'month_day'),
            # 10th of February, 10 February
            (r'(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|'
             r'apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|'
             r'nov(?:ember)?|dec(?:ember)?)(?:\s*,?\s*(\d{4}))?', 'day_month'),
            # MM/DD/YYYY or MM-DD-YYYY
            (r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', 'numeric'),
        ]

        months = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
            'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
            'aug': 8, 'august': 8, 'sep': 9, 'september': 9, 'oct': 10, 'october': 10,
            'nov': 11, 'november': 11, 'dec': 12, 'december': 12
        }

        for pattern, ptype in patterns:
            match = re.search(pattern, query_lower)
            if match:
                try:
                    if ptype == 'month_day':
                        month = months[match.group(1)[:3]]
                        day = int(match.group(2))
                        year = int(match.group(3)) if match.group(3) else today.year
                    elif ptype == 'day_month':
                        day = int(match.group(1))
                        month = months[match.group(2)[:3]]
                        year = int(match.group(3)) if match.group(3) else today.year
                    elif ptype == 'numeric':
                        month = int(match.group(1))
                        day = int(match.group(2))
                        year = int(match.group(3)) if match.group(3) else today.year
                        if year < 100:
                            year += 2000

                    result = today.replace(month=month, day=day, year=year,
                                          hour=0, minute=0, second=0, microsecond=0)
                    # If date is in the past, assume next year
                    if result < today:
                        result = result.replace(year=result.year + 1)
                    return result
                except (ValueError, KeyError):
                    continue

        return None

    def _parse_time(self, query: str) -> tuple[int, int] | None:
        """Parse time from query, returns (hour, minute)."""
        query_lower = query.lower()

        # Handle special times
        if 'noon' in query_lower or 'midday' in query_lower:
            return (12, 0)
        if 'midnight' in query_lower:
            return (0, 0)

        patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm)?',
            r'(\d{1,2})\s*(am|pm)',
            r'at\s+(\d{1,2})\s*(am|pm)?',
        ]

        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                groups = match.groups()
                hour = int(groups[0])
                minute = int(groups[1]) if len(groups) > 1 and groups[1] and groups[1].isdigit() else 0
                ampm = groups[-1] if groups[-1] and groups[-1].lower() in ('am', 'pm') else None

                if ampm:
                    ampm = ampm.lower()
                    if ampm == 'pm' and hour != 12:
                        hour += 12
                    elif ampm == 'am' and hour == 12:
                        hour = 0

                return (hour, minute)

        return None

    def _extract_event_description(self, query: str) -> str:
        """Extract event description from query."""
        # Remove common trigger phrases
        desc = query
        remove_patterns = [
            r'^(add|put|schedule|set|create)\s+(a\s+)?(calendar\s+)?(event|appointment|reminder)?\s*(for|about|on|to)?\s*',
            r'^remind\s+me\s+(on|about|to)\s*',
            r'\s*(on|for|at|to)\s+(my\s+)?calendar',
            r'\s+(on|for)\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d+.*$',
            r'\s+(on|for)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday).*$',
            r'\s+(on|for)?\s*(today|tomorrow|next\s+week).*$',
            r'\s+at\s+\d{1,2}(:\d{2})?\s*(am|pm)?.*$',
            r'\s+at\s+(noon|midday|midnight).*$',
            r'\s+\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?.*$',
        ]

        for pattern in remove_patterns:
            desc = re.sub(pattern, '', desc, flags=re.IGNORECASE)

        # Clean up
        desc = desc.strip()
        desc = re.sub(r'\s+', ' ', desc)

        # Capitalize first letter
        if desc:
            desc = desc[0].upper() + desc[1:]

        return desc if desc else "Event"

    def _add_event(self, query: str) -> str:
        """Add an event to calcurse."""
        date = self._parse_date(query)
        if not date:
            return "I couldn't understand the date. Try something like 'February 10th' or 'next Tuesday'."

        time = self._parse_time(query)
        description = self._extract_event_description(query)

        # Format for calcurse
        date_str = date.strftime("%m/%d/%Y")

        if time:
            hour, minute = time
            start_time = f"{hour:02d}:{minute:02d}"
            # Default 1 hour duration
            end_hour = hour + 1
            end_time = f"{end_hour:02d}:{minute:02d}"
            entry = f"{date_str} @ {start_time} -> {date_str} @ {end_time} |{description}\n"
            time_display = f" at {hour:02d}:{minute:02d}"
        else:
            # All-day event
            entry = f"{date_str} [1] |{description}\n"
            time_display = ""

        # Append to calcurse appointments file
        try:
            with open(self.apts_file, 'a') as f:
                f.write(entry)

            date_display = date.strftime("%A, %B %d")
            return f"Added to calendar: \"{description}\" on {date_display}{time_display}"

        except Exception as e:
            return f"Couldn't add event: {e}"

    def _list_events(self, query: str) -> str:
        """List events from calcurse."""
        # Determine date range
        date = self._parse_date(query)
        if not date:
            date = datetime.now()

        # Read directly from file (more reliable)
        return self._list_events_from_file(date)

    def _list_events_from_file(self, target_date: datetime) -> str:
        """List events by reading calcurse file directly."""
        if not self.apts_file.exists():
            return "No events scheduled."

        events = []
        target_str = target_date.strftime("%m/%d/%Y")

        try:
            with open(self.apts_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Check if event is on target date
                    if line.startswith(target_str):
                        # Extract description
                        if '|' in line:
                            desc = line.split('|', 1)[1]
                            # Extract time if present
                            time_match = re.search(r'@ (\d{2}:\d{2})', line)
                            if time_match:
                                events.append(f"{time_match.group(1)} - {desc}")
                            else:
                                events.append(desc)

            if events:
                date_display = target_date.strftime("%A, %B %d")
                return f"Events on {date_display}:\n" + "\n".join(events)
            else:
                return "No events scheduled for that day."

        except Exception as e:
            return f"Couldn't read calendar: {e}"
