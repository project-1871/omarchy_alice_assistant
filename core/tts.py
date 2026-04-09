"""Kokoro ONNX TTS — expressive American female voice (af_heart) + Cherry Honey FFmpeg FX."""
import tempfile
import os
import re
import queue
import subprocess
import threading
import sys
import numpy as np
sys.path.insert(0, '..')
import config
from core.pronunciation import preprocess


class TTS:
    """Text-to-speech using Kokoro ONNX (kokoro-onnx package)."""

    def __init__(self):
        self._kokoro = None

    def _get_kokoro(self):
        if self._kokoro is None:
            from kokoro_onnx import Kokoro
            self._kokoro = Kokoro(config.KOKORO_MODEL, config.KOKORO_VOICES)
        return self._kokoro

    def _apply_fx(self, in_path: str, out_path: str):
        """Run FFmpeg Cherry Honey FX chain."""
        subprocess.run(
            ['ffmpeg', '-y', '-i', in_path, '-af', config.KITTEN_FX, out_path],
            capture_output=True
        )

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences for pipelined generation."""
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
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

    def _generate_chunk(self, text: str) -> str | None:
        """Generate audio for one sentence. Returns fx_path or None."""
        try:
            kokoro = self._get_kokoro()
            samples, sample_rate = kokoro.create(
                text,
                voice=config.KOKORO_VOICE,
                speed=config.KOKORO_SPEED,
                lang=config.KOKORO_LANG,
            )

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                raw_path = f.name
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                fx_path = f.name

            import soundfile as sf
            sf.write(raw_path, samples, sample_rate)
            self._apply_fx(raw_path, fx_path)
            os.remove(raw_path)
            return fx_path
        except Exception:
            import traceback
            traceback.print_exc()
            return None

    def _play_file(self, fx_path: str):
        """Play processed WAV via paplay."""
        try:
            import soundfile as sf
            audio, _ = sf.read(fx_path, dtype='int16')
            paplay = subprocess.Popen(
                ['paplay', f'--device={config.AUDIO_SINK}', '--raw',
                 '--channels=1', f'--rate={config.KITTEN_SAMPLE_RATE}'],
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
        return self.speak_raw(text)

    def speak_raw(self, text: str) -> bool:
        """Speak text with pipelined sentence generation+playback."""
        try:
            text = preprocess(text)
            sentences = self._split_sentences(text)

            if len(sentences) == 1:
                fx_path = self._generate_chunk(sentences[0])
                if fx_path:
                    self._play_file(fx_path)
                return True

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
            import traceback
            traceback.print_exc()
            return False
