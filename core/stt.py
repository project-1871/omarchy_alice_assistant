"""Whisper STT integration."""
import sys
sys.path.insert(0, '..')
import config


class STT:
    """Speech-to-text using faster-whisper."""

    def __init__(self):
        self.model_name = config.WHISPER_MODEL
        self.device = config.WHISPER_DEVICE
        self.model = None

    def _load_model(self):
        """Lazy load the whisper model."""
        if self.model is None:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type='int8'
            )

    def transcribe(self, audio_file: str) -> str:
        """Transcribe an audio file."""
        self._load_model()
        segments, _ = self.model.transcribe(audio_file)
        return ''.join(segment.text for segment in segments).strip()

    def preload(self):
        """Preload the model for faster first transcription."""
        self._load_model()
