"""Whisper STT integration."""
import sys
import time
import os
import wave
import logging
sys.path.insert(0, '..')
import config

# STT performance log — append-only, one line per transcription
_log = logging.getLogger('stt_perf')
_log.setLevel(logging.DEBUG)
_fh = logging.FileHandler(os.path.join(config.PROJECT_DIR, 'stt_perf.log'))
_fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
_log.addHandler(_fh)


def _audio_duration(path: str) -> float:
    """Return duration of a WAV file in seconds."""
    try:
        with wave.open(path, 'r') as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 0.0


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
                compute_type='int8',
                cpu_threads=config.WHISPER_THREADS,
            )

    def transcribe(self, audio_file: str) -> str:
        """Transcribe an audio file."""
        self._load_model()
        audio_dur = _audio_duration(audio_file)
        t0 = time.perf_counter()
        segments, info = self.model.transcribe(
            audio_file,
            beam_size=config.WHISPER_BEAM_SIZE,
            vad_filter=True,
        )
        text = ''.join(segment.text for segment in segments).strip()
        elapsed = time.perf_counter() - t0
        rtf = elapsed / audio_dur if audio_dur > 0 else 0
        _log.info(
            f'audio={audio_dur:.2f}s | infer={elapsed:.2f}s | RTF={rtf:.2f} | '
            f'lang={info.language}({info.language_probability:.0%}) | '
            f'words={len(text.split())} | model={self.model_name}/{self.device}'
        )
        return text

    def preload(self):
        """Preload the model for faster first transcription."""
        self._load_model()
