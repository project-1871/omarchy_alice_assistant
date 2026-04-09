"""Voice-only fullscreen mode for Alice."""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')

from gi.repository import Gtk, Gdk, GLib, Pango
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .recorder import AudioRecorder

# States
IDLE      = 'idle'
RECORDING = 'recording'
THINKING  = 'thinking'
SPEAKING  = 'speaking'

# Dot unicode glyph
DOT = '●'


class VoiceFullscreenWindow(Gtk.Window):
    """Fullscreen voice-only interface — press SPACE to talk, ESC to close."""

    def __init__(self, alice, parent=None):
        super().__init__(title="Alice")
        self.alice = alice
        self.recorder = AudioRecorder()
        self._state = IDLE
        self._pulse_on = False
        self._pulse_timer = None
        self._response_clear_timer = None

        if parent:
            self.set_transient_for(parent)

        self._load_css()
        self._build_ui()
        self._setup_keys()
        self.fullscreen()
        self.set_decorated(False)

    # ── CSS ───────────────────────────────────────────────────────────────────

    def _load_css(self):
        css = b"""
        .voice-fullscreen { background-color: #0a0a0a; }

        .voice-alice-title {
            color: #cc2222;
            font-size: 28px;
            font-weight: bold;
            letter-spacing: 8px;
        }

        .voice-dot-idle        { color: #333333; font-size: 72px; }
        .voice-dot-idle-pulse  { color: #444444; font-size: 78px; }

        .voice-dot-recording        { color: #dc2626; font-size: 80px; }
        .voice-dot-recording-pulse  { color: #ef4444; font-size: 92px; }

        .voice-dot-thinking        { color: #2563eb; font-size: 72px; }
        .voice-dot-thinking-pulse  { color: #60a5fa; font-size: 82px; }

        .voice-dot-speaking        { color: #16a34a; font-size: 72px; }
        .voice-dot-speaking-pulse  { color: #22c55e; font-size: 82px; }

        .voice-status {
            color: #555555;
            font-size: 16px;
            letter-spacing: 3px;
        }
        .voice-status-recording { color: #dc2626; font-size: 16px; letter-spacing: 3px; }
        .voice-status-thinking  { color: #3b82f6; font-size: 16px; letter-spacing: 3px; }
        .voice-status-speaking  { color: #16a34a; font-size: 16px; letter-spacing: 3px; }

        .voice-response {
            color: #d0d0d0;
            font-size: 20px;
        }

        .voice-hint {
            color: #303030;
            font-size: 13px;
            letter-spacing: 1px;
        }

        .voice-exit-btn {
            background-color: transparent;
            color: #333333;
            border: 1px solid #333333;
            border-radius: 4px;
            padding: 4px 12px;
            font-size: 12px;
        }
        .voice-exit-btn:hover { color: #888888; border-color: #888888; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10
        )

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.add_css_class('voice-fullscreen')
        root.set_hexpand(True)
        root.set_vexpand(True)
        self.set_child(root)

        # Exit button (top-right corner)
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        top_bar.set_margin_top(20)
        top_bar.set_margin_end(24)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_bar.append(spacer)
        exit_btn = Gtk.Button(label="✕ ESC")
        exit_btn.add_css_class('voice-exit-btn')
        exit_btn.connect('clicked', lambda _: self.close())
        top_bar.append(exit_btn)
        root.append(top_bar)

        # Centre content
        centre = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=28)
        centre.set_halign(Gtk.Align.CENTER)
        centre.set_valign(Gtk.Align.CENTER)
        centre.set_vexpand(True)

        # Alice title
        title = Gtk.Label(label="A L I C E")
        title.add_css_class('voice-alice-title')
        centre.append(title)

        # Pulsing dot (click = record)
        self.dot_label = Gtk.Label(label=DOT)
        self.dot_label.add_css_class('voice-dot-idle')
        self.dot_label.set_cursor(Gdk.Cursor.new_from_name('pointer'))
        click = Gtk.GestureClick()
        click.connect('released', self._on_dot_click)
        self.dot_label.add_controller(click)
        centre.append(self.dot_label)

        # Status text
        self.status_label = Gtk.Label(label="PRESS SPACE")
        self.status_label.add_css_class('voice-status')
        centre.append(self.status_label)

        # Response text
        self.response_label = Gtk.Label(label="")
        self.response_label.add_css_class('voice-response')
        self.response_label.set_wrap(True)
        self.response_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.response_label.set_justify(Gtk.Justification.CENTER)
        self.response_label.set_max_width_chars(60)
        self.response_label.set_margin_top(8)
        centre.append(self.response_label)

        root.append(centre)

        # Bottom hint
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bottom.set_margin_bottom(24)
        hint_spacer = Gtk.Box()
        hint_spacer.set_hexpand(True)
        hint = Gtk.Label(label="SPACE  hold to talk     ESC  exit")
        hint.add_css_class('voice-hint')
        hint_spacer2 = Gtk.Box()
        hint_spacer2.set_hexpand(True)
        bottom.append(hint_spacer)
        bottom.append(hint)
        bottom.append(hint_spacer2)
        root.append(bottom)

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def _setup_keys(self):
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect('key-pressed',  self._on_key_pressed)
        key_ctrl.connect('key-released', self._on_key_released)
        self.add_controller(key_ctrl)

    def _on_key_pressed(self, ctrl, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if keyval == Gdk.KEY_space and self._state == IDLE:
            self._start_recording()
            return True
        return False

    def _on_key_released(self, ctrl, keyval, keycode, state):
        if keyval == Gdk.KEY_space and self._state == RECORDING:
            self._stop_and_process()
            return True
        return False

    def _on_dot_click(self, gesture, n_press, x, y):
        if self._state == IDLE:
            self._start_recording()
        elif self._state == RECORDING:
            self._stop_and_process()

    # ── State machine ─────────────────────────────────────────────────────────

    def _set_state(self, state: str):
        self._state = state
        self._stop_pulse()

        if state == IDLE:
            self._set_dot('voice-dot-idle', 'voice-dot-idle-pulse')
            self.status_label.set_text("PRESS SPACE")
            self.status_label.set_css_classes(['voice-status'])
        elif state == RECORDING:
            self._set_dot('voice-dot-recording', 'voice-dot-recording-pulse')
            self.status_label.set_text("LISTENING")
            self.status_label.set_css_classes(['voice-status-recording'])
        elif state == THINKING:
            self._set_dot('voice-dot-thinking', 'voice-dot-thinking-pulse')
            self.status_label.set_text("THINKING")
            self.status_label.set_css_classes(['voice-status-thinking'])
        elif state == SPEAKING:
            self._set_dot('voice-dot-speaking', 'voice-dot-speaking-pulse')
            self.status_label.set_text("SPEAKING")
            self.status_label.set_css_classes(['voice-status-speaking'])

        self._start_pulse(state)

    def _set_dot(self, base_cls: str, pulse_cls: str):
        self._dot_base = base_cls
        self._dot_pulse = pulse_cls
        self._pulse_on = False
        self.dot_label.set_css_classes([base_cls])

    def _start_pulse(self, state: str):
        interval = 600 if state == RECORDING else 900
        self._pulse_timer = GLib.timeout_add(interval, self._tick_pulse)

    def _stop_pulse(self):
        if self._pulse_timer:
            GLib.source_remove(self._pulse_timer)
            self._pulse_timer = None

    def _tick_pulse(self):
        if self._state == IDLE:
            # Very subtle idle breathe
            self._pulse_on = not self._pulse_on
            cls = self._dot_pulse if self._pulse_on else self._dot_base
            self.dot_label.set_css_classes([cls])
        elif self._state in (RECORDING, THINKING, SPEAKING):
            self._pulse_on = not self._pulse_on
            cls = self._dot_pulse if self._pulse_on else self._dot_base
            self.dot_label.set_css_classes([cls])
        return True  # keep firing

    # ── Recording & processing ────────────────────────────────────────────────

    def _start_recording(self):
        self._set_state(RECORDING)
        self.recorder.start()

    def _stop_and_process(self):
        audio_file = self.recorder.stop()
        if not audio_file:
            self._set_state(IDLE)
            return

        self._set_state(THINKING)

        import threading
        def _worker():
            try:
                # Transcribe
                text = self.alice.transcribe(audio_file)
                if not text or not text.strip():
                    GLib.idle_add(self._show_response, "(didn't catch that)", go_idle=True)
                    return

                GLib.idle_add(self._show_transcript, text)

                # Process
                result = self.alice.process(text)
                response = result.get('response', '')

                # Speak
                GLib.idle_add(self._show_response, response)
                self.alice.speak(response)
                GLib.idle_add(self._set_state, IDLE)

            except Exception as e:
                GLib.idle_add(self._show_response, f"Error: {e}", go_idle=True)
            finally:
                try:
                    import os as _os
                    if audio_file and _os.path.exists(audio_file):
                        _os.remove(audio_file)
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _show_transcript(self, text: str):
        """Show what was heard while Alice is thinking."""
        short = text[:80] + ('...' if len(text) > 80 else '')
        self.status_label.set_text(f'"{short}"')
        self.status_label.set_css_classes(['voice-status-thinking'])

    def _show_response(self, text: str, go_idle: bool = False):
        """Display response text and optionally return to idle."""
        self._set_state(SPEAKING)
        # Trim for display — TTS handles the full text
        display = text[:280] + ('...' if len(text) > 280 else '')
        self.response_label.set_text(display)
        if go_idle:
            GLib.timeout_add(2000, lambda: (self._set_state(IDLE), False)[1])
