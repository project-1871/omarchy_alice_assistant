"""Alarms and timers tool."""
import subprocess
import os
import sys
import re
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool


class AlarmsTool(Tool):
    """Set alarms, timers, and reminders."""

    name = "alarms"
    description = "Set alarms, timers, and reminders"
    triggers = [
        "set alarm", "alarm for", "wake me", "remind me in",
        "set timer", "timer for", "countdown",
        "remind me at", "reminder for"
    ]

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # Timer (duration-based)
        if any(t in query_lower for t in ["timer", "remind me in", "countdown"]):
            return self._set_timer(query)

        # Alarm (time-based)
        if any(t in query_lower for t in ["alarm", "wake me", "remind me at"]):
            return self._set_alarm(query)

        return "I can set alarms (for a specific time) or timers (for a duration). Which do you need?"

    def _parse_duration(self, query: str) -> int | None:
        """Parse duration from query, return seconds."""
        patterns = [
            (r'(\d+)\s*hour', 3600),
            (r'(\d+)\s*minute', 60),
            (r'(\d+)\s*min', 60),
            (r'(\d+)\s*second', 1),
            (r'(\d+)\s*sec', 1),
        ]

        total_seconds = 0
        found = False

        for pattern, multiplier in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                total_seconds += int(match.group(1)) * multiplier
                found = True

        return total_seconds if found else None

    def _parse_time(self, query: str) -> datetime | None:
        """Parse time from query."""
        # Try various time formats
        patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm)?',
            r'(\d{1,2})\s*(am|pm)',
        ]

        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                groups = match.groups()

                if len(groups) == 3:
                    hour, minute, ampm = groups
                    hour = int(hour)
                    minute = int(minute)
                elif len(groups) == 2:
                    hour = int(groups[0])
                    minute = 0
                    ampm = groups[1]
                else:
                    continue

                # Handle AM/PM
                if ampm:
                    ampm = ampm.lower()
                    if ampm == 'pm' and hour != 12:
                        hour += 12
                    elif ampm == 'am' and hour == 12:
                        hour = 0

                now = datetime.now()
                alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # If time has passed today, set for tomorrow
                if alarm_time <= now:
                    alarm_time += timedelta(days=1)

                return alarm_time

        return None

    def _set_timer(self, query: str) -> str:
        """Set a countdown timer."""
        seconds = self._parse_duration(query)
        if not seconds:
            return "How long should the timer be? (e.g., '5 minutes', '1 hour')"

        # Extract message/reason if any
        message = "Timer done!"

        # Use systemd-run for the timer (more reliable than at)
        try:
            # Create a notification command
            notify_cmd = f'notify-send "Alice Timer" "{message}" && paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga'

            subprocess.run([
                'systemd-run', '--user', '--on-active=' + str(seconds),
                'bash', '-c', notify_cmd
            ], capture_output=True, check=True)

            # Format duration for response
            if seconds >= 3600:
                duration_str = f"{seconds // 3600} hour(s) {(seconds % 3600) // 60} minute(s)"
            elif seconds >= 60:
                duration_str = f"{seconds // 60} minute(s)"
            else:
                duration_str = f"{seconds} second(s)"

            return f"Timer set for {duration_str}. I'll notify you when it's done."

        except subprocess.CalledProcessError:
            # Fallback: use at command
            try:
                at_time = datetime.now() + timedelta(seconds=seconds)
                at_str = at_time.strftime("%H:%M")
                notify_cmd = f'notify-send "Alice Timer" "{message}"'

                proc = subprocess.Popen(
                    ['at', at_str],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                proc.communicate(notify_cmd.encode())

                return f"Timer set. You'll be notified at {at_str}."
            except Exception:
                return "Couldn't set timer. Is 'at' or systemd available?"

    def _set_alarm(self, query: str) -> str:
        """Set an alarm for a specific time."""
        alarm_time = self._parse_time(query)
        if not alarm_time:
            return "What time should I set the alarm for? (e.g., '7:30 am', '14:00')"

        message = "Wake up! Time to get shit done."

        try:
            # Calculate seconds until alarm
            seconds_until = int((alarm_time - datetime.now()).total_seconds())

            # Use systemd-run
            notify_cmd = f'notify-send "Alice Alarm" "{message}" && paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga'

            subprocess.run([
                'systemd-run', '--user', '--on-active=' + str(seconds_until),
                'bash', '-c', notify_cmd
            ], capture_output=True, check=True)

            time_str = alarm_time.strftime("%I:%M %p")
            return f"Alarm set for {time_str}. I'll wake you."

        except subprocess.CalledProcessError:
            return "Couldn't set alarm. Check systemd user services."
