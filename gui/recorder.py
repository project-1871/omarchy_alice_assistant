"""Audio recording using PipeWire."""
import subprocess
import tempfile
import os
import signal


class AudioRecorder:
    """Records audio using PipeWire (pw-record)."""

    def __init__(self):
        self.process = None
        self.temp_file = None

    def start(self) -> str:
        """Start recording audio."""
        if self.process is not None:
            self.stop()

        fd, self.temp_file = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

        self.process = subprocess.Popen(
            ['pw-record',
             '--target=alsa_input.usb-USB_AUDIO_USB_AUDIO_20200508V100-00.mono-fallback',
             '--format=s16', '--rate=16000', '--channels=1', self.temp_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return self.temp_file

    def stop(self) -> str | None:
        """Stop recording and return the audio file path."""
        if self.process is None:
            return None

        self.process.send_signal(signal.SIGINT)
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

        self.process = None
        result = self.temp_file
        self.temp_file = None
        return result

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.process is not None

    def cleanup(self):
        """Clean up any temporary files."""
        self.stop()
        if self.temp_file and os.path.exists(self.temp_file):
            os.remove(self.temp_file)
            self.temp_file = None
