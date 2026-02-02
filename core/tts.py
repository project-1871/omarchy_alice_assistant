"""Piper TTS integration - Alba voice."""
import subprocess
import tempfile
import os
import sys
sys.path.insert(0, '..')
import config


class TTS:
    """Text-to-speech using Piper with Alba voice."""

    def __init__(self):
        self.voice_model = config.VOICE_MODEL
        self.sample_rate = config.VOICE_SAMPLE_RATE
        # Find piper in venv or system
        self.piper_bin = self._find_piper()

    def _find_piper(self) -> str:
        """Find piper executable."""
        # Check venv first
        venv_piper = os.path.join(config.PROJECT_DIR, 'venv', 'bin', 'piper')
        if os.path.exists(venv_piper):
            return venv_piper
        # Check AUR install location
        aur_piper = '/opt/piper-tts/piper'
        if os.path.exists(aur_piper):
            return aur_piper
        # Fall back to system
        return 'piper'

    def speak(self, text: str) -> bool:
        """Speak text (blocking)."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                temp_path = f.name

            result = subprocess.run(
                [self.piper_bin, '--model', self.voice_model, '--output_file', temp_path],
                input=text.encode(),
                capture_output=True,
                timeout=30
            )

            if result.returncode != 0:
                return False

            subprocess.run(['pw-play', temp_path], timeout=60)
            os.remove(temp_path)
            return True
        except Exception:
            return False

    def speak_raw(self, text: str) -> bool:
        """Speak text using raw audio output (slightly faster)."""
        try:
            piper = subprocess.Popen(
                [self.piper_bin, '--model', self.voice_model, '--output-raw'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )

            paplay = subprocess.Popen(
                ['paplay', '--raw', '--channels=1', f'--rate={self.sample_rate}'],
                stdin=piper.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            piper.stdin.write(text.encode())
            piper.stdin.close()
            paplay.wait()
            piper.wait()
            return True
        except Exception:
            return False
