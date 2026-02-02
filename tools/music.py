"""Music control tool."""
import subprocess
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool


class MusicTool(Tool):
    """Control music playback."""

    name = "music"
    description = "Control music playback"
    triggers = [
        "play music", "play some music", "put on music",
        "pause", "stop music", "resume",
        "next song", "skip", "previous", "next track",
        "volume up", "volume down", "louder", "quieter"
    ]

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # Play music
        if any(t in query_lower for t in ["play music", "play some music", "put on music"]):
            return self._play()

        # Pause/Stop
        if any(t in query_lower for t in ["pause", "stop music"]):
            return self._pause()

        # Resume
        if "resume" in query_lower:
            return self._play()

        # Next
        if any(t in query_lower for t in ["next song", "skip", "next track"]):
            return self._next()

        # Previous
        if "previous" in query_lower:
            return self._previous()

        # Volume
        if any(t in query_lower for t in ["volume up", "louder"]):
            return self._volume_up()
        if any(t in query_lower for t in ["volume down", "quieter"]):
            return self._volume_down()

        return "I can play, pause, skip tracks, or adjust volume. What would you like?"

    def _run_playerctl(self, *args) -> tuple[bool, str]:
        """Run a playerctl command."""
        try:
            result = subprocess.run(
                ['playerctl', *args],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0, result.stdout.strip()
        except FileNotFoundError:
            return False, "playerctl not installed"
        except Exception as e:
            return False, str(e)

    def _play(self) -> str:
        """Start or resume playback."""
        # First try to resume existing player
        success, _ = self._run_playerctl('play')
        if success:
            # Get what's playing
            _, title = self._run_playerctl('metadata', 'title')
            _, artist = self._run_playerctl('metadata', 'artist')
            if title:
                return f"Playing: {artist} - {title}" if artist else f"Playing: {title}"
            return "Resuming playback."

        # If no player, try to launch spotify or another player
        try:
            subprocess.Popen(
                ['spotify'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return "Launching Spotify..."
        except FileNotFoundError:
            return "No music player found. Install Spotify or another player with playerctl support."

    def _pause(self) -> str:
        """Pause playback."""
        success, _ = self._run_playerctl('pause')
        return "Paused." if success else "Nothing playing."

    def _next(self) -> str:
        """Skip to next track."""
        success, _ = self._run_playerctl('next')
        if success:
            _, title = self._run_playerctl('metadata', 'title')
            return f"Next track: {title}" if title else "Skipped."
        return "Couldn't skip."

    def _previous(self) -> str:
        """Go to previous track."""
        success, _ = self._run_playerctl('previous')
        return "Previous track." if success else "Couldn't go back."

    def _volume_up(self) -> str:
        """Increase volume."""
        success, _ = self._run_playerctl('volume', '0.1+')
        if success:
            _, vol = self._run_playerctl('volume')
            return f"Volume: {int(float(vol) * 100)}%"
        # Fallback to system volume
        subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', '+10%'])
        return "Volume up."

    def _volume_down(self) -> str:
        """Decrease volume."""
        success, _ = self._run_playerctl('volume', '0.1-')
        if success:
            _, vol = self._run_playerctl('volume')
            return f"Volume: {int(float(vol) * 100)}%"
        # Fallback to system volume
        subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', '-10%'])
        return "Volume down."
