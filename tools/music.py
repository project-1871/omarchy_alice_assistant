"""Music control tool."""
import subprocess
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool


class MusicTool(Tool):
    """Control music playback."""

    name = "music"
    description = "Control music playback and search YouTube"
    triggers = [
        "play music", "play some music", "put on music",
        "pause", "stop music", "resume",
        "next song", "skip", "previous", "next track",
        "volume up", "volume down", "louder", "quieter"
    ]

    def __init__(self):
        self._awaiting_artist = False

    def can_handle(self, query: str) -> bool:
        """Also handle the follow-up artist query after 'play music'."""
        if self._awaiting_artist:
            return True
        return super().can_handle(query)

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # Step 2: artist name received — search and play
        if self._awaiting_artist:
            self._awaiting_artist = False
            return self._search_youtube(query.strip())

        # Play music — open YouTube and ask what to play
        if any(t in query_lower for t in ["play music", "play some music", "put on music"]):
            return self._open_youtube()

        # Pause/Stop
        if any(t in query_lower for t in ["pause", "stop music"]):
            return self._pause()

        # Resume
        if "resume" in query_lower:
            return self._resume()

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

        return "I can play music on YouTube, pause, skip, or adjust volume. What do you need?"

    def _open_youtube(self) -> str:
        """Open YouTube web app and ask what artist to play."""
        try:
            subprocess.Popen(
                ['omarchy-launch-webapp', 'https://youtube.com'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        except Exception:
            pass
        self._awaiting_artist = True
        return "YouTube's open. What do you want to listen to?"

    def _search_youtube(self, artist: str) -> str:
        """Find the first YouTube mix for the artist and open it."""
        search_query = f"{artist} mix"
        url = self._find_first_result(search_query)
        if url:
            try:
                subprocess.Popen(
                    ['omarchy-launch-webapp', url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                return f"Playing {artist} mix."
            except Exception as e:
                return f"Found it but couldn't open: {e}"

        # Fallback: open search page
        fallback = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_query)}"
        try:
            subprocess.Popen(
                ['omarchy-launch-webapp', fallback],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        except Exception:
            pass
        return f"Opened YouTube search for {artist} mix."

    def _find_first_result(self, query: str) -> str | None:
        """Use yt-dlp to get the URL of the first YouTube result."""
        try:
            result = subprocess.run(
                ['yt-dlp', '--no-playlist', '--print', 'webpage_url',
                 f'ytsearch1:{query}'],
                capture_output=True,
                text=True,
                timeout=15
            )
            url = result.stdout.strip()
            return url if url.startswith('http') else None
        except Exception:
            return None

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

    def _resume(self) -> str:
        """Resume playback."""
        success, _ = self._run_playerctl('play')
        if success:
            _, title = self._run_playerctl('metadata', 'title')
            _, artist = self._run_playerctl('metadata', 'artist')
            if title:
                return f"Playing: {artist} - {title}" if artist else f"Playing: {title}"
            return "Resuming."
        return "Nothing to resume."

    def _pause(self) -> str:
        """Pause playback."""
        success, _ = self._run_playerctl('pause')
        return "Paused." if success else "Nothing playing."

    def _next(self) -> str:
        """Skip to next track."""
        success, _ = self._run_playerctl('next')
        if success:
            _, title = self._run_playerctl('metadata', 'title')
            return f"Next: {title}" if title else "Skipped."
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
        subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', '+10%'])
        return "Volume up."

    def _volume_down(self) -> str:
        """Decrease volume."""
        success, _ = self._run_playerctl('volume', '0.1-')
        if success:
            _, vol = self._run_playerctl('volume')
            return f"Volume: {int(float(vol) * 100)}%"
        subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', '-10%'])
        return "Volume down."
