"""Main window with chat interface, calendar, and to-do tabs."""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')

from gi.repository import Gtk, Gdk, Gio, GLib, Pango
from pathlib import Path
from datetime import datetime
import random
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alice import Alice
from .recorder import AudioRecorder
import config
from tools.teacher import get_all_lessons_with_status, get_todays_lesson, get_next_lesson

CALCURSE_DIR = Path.home() / ".local/share/calcurse"
APTS_FILE = CALCURSE_DIR / "apts"
TODO_FILE = CALCURSE_DIR / "todo"


class MainWindow(Gtk.ApplicationWindow):
    """Main application window with chat, calendar, and to-do tabs."""

    def __init__(self, app):
        super().__init__(application=app, title="Alice")
        self.app = app
        self.set_default_size(440, 520)

        # Initialize components
        self.alice = Alice()
        self.recorder = AudioRecorder()
        self.tts_enabled = True  # TTS on by default
        self._teacher_mode_active = False  # tracks teacher mode UI state

        # Activity row — single updating row showing live hermes tool/status output
        self._activity_row = None
        self._activity_label = None

        # Wire hermes activity callback so tool lines stream into the GUI in real-time
        from core.llm import HermesLLM
        if isinstance(self.alice.llm, HermesLLM):
            self.alice.llm.activity_callback = self._on_hermes_activity

        # Preload TTS + STT models in background so first speak() has no delay
        import threading
        def _preload_and_listen():
            self.alice.preload()
            self.alice.start_hermes_listener()
        threading.Thread(target=_preload_and_listen, daemon=True).start()

        # Ensure calcurse dir exists
        CALCURSE_DIR.mkdir(parents=True, exist_ok=True)
        if not APTS_FILE.exists():
            APTS_FILE.touch()
        if not TODO_FILE.exists():
            TODO_FILE.touch()

        # Setup UI
        self._setup_ui()
        self._setup_shortcuts()

        # Greeting
        greeting = random.choice(config.GREETINGS)
        self.add_message(greeting, is_user=False)
        self.alice.speak_async(greeting)

    def _setup_ui(self):
        """Build the user interface."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.add_css_class('header-bar')
        title = Gtk.Label(label="Alice")
        title.add_css_class('title-label')
        header.append(title)
        main_box.append(header)

        # Notebook (tabs)
        self.notebook = Gtk.Notebook()
        self.notebook.add_css_class('alice-notebook')
        self.notebook.set_vexpand(True)

        # Tab 1: Chat
        chat_page = self._build_chat_page()
        self.notebook.append_page(chat_page, Gtk.Label(label="Chat"))

        # Tab 2: Calendar
        calendar_page = self._build_calendar_page()
        self.notebook.append_page(calendar_page, Gtk.Label(label="Calendar"))

        # Tab 3: To Do
        todo_page = self._build_todo_page()
        self.notebook.append_page(todo_page, Gtk.Label(label="To Do"))

        # Tab 4: Messages (WhatsApp)
        messages_page = self._build_messages_page()
        self.notebook.append_page(messages_page, Gtk.Label(label="💬 Msg"))

        # Refresh data when switching tabs
        self.notebook.connect('switch-page', self._on_tab_switched)

        main_box.append(self.notebook)
        self.set_child(main_box)

    # ──────────────────────────────────────────────
    # Teacher mode
    # ──────────────────────────────────────────────

    def _on_lesson_button(self, widget):
        """Handle Start/End Lesson button click."""
        if self._teacher_mode_active:
            self._end_lesson()
        else:
            self._show_lesson_selector()

    def _on_profile_toggle(self, widget):
        """Toggle between work and chill profile."""
        new_profile = 'work' if self.alice.active_profile == 'chill' else 'chill'
        msg = self.alice.switch_profile(new_profile)
        self.add_message(msg, is_system=True)

    def _sync_profile_button(self, profile_name: str):
        """Update profile button label and style to match current profile."""
        import config as _cfg
        from gi.repository import GLib
        profile = _cfg.PROFILES.get(profile_name, _cfg.PROFILES['chill'])

        def _update():
            self.profile_button.set_label(profile['display'])
            if profile_name == 'work':
                self.profile_button.remove_css_class('toolbar-button')
                self.profile_button.add_css_class('profile-button-work')
            else:
                self.profile_button.remove_css_class('profile-button-work')
                self.profile_button.add_css_class('toolbar-button')

        GLib.idle_add(_update)

    def _on_uncensored_toggle(self, widget):
        """Toggle between Claude (hermes) and dolphin-llama3 (uncensored local)."""
        try:
            if self.alice.is_uncensored_mode:
                self.alice.switch_to_claude()
                self.uncensored_button.remove_css_class('uncensored-button-active')
                self.uncensored_button.add_css_class('toolbar-button')
                self.add_message("Switched back to Claude.", is_system=True)
            else:
                self.alice.switch_to_uncensored()
                self.uncensored_button.remove_css_class('toolbar-button')
                self.uncensored_button.add_css_class('uncensored-button-active')
                self.add_message("Switched to dolphin-llama3 (uncensored, local). Memory loaded.", is_system=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.add_message(f"Error switching model: {e}", is_system=True)

    def _on_next_section(self, widget):
        """Advance to the next lesson section."""
        if not self._teacher_mode_active or not self.alice.is_teacher_mode:
            return
        self.add_message("next", is_user=True)
        self._set_input_sensitive(False)
        self.alice.process_async('next', self._on_response)

    def _show_lesson_selector(self):
        """Show modal window to pick a lesson (GTK4-compatible, no Gtk.Dialog)."""
        lessons = get_all_lessons_with_status()
        if not lessons:
            self.add_message("Can't find lesson files. Check that /home/glenn/500G/learning/classes/ exists.", is_system=True)
            return

        win = Gtk.Window(title="Choose a Lesson")
        win.set_transient_for(self)
        win.set_modal(True)
        win.set_default_size(440, 460)
        win.set_resizable(False)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        win.set_child(outer)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inner.set_margin_top(10)
        inner.set_margin_bottom(10)
        inner.set_margin_start(10)
        inner.set_margin_end(10)
        outer.append(inner)

        hint_label = Gtk.Label(label="Today's lesson is highlighted. Pick any lesson to start.")
        hint_label.add_css_class('lesson-dialog-hint')
        hint_label.set_xalign(0)
        inner.append(hint_label)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(300)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        listbox.add_css_class('lesson-list')

        today_row = None
        next_row = None

        for lesson in lessons:
            row = Gtk.ListBoxRow()
            row.lesson_info = {
                'number': lesson['number'],
                'tool': lesson['tool'],
                'file': lesson['file'],
                'date': lesson['date'],
            }

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.set_margin_top(5)
            box.set_margin_bottom(5)

            # Lesson number
            num_label = Gtk.Label(label=f"{lesson['number']:02d}")
            num_label.add_css_class('lesson-num')
            num_label.set_size_request(28, -1)
            box.append(num_label)

            # Tool name
            tool_label = Gtk.Label(label=lesson['tool'])
            tool_label.set_xalign(0)
            tool_label.set_hexpand(True)
            if lesson.get('is_today'):
                tool_label.add_css_class('lesson-today')
            elif lesson.get('completed'):
                tool_label.add_css_class('lesson-done')
            else:
                tool_label.add_css_class('lesson-name')
            box.append(tool_label)

            # Date
            date_label = Gtk.Label(label=lesson['date'])
            date_label.add_css_class('lesson-date')
            box.append(date_label)

            # Status indicator
            if lesson.get('completed'):
                status = Gtk.Label(label="✓")
                status.add_css_class('lesson-check')
                box.append(status)
            elif lesson.get('is_today'):
                status = Gtk.Label(label="TODAY")
                status.add_css_class('lesson-today-badge')
                box.append(status)

            row.set_child(box)
            listbox.append(row)

            if lesson.get('is_today'):
                today_row = row
            elif next_row is None and not lesson.get('completed'):
                next_row = row

        scrolled.set_child(listbox)
        inner.append(scrolled)

        # Auto-select today's lesson, then next uncompleted
        target_row = today_row or next_row
        if target_row:
            listbox.select_row(target_row)

        # Buttons row
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(6)
        inner.append(btn_box)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect('clicked', lambda _: win.destroy())
        btn_box.append(cancel_btn)

        start_btn = Gtk.Button(label="Start")
        start_btn.add_css_class('suggested-action')
        btn_box.append(start_btn)

        def on_start(_btn):
            selected = listbox.get_selected_row()
            if selected and hasattr(selected, 'lesson_info'):
                win.destroy()
                self._start_lesson(selected.lesson_info)

        start_btn.connect('clicked', on_start)

        # Double-click on row also starts
        listbox.connect('row-activated', lambda _lb, row: on_start(None))

        win.present()

    def _start_lesson(self, lesson_info: dict):
        """Initialize teacher mode and show Alice's intro."""
        self._teacher_mode_active = True

        # Update button to "End Lesson" (red)
        self.lesson_button.set_label("End Lesson")
        self.lesson_button.remove_css_class('lesson-button')
        self.lesson_button.add_css_class('lesson-button-active')
        self.next_button.set_visible(True)

        # Show status label
        self.lesson_status_label.set_label(
            f"{lesson_info['tool']} · Starting..."
        )
        self.lesson_status_label.set_visible(True)

        # Show system message
        self.add_message(
            f"Lesson {lesson_info['number']}: {lesson_info['tool']} — Teacher mode ON",
            is_system=True
        )

        # Disable input while Alice generates intro
        self._set_input_sensitive(False)

        # Start lesson async (LLM generates intro)
        self.alice.start_lesson_async(lesson_info, self._on_lesson_intro_ready)

    def _on_lesson_intro_ready(self, intro_text: str):
        """Called when Alice's lesson intro is generated."""
        GLib.idle_add(self._display_lesson_intro, intro_text)

    def _display_lesson_intro(self, intro_text: str):
        """Display the lesson intro (main thread)."""
        session = self.alice.teacher_session
        if session:
            self.lesson_status_label.set_label(
                f"{session.lesson_tool} · {session.full_progress_str()}"
            )

        self.add_message(intro_text, is_user=False)
        self._set_input_sensitive(True)
        self.input_entry.grab_focus()

        if self.tts_enabled:
            self.alice.speak_async(intro_text)

        return False

    def _end_lesson(self, save: bool = True):
        """Exit teacher mode."""
        self._teacher_mode_active = False

        # Restore button
        self.lesson_button.set_label("Lesson")
        self.lesson_button.remove_css_class('lesson-button-active')
        self.lesson_button.add_css_class('lesson-button')
        self.next_button.set_visible(False)

        # Hide status label
        self.lesson_status_label.set_visible(False)

        # Disable input while ending
        self._set_input_sensitive(False)
        self.alice.end_lesson_async(self._on_lesson_ended)

    def _on_lesson_ended(self, farewell: str):
        """Called when lesson end is processed."""
        GLib.idle_add(self._display_lesson_end, farewell)

    def _display_lesson_end(self, farewell: str):
        """Display lesson end message (main thread)."""
        self.add_message(farewell, is_user=False)
        self.add_message("Lesson ended — back to normal mode.", is_system=True)
        self._set_input_sensitive(True)
        self.input_entry.grab_focus()
        if self.tts_enabled:
            self.alice.speak_async(farewell)
        return False

    def _update_lesson_status(self):
        """Refresh the section/step progress label during teacher mode."""
        session = self.alice.teacher_session
        if session and self._teacher_mode_active:
            self.lesson_status_label.set_label(
                f"{session.lesson_tool} · {session.full_progress_str()}"
            )

    # ──────────────────────────────────────────────
    # Chat tab (existing functionality)
    # ──────────────────────────────────────────────

    def _build_chat_page(self):
        """Build the chat tab content."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.add_css_class('toolbar')
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)

        # Load Reference Doc button
        self.ref_doc_button = Gtk.Button(label="Ref")
        self.ref_doc_button.add_css_class('toolbar-button')
        self.ref_doc_button.set_tooltip_text("Load a document for this session")
        self.ref_doc_button.connect('clicked', self._on_load_reference)
        toolbar.append(self.ref_doc_button)

        # Session docs indicator
        self.session_docs_label = Gtk.Label(label="")
        self.session_docs_label.add_css_class('session-docs-label')
        toolbar.append(self.session_docs_label)

        # Add Knowledge button
        self.knowledge_button = Gtk.Button(label="Know")
        self.knowledge_button.add_css_class('toolbar-button')
        self.knowledge_button.set_tooltip_text("Add permanent knowledge")
        self.knowledge_button.connect('clicked', self._on_add_knowledge)
        toolbar.append(self.knowledge_button)

        # Profile toggle — Work / Chill
        self.profile_button = Gtk.Button(label="😎 Chill")
        self.profile_button.add_css_class('toolbar-button')
        self.profile_button.set_tooltip_text("Toggle work/chill mode")
        self.profile_button.connect('clicked', self._on_profile_toggle)
        toolbar.append(self.profile_button)
        # Sync button with Alice's current profile (restored from memory on init)
        self._sync_profile_button(self.alice.active_profile)
        # Register callback so voice commands update the button too
        self.alice.profile_change_callback = self._sync_profile_button

        # Uncensored model toggle
        self.uncensored_button = Gtk.Button(label="Dolphin")
        self.uncensored_button.add_css_class('toolbar-button')
        self.uncensored_button.set_tooltip_text("Switch to dolphin-llama3 (uncensored local model)")
        self.uncensored_button.connect('clicked', self._on_uncensored_toggle)
        toolbar.append(self.uncensored_button)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        # Lesson status label (hidden until teacher mode active)
        self.lesson_status_label = Gtk.Label(label="")
        self.lesson_status_label.add_css_class('lesson-status-label')
        self.lesson_status_label.set_visible(False)
        toolbar.append(self.lesson_status_label)

        # Next Section button (teacher mode only)
        self.next_button = Gtk.Button(label="→ Next")
        self.next_button.add_css_class('next-section-button')
        self.next_button.set_tooltip_text("Advance to next section")
        self.next_button.connect('clicked', self._on_next_section)
        self.next_button.set_visible(False)
        toolbar.append(self.next_button)

        # Fullscreen voice mode button
        fullscreen_btn = Gtk.Button(label="⛶")
        fullscreen_btn.add_css_class('toolbar-button')
        fullscreen_btn.set_tooltip_text("Voice-only fullscreen mode (F11)")
        fullscreen_btn.connect('clicked', self._on_open_fullscreen)
        toolbar.append(fullscreen_btn)

        # Start Lesson button
        self.lesson_button = Gtk.Button(label="Lesson")
        self.lesson_button.add_css_class('lesson-button')
        self.lesson_button.set_tooltip_text("Start a hacking lesson")
        self.lesson_button.connect('clicked', self._on_lesson_button)
        toolbar.append(self.lesson_button)

        page.append(toolbar)

        # Chat area
        chat_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        chat_frame.set_vexpand(True)
        chat_frame.set_margin_start(10)
        chat_frame.set_margin_end(10)
        chat_frame.set_margin_top(10)
        chat_frame.add_css_class('chat-container')

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_propagate_natural_height(False)
        self.scrolled.set_min_content_height(200)

        self.message_list = Gtk.ListBox()
        self.message_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scrolled.set_child(self.message_list)

        chat_frame.append(self.scrolled)
        page.append(chat_frame)

        # Input area
        input_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        input_container.add_css_class('input-container')
        input_container.set_margin_start(8)
        input_container.set_margin_end(8)
        input_container.set_margin_top(6)
        input_container.set_margin_bottom(8)

        self.input_entry = Gtk.Entry()
        self.input_entry.set_placeholder_text("Type or press F12 to speak...")
        self.input_entry.set_hexpand(True)
        self.input_entry.add_css_class('input-entry')
        self.input_entry.connect('activate', self._on_send)

        self.voice_button = Gtk.Button(label="🎙")
        self.voice_button.add_css_class('voice-button')
        self.voice_button.set_tooltip_text("Voice input (F12)")
        self.voice_button.connect('clicked', self._on_voice_toggle)

        self.type_button = Gtk.Button(label="⌨")
        self.type_button.add_css_class('type-button')
        self.type_button.set_tooltip_text("Focus text input (type mode)")
        self.type_button.connect('clicked', self._on_type_toggle)

        self.tts_button = Gtk.Button(label="🔊")
        self.tts_button.add_css_class('tts-button')
        self.tts_button.add_css_class('active')
        self.tts_button.set_tooltip_text("Toggle text-to-speech (Ctrl+T)")
        self.tts_button.connect('clicked', self._on_tts_toggle)

        self.send_button = Gtk.Button(label="➤")
        self.send_button.add_css_class('send-button')
        self.send_button.connect('clicked', self._on_send)

        input_container.append(self.input_entry)
        input_container.append(self.voice_button)
        input_container.append(self.type_button)
        input_container.append(self.tts_button)
        input_container.append(self.send_button)

        page.append(input_container)
        return page

    # ──────────────────────────────────────────────
    # Calendar tab
    # ──────────────────────────────────────────────

    def _build_calendar_page(self):
        """Build the calendar tab content."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.add_css_class('toolbar')
        toolbar.set_margin_start(10)
        toolbar.set_margin_end(10)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)

        add_btn = Gtk.Button(label="Add Event")
        add_btn.add_css_class('toolbar-button')
        add_btn.connect('clicked', self._on_cal_add_event)
        toolbar.append(add_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.add_css_class('toolbar-button')
        refresh_btn.connect('clicked', lambda w: self._load_calendar_events())
        toolbar.append(refresh_btn)

        page.append(toolbar)

        # Event list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_margin_start(10)
        scrolled.set_margin_end(10)
        scrolled.set_margin_top(6)
        scrolled.set_margin_bottom(10)

        self.cal_listbox = Gtk.ListBox()
        self.cal_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.cal_listbox.add_css_class('cal-list')
        self.cal_listbox.connect('row-activated', self._on_cal_row_activated)
        scrolled.set_child(self.cal_listbox)

        page.append(scrolled)
        return page

    def _load_calendar_events(self):
        """Read apts file and populate the calendar listbox."""
        # Clear existing rows
        while True:
            row = self.cal_listbox.get_row_at_index(0)
            if row is None:
                break
            self.cal_listbox.remove(row)

        if not APTS_FILE.exists():
            return

        events = []
        try:
            with open(APTS_FILE, 'r') as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if not line or '|' not in line:
                        continue
                    parsed = self._parse_apt_line(line)
                    if parsed:
                        parsed['line_num'] = line_num
                        parsed['raw'] = line
                        events.append(parsed)
        except Exception:
            return

        # Sort by date then time
        events.sort(key=lambda e: (e['date'], e['time_sort']))

        for ev in events:
            row = self._make_cal_row(ev)
            self.cal_listbox.append(row)

    def _parse_apt_line(self, line: str) -> dict | None:
        """Parse a calcurse apts line into a dict."""
        if '|' not in line:
            return None
        desc = line.split('|', 1)[1].strip()
        date_match = re.match(r'(\d{2})/(\d{2})/(\d{4})', line)
        if not date_match:
            return None
        month, day, year = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
        try:
            date = datetime(year, month, day)
        except ValueError:
            return None

        time_match = re.search(r'@ (\d{2}):(\d{2})', line)
        if time_match:
            hour, minute = int(time_match.group(1)), int(time_match.group(2))
            ampm = "AM" if hour < 12 else "PM"
            display_hour = hour if hour <= 12 else hour - 12
            if display_hour == 0:
                display_hour = 12
            time_str = f"{display_hour}:{minute:02d} {ampm}"
            time_sort = f"{hour:02d}:{minute:02d}"
        else:
            time_str = "All day"
            time_sort = "00:00"

        return {
            'date': date,
            'date_str': date.strftime("%m/%d/%Y"),
            'date_display': date.strftime("%a %m/%d/%Y"),
            'time_str': time_str,
            'time_sort': time_sort,
            'desc': desc,
        }

    def _make_cal_row(self, ev: dict) -> Gtk.ListBoxRow:
        """Create a listbox row for a calendar event."""
        row = Gtk.ListBoxRow()
        row.event_data = ev

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.add_css_class('cal-row')
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        date_label = Gtk.Label(label=ev['date_display'])
        date_label.add_css_class('cal-date')
        date_label.set_xalign(0)
        date_label.set_size_request(120, -1)
        box.append(date_label)

        time_label = Gtk.Label(label=ev['time_str'])
        time_label.add_css_class('cal-time')
        time_label.set_xalign(0)
        time_label.set_size_request(80, -1)
        box.append(time_label)

        desc_label = Gtk.Label(label=ev['desc'])
        desc_label.add_css_class('cal-desc')
        desc_label.set_xalign(0)
        desc_label.set_hexpand(True)
        desc_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        box.append(desc_label)

        row.set_child(box)
        return row

    def _on_cal_row_activated(self, listbox, row):
        """Open edit dialog for a calendar event."""
        ev = row.event_data
        self._show_event_dialog(ev)

    def _on_cal_add_event(self, widget):
        """Show dialog to add a new calendar event."""
        self._show_event_dialog(None)

    def _show_event_dialog(self, ev):
        """Show add/edit dialog for a calendar event. ev=None means add new."""
        is_edit = ev is not None

        win = Gtk.Window(title="Edit Event" if is_edit else "Add Event")
        win.set_transient_for(self)
        win.set_modal(True)
        win.set_default_size(350, -1)
        win.set_resizable(False)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        win.set_child(outer)

        # Date
        date_label = Gtk.Label(label="Date (MM/DD/YYYY)")
        date_label.set_xalign(0)
        outer.append(date_label)
        date_entry = Gtk.Entry()
        date_entry.set_placeholder_text("02/19/2026")
        date_entry.set_text(ev['date_str'] if is_edit else datetime.now().strftime("%m/%d/%Y"))
        outer.append(date_entry)

        # Time
        time_label = Gtk.Label(label="Time (HH:MM 24h, or leave blank for all-day)")
        time_label.set_xalign(0)
        outer.append(time_label)
        time_entry = Gtk.Entry()
        time_entry.set_placeholder_text("14:30")
        if is_edit and ev['time_str'] != "All day":
            time_entry.set_text(ev['time_sort'])
        outer.append(time_entry)

        # Description
        desc_label = Gtk.Label(label="Description")
        desc_label.set_xalign(0)
        outer.append(desc_label)
        desc_entry = Gtk.Entry()
        desc_entry.set_placeholder_text("Event description")
        if is_edit:
            desc_entry.set_text(ev['desc'])
        outer.append(desc_entry)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(6)
        outer.append(btn_box)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect('clicked', lambda _: win.destroy())
        btn_box.append(cancel_btn)

        if is_edit:
            del_btn = Gtk.Button(label="Delete")
            del_btn.add_css_class('destructive-action')
            def on_delete(_):
                self._delete_apt_line(ev['raw'])
                self._load_calendar_events()
                win.destroy()
            del_btn.connect('clicked', on_delete)
            btn_box.append(del_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class('suggested-action')
        def on_save(_):
            date_text = date_entry.get_text().strip()
            time_text = time_entry.get_text().strip()
            desc_text = desc_entry.get_text().strip()
            if not date_text or not desc_text:
                win.destroy()
                return
            if time_text:
                match = re.match(r'(\d{1,2}):(\d{2})', time_text)
                if match:
                    h, m = int(match.group(1)), int(match.group(2))
                    eh = h + 1
                    new_line = f"{date_text} @ {h:02d}:{m:02d} -> {date_text} @ {eh:02d}:{m:02d} |{desc_text}"
                else:
                    new_line = f"{date_text} [1] |{desc_text}"
            else:
                new_line = f"{date_text} [1] |{desc_text}"
            if is_edit:
                self._replace_apt_line(ev['raw'], new_line)
            else:
                with open(APTS_FILE, 'a') as f:
                    f.write(new_line + '\n')
            self._load_calendar_events()
            win.destroy()
        save_btn.connect('clicked', on_save)
        btn_box.append(save_btn)

        win.present()

    def _delete_apt_line(self, raw_line: str):
        """Delete a line from the apts file."""
        try:
            lines = APTS_FILE.read_text().splitlines()
            lines = [l for l in lines if l.strip() != raw_line.strip()]
            APTS_FILE.write_text('\n'.join(lines) + '\n' if lines else '')
        except Exception:
            pass

    def _replace_apt_line(self, old_raw: str, new_line: str):
        """Replace a line in the apts file."""
        try:
            lines = APTS_FILE.read_text().splitlines()
            new_lines = []
            for l in lines:
                if l.strip() == old_raw.strip():
                    new_lines.append(new_line)
                else:
                    new_lines.append(l)
            APTS_FILE.write_text('\n'.join(new_lines) + '\n' if new_lines else '')
        except Exception:
            pass

    # ──────────────────────────────────────────────
    # To Do tab
    # ──────────────────────────────────────────────

    def _build_todo_page(self):
        """Build the to-do tab content."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Scrollable todo list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_margin_start(10)
        scrolled.set_margin_end(10)
        scrolled.set_margin_top(10)

        self.todo_listbox = Gtk.ListBox()
        self.todo_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.todo_listbox.add_css_class('todo-list')
        scrolled.set_child(self.todo_listbox)

        page.append(scrolled)

        # Add todo input bar
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        input_box.add_css_class('todo-input-container')
        input_box.set_margin_start(10)
        input_box.set_margin_end(10)
        input_box.set_margin_top(8)
        input_box.set_margin_bottom(10)

        self.todo_entry = Gtk.Entry()
        self.todo_entry.set_placeholder_text("Add a to-do item...")
        self.todo_entry.set_hexpand(True)
        self.todo_entry.add_css_class('input-entry')
        self.todo_entry.connect('activate', self._on_todo_add)

        add_btn = Gtk.Button(label="Add")
        add_btn.add_css_class('send-button')
        add_btn.connect('clicked', self._on_todo_add)

        input_box.append(self.todo_entry)
        input_box.append(add_btn)

        page.append(input_box)
        return page

    def _load_todo_items(self):
        """Read calcurse todo file and populate the todo listbox."""
        # Clear existing
        while True:
            row = self.todo_listbox.get_row_at_index(0)
            if row is None:
                break
            self.todo_listbox.remove(row)

        if not TODO_FILE.exists():
            return

        try:
            lines = TODO_FILE.read_text().splitlines()
        except Exception:
            return

        for line in lines:
            line = line.strip()
            if not line:
                continue
            parsed = self._parse_todo_line(line)
            if parsed:
                row = self._make_todo_row(parsed)
                self.todo_listbox.append(row)

    def _parse_todo_line(self, line: str) -> dict | None:
        """Parse a calcurse todo line. Format: [5] or [-5] followed by text."""
        match = re.match(r'\[(-?\d+)\]\s*(.*)', line)
        if not match:
            return None
        priority = int(match.group(1))
        desc = match.group(2).strip()
        completed = priority < 0
        return {
            'desc': desc,
            'completed': completed,
            'priority': abs(priority),
            'raw': line,
        }

    def _make_todo_row(self, item: dict) -> Gtk.ListBoxRow:
        """Create a listbox row for a todo item."""
        row = Gtk.ListBoxRow()
        row.set_activatable(False)
        row.todo_data = item

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.add_css_class('todo-row')
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        # Checkbox
        check = Gtk.CheckButton()
        check.set_active(item['completed'])
        check.connect('toggled', self._on_todo_toggled, row)
        box.append(check)

        # Description label
        label = Gtk.Label(label=item['desc'])
        label.set_xalign(0)
        label.set_hexpand(True)
        label.set_wrap(True)
        label.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        label.add_css_class('todo-desc')
        if item['completed']:
            label.add_css_class('todo-done')
        row.todo_label = label
        box.append(label)

        # Delete button
        del_btn = Gtk.Button(label="x")
        del_btn.add_css_class('todo-delete-btn')
        del_btn.set_tooltip_text("Delete item")
        del_btn.connect('clicked', self._on_todo_delete, row)
        box.append(del_btn)

        row.set_child(box)
        return row

    def _on_todo_add(self, widget):
        """Add a new todo item."""
        text = self.todo_entry.get_text().strip()
        if not text:
            return
        self.todo_entry.set_text("")

        # Append to calcurse todo file with default priority 5
        new_line = f"[5] {text}"
        try:
            with open(TODO_FILE, 'a') as f:
                f.write(new_line + '\n')
        except Exception:
            return

        self._load_todo_items()

    def _on_todo_toggled(self, check_button, row):
        """Toggle a todo item's completed state."""
        item = row.todo_data
        old_raw = item['raw']
        now_completed = check_button.get_active()

        if now_completed:
            new_raw = f"[-{item['priority']}] {item['desc']}"
            row.todo_label.add_css_class('todo-done')
        else:
            new_raw = f"[{item['priority']}] {item['desc']}"
            row.todo_label.remove_css_class('todo-done')

        self._replace_todo_line(old_raw, new_raw)
        item['raw'] = new_raw
        item['completed'] = now_completed

    def _on_todo_delete(self, button, row):
        """Delete a todo item."""
        item = row.todo_data
        self._delete_todo_line(item['raw'])
        self.todo_listbox.remove(row)

    def _replace_todo_line(self, old_line: str, new_line: str):
        """Replace a line in the todo file."""
        try:
            lines = TODO_FILE.read_text().splitlines()
            new_lines = []
            replaced = False
            for l in lines:
                if not replaced and l.strip() == old_line.strip():
                    new_lines.append(new_line)
                    replaced = True
                else:
                    new_lines.append(l)
            TODO_FILE.write_text('\n'.join(new_lines) + '\n' if new_lines else '')
        except Exception:
            pass

    def _delete_todo_line(self, raw_line: str):
        """Delete a line from the todo file."""
        try:
            lines = TODO_FILE.read_text().splitlines()
            new_lines = []
            deleted = False
            for l in lines:
                if not deleted and l.strip() == raw_line.strip():
                    deleted = True
                else:
                    new_lines.append(l)
            TODO_FILE.write_text('\n'.join(new_lines) + '\n' if new_lines else '')
        except Exception:
            pass

    # ──────────────────────────────────────────────
    # Tab switching
    # ──────────────────────────────────────────────

    def _on_tab_switched(self, notebook, page, page_num):
        """Refresh data when switching tabs."""
        if page_num == 1:
            self._load_calendar_events()
        elif page_num == 2:
            self._load_todo_items()
        elif page_num == 3:
            self._load_contacts()

    # ──────────────────────────────────────────────
    # Messages tab (WhatsApp)
    # ──────────────────────────────────────────────

    def _build_messages_page(self):
        """Build the Messages (WhatsApp) tab."""
        from tools.contacts import load as load_contacts_data
        self._selected_contact = None

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # ── Toolbar ──────────────────────────────
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.add_css_class('toolbar')
        toolbar.set_margin_start(10)
        toolbar.set_margin_end(10)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)

        wa_label = Gtk.Label(label="📱 WhatsApp")
        wa_label.add_css_class('msg-title-label')
        toolbar.append(wa_label)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        add_btn = Gtk.Button(label="+ Contact")
        add_btn.add_css_class('toolbar-button')
        add_btn.set_tooltip_text("Add a new contact")
        add_btn.connect('clicked', self._on_add_contact)
        toolbar.append(add_btn)

        import_btn = Gtk.Button(label="⇩ Google")
        import_btn.add_css_class('toolbar-button')
        import_btn.set_tooltip_text("Import contacts from Google Contacts CSV\n(export from contacts.google.com → Export → Google CSV)")
        import_btn.connect('clicked', self._on_import_google)
        toolbar.append(import_btn)

        page.append(toolbar)

        # ── Contacts grid ─────────────────────────
        contacts_scroll = Gtk.ScrolledWindow()
        contacts_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        contacts_scroll.set_min_content_height(110)
        contacts_scroll.set_max_content_height(110)

        self._contacts_flow = Gtk.FlowBox()
        self._contacts_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._contacts_flow.set_column_spacing(6)
        self._contacts_flow.set_row_spacing(6)
        self._contacts_flow.set_margin_start(10)
        self._contacts_flow.set_margin_end(10)
        self._contacts_flow.set_margin_top(6)
        self._contacts_flow.set_margin_bottom(6)
        self._contacts_flow.set_max_children_per_line(4)

        contacts_scroll.set_child(self._contacts_flow)
        page.append(contacts_scroll)

        # ── Separator ─────────────────────────────
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        page.append(sep)

        # ── Compose area ──────────────────────────
        compose_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        compose_box.set_margin_start(10)
        compose_box.set_margin_end(10)
        compose_box.set_margin_top(8)
        compose_box.set_margin_bottom(4)

        self._compose_to_label = Gtk.Label(label="← Select a contact above")
        self._compose_to_label.add_css_class('compose-to-label')
        self._compose_to_label.set_xalign(0)
        compose_box.append(self._compose_to_label)

        self._compose_entry = Gtk.Entry()
        self._compose_entry.set_placeholder_text("Type your message...")
        self._compose_entry.set_hexpand(True)
        self._compose_entry.add_css_class('compose-entry')
        self._compose_entry.connect('activate', self._on_compose_send)
        compose_box.append(self._compose_entry)

        send_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self._wa_send_btn = Gtk.Button(label="📱 Send WhatsApp")
        self._wa_send_btn.add_css_class('wa-send-button')
        self._wa_send_btn.set_hexpand(True)
        self._wa_send_btn.set_sensitive(False)
        self._wa_send_btn.connect('clicked', self._on_compose_send)
        send_row.append(self._wa_send_btn)

        compose_box.append(send_row)
        page.append(compose_box)

        # ── Quick messages ────────────────────────
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(4)
        page.append(sep2)

        quick_label = Gtk.Label(label="Quick messages")
        quick_label.add_css_class('quick-label')
        quick_label.set_xalign(0)
        quick_label.set_margin_start(10)
        quick_label.set_margin_top(6)
        page.append(quick_label)

        quick_scroll = Gtk.ScrolledWindow()
        quick_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        quick_scroll.set_vexpand(True)

        self._quick_flow = Gtk.FlowBox()
        self._quick_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._quick_flow.set_column_spacing(6)
        self._quick_flow.set_row_spacing(6)
        self._quick_flow.set_margin_start(10)
        self._quick_flow.set_margin_end(10)
        self._quick_flow.set_margin_top(4)
        self._quick_flow.set_margin_bottom(8)
        self._quick_flow.set_max_children_per_line(2)

        quick_scroll.set_child(self._quick_flow)
        page.append(quick_scroll)

        # ── Status label ──────────────────────────
        self._msg_status_label = Gtk.Label(label="")
        self._msg_status_label.add_css_class('msg-status-label')
        self._msg_status_label.set_margin_bottom(6)
        page.append(self._msg_status_label)

        # Populate
        self._load_contacts()
        return page

    def _load_contacts(self):
        """Reload contacts and quick messages from file."""
        from tools.contacts import load as load_contacts_data
        try:
            data = load_contacts_data()
        except Exception:
            return

        # Clear and rebuild contact buttons
        while self._contacts_flow.get_child_at_index(0):
            self._contacts_flow.remove(self._contacts_flow.get_child_at_index(0))

        for contact in data.get("contacts", []):
            name  = contact.get("name", "?")
            emoji = contact.get("emoji", "👤")
            wa    = contact.get("whatsapp", "")

            btn = Gtk.Button(label=f"{emoji}\n{name}")
            btn.add_css_class('contact-button')
            btn.set_tooltip_text(f"WhatsApp: +{wa}")
            btn.connect('clicked', self._on_contact_selected, contact)
            self._contacts_flow.append(btn)

        # Clear and rebuild quick message buttons
        while self._quick_flow.get_child_at_index(0):
            self._quick_flow.remove(self._quick_flow.get_child_at_index(0))

        for msg in data.get("quick_messages", []):
            btn = Gtk.Button(label=msg)
            btn.add_css_class('quick-msg-button')
            btn.connect('clicked', self._on_quick_message, msg)
            self._quick_flow.append(btn)

    def _on_contact_selected(self, widget, contact):
        """Select a contact for composing."""
        self._selected_contact = contact
        name  = contact.get("name", "?")
        emoji = contact.get("emoji", "👤")
        wa    = contact.get("whatsapp", "")
        self._compose_to_label.set_label(f"To: {emoji} {name}  (+{wa})")
        self._compose_to_label.add_css_class('compose-to-active')
        self._wa_send_btn.set_sensitive(True)
        self._compose_entry.grab_focus()
        self._msg_status_label.set_label("")

        # Highlight selected button
        child = self._contacts_flow.get_child_at_index(0)
        idx = 0
        while child:
            btn = child.get_child()
            if btn:
                if btn.get_label() == f"{emoji}\n{name}":
                    btn.add_css_class('contact-button-selected')
                else:
                    btn.remove_css_class('contact-button-selected')
            idx += 1
            child = self._contacts_flow.get_child_at_index(idx)

    def _on_quick_message(self, widget, msg):
        """Fill compose entry with quick message text."""
        self._compose_entry.set_text(msg)
        self._compose_entry.grab_focus()
        # Move cursor to end
        self._compose_entry.set_position(len(msg))

    def _on_compose_send(self, widget):
        """Send the composed WhatsApp message."""
        if not self._selected_contact:
            self._msg_status_label.set_label("⚠ Select a contact first")
            return
        msg = self._compose_entry.get_text().strip()
        if not msg:
            self._msg_status_label.set_label("⚠ Type a message first")
            return

        import json, subprocess
        wa    = self._selected_contact.get("whatsapp", "")
        name  = self._selected_contact.get("name", "?")
        chat_id = f"{wa}@c.us"
        payload = json.dumps({"chatId": chat_id, "message": msg})

        try:
            result = subprocess.run(
                ["curl", "-sf", "-X", "POST",
                 "-H", "Content-Type: application/json",
                 "-d", payload,
                 "http://localhost:3000/send"],
                capture_output=True, text=True, timeout=10
            )
            resp = json.loads(result.stdout)
            if resp.get("success"):
                self._msg_status_label.set_label(f"✅ Sent to {name}")
                self._compose_entry.set_text("")
            else:
                self._msg_status_label.set_label(f"❌ Failed: {resp.get('error', 'unknown')}")
        except Exception as e:
            self._msg_status_label.set_label(f"❌ Error: {e}")

    def _on_add_contact(self, widget):
        """Show add contact dialog."""
        win = Gtk.Window(title="Add Contact")
        win.set_transient_for(self)
        win.set_modal(True)
        win.set_default_size(320, 200)
        win.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        win.set_child(box)

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Name (e.g. Bea)")
        box.append(name_entry)

        phone_entry = Gtk.Entry()
        phone_entry.set_placeholder_text("WhatsApp number (e.g. 34679205712)")
        box.append(phone_entry)

        emoji_entry = Gtk.Entry()
        emoji_entry.set_placeholder_text("Emoji (e.g. ❤️)  — optional")
        box.append(emoji_entry)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect('clicked', lambda _: win.destroy())
        btn_row.append(cancel)

        save_btn = Gtk.Button(label="Add")
        save_btn.add_css_class('suggested-action')
        btn_row.append(save_btn)

        def on_save(_):
            from tools.contacts import add_contact
            name  = name_entry.get_text().strip()
            phone = phone_entry.get_text().strip().replace("+", "").replace(" ", "")
            emoji = emoji_entry.get_text().strip() or "👤"
            if name and phone:
                add_contact(name, phone, emoji)
                self._load_contacts()
                win.destroy()

        save_btn.connect('clicked', on_save)
        win.present()

    def _on_import_google(self, widget):
        """Import contacts from Google CSV file."""
        dialog = Gtk.FileChooserNative(
            title="Select Google Contacts CSV",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        f = Gtk.FileFilter()
        f.set_name("CSV files")
        f.add_pattern("*.csv")
        dialog.add_filter(f)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                path = d.get_file().get_path()
                from tools.contacts import import_google_csv
                try:
                    n = import_google_csv(path)
                    self._load_contacts()
                    self._msg_status_label.set_label(f"✅ Imported {n} contacts from Google")
                except Exception as e:
                    self._msg_status_label.set_label(f"❌ Import failed: {e}")
            d.destroy()

        dialog.connect('response', on_response)
        dialog.show()

    # ──────────────────────────────────────────────
    # Chat functionality (unchanged)
    # ──────────────────────────────────────────────

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        action_voice = Gio.SimpleAction.new("voice-input", None)
        action_voice.connect("activate", lambda a, p: self._on_voice_toggle(None))
        self.add_action(action_voice)
        self.app.set_accels_for_action("win.voice-input", ["F12"])

        action_clear = Gio.SimpleAction.new("clear-chat", None)
        action_clear.connect("activate", lambda a, p: self._on_clear())
        self.add_action(action_clear)
        self.app.set_accels_for_action("win.clear-chat", ["<Control>l"])

        action_tts = Gio.SimpleAction.new("toggle-tts", None)
        action_tts.connect("activate", lambda a, p: self._on_tts_toggle(None))
        self.add_action(action_tts)
        self.app.set_accels_for_action("win.toggle-tts", ["<Control>t"])

        action_cancel = Gio.SimpleAction.new("cancel-recording", None)
        action_cancel.connect("activate", lambda a, p: self._on_cancel_recording())
        self.add_action(action_cancel)
        self.app.set_accels_for_action("win.cancel-recording", ["Escape"])

        action_fullscreen = Gio.SimpleAction.new("voice-fullscreen", None)
        action_fullscreen.connect("activate", lambda a, p: self._on_open_fullscreen(None))
        self.add_action(action_fullscreen)
        self.app.set_accels_for_action("win.voice-fullscreen", ["F11"])

    # ── Voice fullscreen ──────────────────────────────────────────────────────

    def _on_open_fullscreen(self, widget):
        """Launch the voice-only fullscreen window."""
        from gui.fullscreen import VoiceFullscreenWindow
        fs = VoiceFullscreenWindow(alice=self.alice, parent=self)
        fs.present()

    # ── Hermes activity (live tool/status streaming) ─────────────────────────

    def _on_hermes_activity(self, line: str):
        """Called from background thread with each hermes activity line."""
        cleaned = line.strip()
        if cleaned:
            GLib.idle_add(self._update_activity_row, cleaned)

    def _update_activity_row(self, text: str):
        """Create or update the single activity row (main thread)."""
        if self._activity_label is None:
            self._activity_label = Gtk.Label()
            self._activity_label.set_wrap(True)
            self._activity_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            self._activity_label.set_max_width_chars(55)
            self._activity_label.set_xalign(0)
            self._activity_label.add_css_class('activity-message')
            self._activity_row = Gtk.ListBoxRow()
            self._activity_row.set_child(self._activity_label)
            self._activity_row.add_css_class('message-row')
            self._activity_row.set_activatable(False)
            self.message_list.append(self._activity_row)
        self._activity_label.set_label(text)
        GLib.idle_add(self._scroll_to_bottom)
        return False

    def _clear_activity(self):
        """Remove the activity row (called when hermes response arrives)."""
        if self._activity_row is not None:
            self.message_list.remove(self._activity_row)
            self._activity_row = None
            self._activity_label = None

    # ──────────────────────────────────────────────

    def add_message(self, text: str, is_user: bool = False, is_system: bool = False, is_thinking: bool = False):
        """Add a message to the chat."""
        label = Gtk.Label(label=text)
        label.set_wrap(True)
        label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_max_width_chars(55)
        label.set_xalign(0)
        label.set_selectable(True)

        if is_thinking:
            label.add_css_class('thinking-message')
            label.set_halign(Gtk.Align.START)
        elif is_system:
            label.add_css_class('system-message')
            label.set_halign(Gtk.Align.CENTER)
        elif is_user:
            label.add_css_class('user-message')
            label.set_halign(Gtk.Align.END)
        else:
            label.add_css_class('assistant-message')
            label.set_halign(Gtk.Align.START)

        row = Gtk.ListBoxRow()
        row.set_child(label)
        row.add_css_class('message-row')
        row.set_activatable(False)

        self.message_list.append(row)
        GLib.idle_add(self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """Scroll chat to the bottom."""
        adj = self.scrolled.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return False

    def _on_send(self, widget):
        """Handle send button/enter key."""
        text = self.input_entry.get_text().strip()
        if not text:
            return

        self.input_entry.set_text("")
        self.add_message(text, is_user=True)
        self._set_input_sensitive(False)
        self.alice.process_async(text, self._on_response)

    def _on_response(self, response: dict):
        """Handle response (called from background thread)."""
        GLib.idle_add(self._display_response, response)

    def _display_response(self, response: dict):
        """Display response in chat (main thread)."""
        self._clear_activity()
        thinking = response.get('thinking', '')
        answer = response.get('response', '')

        if thinking:
            self.add_message(f"[thinking]\n{thinking}", is_thinking=True)

        self.add_message(answer, is_user=False)
        self._set_input_sensitive(True)
        self.input_entry.grab_focus()

        # Update lesson section progress label if in teacher mode
        if self._teacher_mode_active:
            if self.alice.teacher_session is None:
                # Lesson just auto-completed (quiz finished)
                self._teacher_mode_active = False
                self.lesson_button.set_label("Lesson")
                self.lesson_button.remove_css_class('lesson-button-active')
                self.lesson_button.add_css_class('lesson-button')
                self.next_button.set_visible(False)
                self.lesson_status_label.set_visible(False)
                self.add_message("Lesson complete — back to normal mode.", is_system=True)
            else:
                self._update_lesson_status()

        force_speak = response.get('speak', False)
        if self.tts_enabled and answer and (force_speak or not getattr(self.alice.llm, 'handles_tts', False)):
            self.alice.speak_async(answer)

        return False

    def _on_voice_toggle(self, widget):
        """Handle voice button click."""
        if self.recorder.is_recording():
            self.voice_button.remove_css_class('recording')
            self.voice_button.set_label("F12")
            audio_file = self.recorder.stop()

            if audio_file:
                self.add_message("Transcribing...", is_system=True)
                self.alice.transcribe_async(audio_file, self._on_transcription)
        else:
            self.voice_button.add_css_class('recording')
            self.voice_button.set_label("...")
            self.recorder.start()

    def _on_transcription(self, text: str):
        """Handle transcription result (called from background thread)."""
        GLib.idle_add(self._process_transcription, text)

    def _process_transcription(self, text: str):
        """Process transcription result (main thread)."""
        if text and not text.startswith('['):
            self.add_message(text, is_user=True)
            self._set_input_sensitive(False)
            self.alice.process_async(text, self._on_response)
        else:
            self.add_message(f"Couldn't transcribe: {text}", is_system=True)
        return False

    def _on_tts_toggle(self, widget):
        """Toggle TTS on/off."""
        self.tts_enabled = not self.tts_enabled
        if self.tts_enabled:
            self.tts_button.add_css_class('active')
        else:
            self.tts_button.remove_css_class('active')

    def _on_type_toggle(self, widget):
        """Focus the text input and highlight it (type mode)."""
        self.input_entry.grab_focus()
        if self.type_button.has_css_class('type-button-active'):
            self.type_button.remove_css_class('type-button-active')
            self.input_entry.remove_css_class('input-entry-active')
        else:
            self.type_button.add_css_class('type-button-active')
            self.input_entry.add_css_class('input-entry-active')

    def _on_clear(self):
        """Clear chat history."""
        while True:
            row = self.message_list.get_row_at_index(0)
            if row is None:
                break
            self.message_list.remove(row)

        self.alice.clear_history()
        self.add_message("Chat cleared.", is_system=True)

    def _on_cancel_recording(self):
        """Cancel ongoing recording."""
        if self.recorder.is_recording():
            self.voice_button.remove_css_class('recording')
            self.voice_button.set_label("F12")
            self.recorder.stop()

    def _set_input_sensitive(self, sensitive: bool):
        """Enable/disable input controls."""
        self.input_entry.set_sensitive(sensitive)
        self.send_button.set_sensitive(sensitive)
        if hasattr(self, 'next_button') and self.next_button.get_visible():
            self.next_button.set_sensitive(sensitive)

    def _on_load_reference(self, widget):
        """Open file chooser to load a reference document."""
        native = Gtk.FileChooserNative.new("Load Reference Document", self, Gtk.FileChooserAction.OPEN, "Load", "Cancel")

        filter_all = Gtk.FileFilter()
        filter_all.set_name("Supported files")
        for pat in ["*.pdf", "*.txt", "*.md", "*.json", "*.py", "*.sh", "*.png", "*.jpg", "*.jpeg"]:
            filter_all.add_pattern(pat)
        native.add_filter(filter_all)

        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF documents")
        filter_pdf.add_pattern("*.pdf")
        native.add_filter(filter_pdf)

        filter_text = Gtk.FileFilter()
        filter_text.set_name("Text files")
        filter_text.add_pattern("*.txt")
        filter_text.add_pattern("*.md")
        native.add_filter(filter_text)

        def on_response(dlg, response):
            if response == Gtk.ResponseType.ACCEPT:
                f = dlg.get_file()
                if f:
                    file_path = f.get_path()
                    success, message = self.alice.load_session_document(file_path)
                    if success:
                        self.add_message(f"Loaded: {message}", is_system=True)
                        self._update_session_docs_label()
                    else:
                        self.add_message(f"Failed to load: {message}", is_system=True)

        native.connect("response", on_response)
        native.show()

    def _update_session_docs_label(self):
        """Update the session docs indicator."""
        docs = self.alice.get_session_documents()
        if docs:
            names = list(docs.keys())
            if len(names) <= 2:
                self.session_docs_label.set_label(f"[{', '.join(names)}]")
            else:
                self.session_docs_label.set_label(f"[{len(names)} docs loaded]")
        else:
            self.session_docs_label.set_label("")

    def _on_add_knowledge(self, widget):
        """Open window to add permanent knowledge."""
        win = Gtk.Window(title="Add Knowledge")
        win.set_transient_for(self)
        win.set_modal(True)
        win.set_default_size(400, 340)
        win.set_resizable(False)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        win.set_child(outer)

        title_label = Gtk.Label(label="Title (e.g., 'pacman commands')")
        title_label.set_xalign(0)
        outer.append(title_label)

        title_entry = Gtk.Entry()
        title_entry.set_placeholder_text("Short title...")
        outer.append(title_entry)

        cat_label = Gtk.Label(label="Category")
        cat_label.set_xalign(0)
        outer.append(cat_label)

        category_combo = Gtk.ComboBoxText()
        for cat in ("general", "arch-linux", "commands", "coding", "hardware", "other"):
            category_combo.append_text(cat)
        category_combo.set_active(0)
        outer.append(category_combo)

        content_label = Gtk.Label(label="Content")
        content_label.set_xalign(0)
        outer.append(content_label)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(100)
        content_view = Gtk.TextView()
        content_view.set_wrap_mode(Gtk.WrapMode.WORD)
        scrolled.set_child(content_view)
        outer.append(scrolled)

        def load_from_file(_btn):
            native = Gtk.FileChooserNative.new("Load Knowledge File", win, Gtk.FileChooserAction.OPEN, "Load", "Cancel")
            filt = Gtk.FileFilter()
            filt.set_name("Text files")
            filt.add_pattern("*.txt")
            filt.add_pattern("*.md")
            native.add_filter(filt)
            def on_file_chosen(dlg, resp):
                if resp == Gtk.ResponseType.ACCEPT:
                    f = dlg.get_file()
                    if f:
                        try:
                            text = Path(f.get_path()).read_text()
                            content_view.get_buffer().set_text(text)
                            if not title_entry.get_text():
                                title_entry.set_text(Path(f.get_path()).stem)
                        except Exception as e:
                            self.add_message(f"Error reading file: {e}", is_system=True)
            native.connect("response", on_file_chosen)
            native.show()

        load_btn = Gtk.Button(label="Load from file...")
        load_btn.connect('clicked', load_from_file)
        outer.append(load_btn)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(4)
        outer.append(btn_box)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect('clicked', lambda _: win.destroy())
        btn_box.append(cancel_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class('suggested-action')
        def on_save(_):
            title = title_entry.get_text().strip()
            category = category_combo.get_active_text()
            buf = content_view.get_buffer()
            content = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
            if title and content:
                self.alice.add_knowledge(title, content, category)
                self.add_message(f"Saved knowledge: '{title}' [{category}]", is_system=True)
            else:
                self.add_message("Need both title and content to save knowledge.", is_system=True)
            win.destroy()
        save_btn.connect('clicked', on_save)
        btn_box.append(save_btn)

        win.present()
