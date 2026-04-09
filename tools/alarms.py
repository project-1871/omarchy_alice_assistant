"""Alarms and timers tool — with persistence via alarm_log.json."""
import subprocess
import os
import sys
import re
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool


class AlarmsTool(Tool):
    """Set alarms, timers, and reminders. Persists across restarts."""

    name = "alarms"
    description = "Set alarms, timers, and reminders"
    triggers = [
        "set alarm", "alarm for", "wake me", "remind me in",
        "set timer", "timer for", "countdown",
        "remind me at", "reminder for",
        "what alarms", "list alarms", "list timers", "any timers",
        "any alarms", "show alarms", "show timers",
        "cancel alarm", "cancel timer", "stop alarm", "stop timer",
        "delete alarm", "delete timer",
    ]

    def __init__(self):
        # Lazy-load Memory to avoid circular import issues
        self._memory = None

    @property
    def memory(self):
        if self._memory is None:
            from core.memory import Memory
            self._memory = Memory()
        return self._memory

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # List active alarms/timers
        if any(t in query_lower for t in ["what alarms", "list alarms", "list timers",
                                           "any timers", "any alarms", "show alarms", "show timers"]):
            return self._list_alarms()

        # Cancel an alarm/timer
        if any(t in query_lower for t in ["cancel alarm", "cancel timer", "stop alarm",
                                           "stop timer", "delete alarm", "delete timer"]):
            return self._cancel_alarm(query)

        # Timer (duration-based)
        if any(t in query_lower for t in ["timer", "remind me in", "countdown"]):
            return self._set_timer(query)

        # Alarm (time-based)
        if any(t in query_lower for t in ["alarm", "wake me", "remind me at"]):
            return self._set_alarm(query)

        return "I can set alarms (for a specific time) or timers (for a duration). Which do you need?"

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse_duration(self, query: str) -> int | None:
        """Parse duration from query, return total seconds.

        Uses word-boundary style to avoid double-counting (e.g. 'minute' and 'min'
        both matching '2 minutes').
        """
        patterns = [
            (r'(\d+)\s*hours?', 3600),
            (r'(\d+)\s*minutes?', 60),
            (r'(\d+)\s*mins?\b', 60),
            (r'(\d+)\s*seconds?', 1),
            (r'(\d+)\s*secs?\b', 1),
        ]
        total_seconds = 0
        found = False
        already_matched_positions = set()
        for pattern, multiplier in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # Skip if this number position was already counted
                if match.start(1) in already_matched_positions:
                    continue
                already_matched_positions.add(match.start(1))
                total_seconds += int(match.group(1)) * multiplier
                found = True
        return total_seconds if found else None

    def _parse_time(self, query: str) -> datetime | None:
        """Parse time from query, return datetime (today or tomorrow if past)."""
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
                if ampm:
                    ampm = ampm.lower()
                    if ampm == 'pm' and hour != 12:
                        hour += 12
                    elif ampm == 'am' and hour == 12:
                        hour = 0
                now = datetime.now()
                alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if alarm_time <= now:
                    alarm_time += timedelta(days=1)
                return alarm_time
        return None

    # ── systemd helpers ───────────────────────────────────────────────────────

    def _run_systemd(self, seconds: int, notify_cmd: str) -> str | None:
        """Run systemd-run --user --on-active=N and return the unit name, or None on failure."""
        result = subprocess.run(
            ['systemd-run', '--user', f'--on-active={seconds}', 'bash', '-c', notify_cmd],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return None
        # stderr contains: "Running as unit: run-XXXXXXXX.service"
        match = re.search(r'Running as unit:\s*(\S+)', result.stderr)
        return match.group(1) if match else 'unknown'

    def _stop_unit(self, unit: str) -> bool:
        """Stop a systemd user timer/service unit. Returns True on success."""
        # Try stopping both the .service and .timer variants
        for suffix in ('', '.timer', '.service'):
            name = unit if unit.endswith(('.service', '.timer')) else unit + suffix
            r = subprocess.run(
                ['systemctl', '--user', 'stop', name],
                capture_output=True
            )
            if r.returncode == 0:
                return True
        return False

    # ── Core methods ──────────────────────────────────────────────────────────

    def _set_timer(self, query: str) -> str:
        """Set a countdown timer and log it."""
        seconds = self._parse_duration(query)
        if not seconds:
            return "How long should the timer be? (e.g., '5 minutes', '1 hour')"

        message = "Timer done!"
        scheduled_for = datetime.now() + timedelta(seconds=seconds)

        # Pre-compute the next alarm ID so we can embed it in the fire-marker command
        next_id = len(self.memory.alarms['alarms']) + 1
        marker_cmd = f'echo {next_id} > /tmp/alice_alarm_fired_{next_id}'
        notify_cmd = (
            f'notify-send "Alice Timer" "{message}" && '
            f'paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga 2>/dev/null; '
            f'{marker_cmd}'
        )

        unit = self._run_systemd(seconds, notify_cmd)
        if unit is None:
            return "Couldn't set timer — systemd-run failed."

        alarm_id = self.memory.add_alarm('timer', scheduled_for, seconds, message, unit)

        if seconds >= 3600:
            duration_str = f"{seconds // 3600}h {(seconds % 3600) // 60}m"
        elif seconds >= 60:
            duration_str = f"{seconds // 60} minute(s)"
        else:
            duration_str = f"{seconds} second(s)"

        return f"Timer set for {duration_str}. I'll notify you when it's done. (alarm #{alarm_id})"

    def _set_alarm(self, query: str) -> str:
        """Set an alarm for a specific time and log it."""
        alarm_time = self._parse_time(query)
        if not alarm_time:
            return "What time should I set the alarm for? (e.g., '7:30 am', '14:00')"

        message = "Wake up! Time to get shit done."
        seconds_until = int((alarm_time - datetime.now()).total_seconds())

        next_id = len(self.memory.alarms['alarms']) + 1
        marker_cmd = f'echo {next_id} > /tmp/alice_alarm_fired_{next_id}'
        notify_cmd = (
            f'notify-send "Alice Alarm" "{message}" && '
            f'paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga 2>/dev/null; '
            f'{marker_cmd}'
        )

        unit = self._run_systemd(seconds_until, notify_cmd)
        if unit is None:
            return "Couldn't set alarm — systemd-run failed."

        alarm_id = self.memory.add_alarm('alarm', alarm_time, None, message, unit)
        time_str = alarm_time.strftime("%I:%M %p")
        day_str = " tomorrow" if alarm_time.date() > datetime.now().date() else ""
        return f"Alarm set for {time_str}{day_str}. I'll wake you. (alarm #{alarm_id})"

    def _list_alarms(self) -> str:
        """List active alarms and timers."""
        active = self.memory.get_active_alarms()
        if not active:
            return "No active alarms or timers."

        now = datetime.now()
        lines = []
        for a in active:
            try:
                scheduled = datetime.fromisoformat(a['scheduled_for'])
                remaining = scheduled - now
                total_secs = int(remaining.total_seconds())
                if total_secs <= 0:
                    time_left = "firing soon"
                elif total_secs < 60:
                    time_left = f"{total_secs}s left"
                elif total_secs < 3600:
                    time_left = f"{total_secs // 60}m left"
                else:
                    time_left = f"{total_secs // 3600}h {(total_secs % 3600) // 60}m left"
                label = a['type'].capitalize()
                lines.append(f"#{a['id']} {label}: {a['message']} — {time_left}")
            except Exception:
                lines.append(f"#{a['id']} {a['type']}: {a['message']}")

        return "Active alarms:\n" + "\n".join(lines)

    def _cancel_alarm(self, query: str) -> str:
        """Cancel an alarm by ID or cancel the most recent one."""
        active = self.memory.get_active_alarms()
        if not active:
            return "No active alarms or timers to cancel."

        # Try to parse an ID from the query
        id_match = re.search(r'#?(\d+)', query)
        if id_match:
            target_id = int(id_match.group(1))
            target = next((a for a in active if a['id'] == target_id), None)
            if not target:
                return f"No active alarm with ID #{target_id}."
        else:
            # Cancel the most recent active alarm
            target = active[-1]

        # Stop the systemd unit
        unit = target.get('systemd_unit')
        if unit and unit != 'unknown':
            self._stop_unit(unit)

        self.memory.cancel_alarm(target['id'])
        label = target['type']
        return f"Cancelled {label} #{target['id']} ({target['message']})."
