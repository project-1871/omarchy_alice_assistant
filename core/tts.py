"""KittenTTS integration - expressive female voice."""
import tempfile
import os
import re
import queue
import subprocess
import threading
import sys
sys.path.insert(0, '..')
import config
from core.pronunciation import preprocess


class TTS:
    """Text-to-speech using KittenTTS (StyleTTS2-based)."""

    def __init__(self):
        self._model = None  # Lazy-loaded on first speak()

    def _get_model(self):
        if self._model is None:
            from kittentts import KittenTTS
            self._model = KittenTTS(config.KITTEN_MODEL)
        return self._model

    def _apply_fx(self, in_path: str, out_path: str):
        """Run FFmpeg post-processing filter chain (smokey rasp effect)."""
        subprocess.run(
            ['ffmpeg', '-y', '-i', in_path, '-af', config.KITTEN_FX, out_path],
            capture_output=True
        )

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences for pipelined generation."""
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
        # Merge very short fragments with the next one
        merged = []
        buf = ''
        for part in parts:
            buf = (buf + ' ' + part).strip() if buf else part
            if len(buf) >= 40:
                merged.append(buf)
                buf = ''
        if buf:
            merged.append(buf)
        return merged if merged else [text]

    def _generate_chunk(self, text: str) -> tuple[str, str] | None:
        """Generate audio for one sentence chunk. Returns (raw_path, fx_path) or None."""
        try:
            model = self._get_model()
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                raw_path = f.name
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                fx_path = f.name
            model.generate_to_file(
                text, raw_path,
                voice=config.KITTEN_VOICE,
                speed=config.KITTEN_SPEED,
                sample_rate=config.KITTEN_SAMPLE_RATE
            )
            self._apply_fx(raw_path, fx_path)
            os.remove(raw_path)
            return fx_path
        except Exception:
            return None

    def _play_file(self, fx_path: str):
        """Play a processed WAV file via paplay."""
        try:
            import soundfile as sf
            audio, _ = sf.read(fx_path, dtype='int16')
            paplay = subprocess.Popen(
                ['paplay', '--raw', '--channels=1', f'--rate={config.KITTEN_SAMPLE_RATE}'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            paplay.stdin.write(audio.tobytes())
            paplay.stdin.close()
            paplay.wait()
        finally:
            try:
                os.remove(fx_path)
            except Exception:
                pass

    def speak(self, text: str) -> bool:
        """Speak text (blocking). Generates WAV, applies FX, plays with pw-play."""
        return self.speak_raw(text)

    def speak_raw(self, text: str) -> bool:
        """Speak text with pipelined sentence generation.

        Splits into sentences, generates the first one, starts playing it,
        and generates the next one in parallel — so audio starts immediately
        and there's no gap between sentences.
        """
        try:
            text = preprocess(text)
            sentences = self._split_sentences(text)

            if len(sentences) == 1:
                # Short text — no need to pipeline
                fx_path = self._generate_chunk(sentences[0])
                if fx_path:
                    self._play_file(fx_path)
                return True

            # Pipeline: producer generates sentences into a queue,
            # consumer plays them as they arrive.
            _DONE = object()
            audio_queue = queue.Queue(maxsize=2)

            def producer():
                for sentence in sentences:
                    fx_path = self._generate_chunk(sentence)
                    if fx_path:
                        audio_queue.put(fx_path)
                audio_queue.put(_DONE)

            prod = threading.Thread(target=producer, daemon=True)
            prod.start()

            while True:
                item = audio_queue.get()
                if item is _DONE:
                    break
                self._play_file(item)

            prod.join()
            return True
        except Exception:
            return False
