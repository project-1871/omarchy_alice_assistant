"""Main window with chat interface."""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')

from gi.repository import Gtk, Gdk, Gio, GLib
from pathlib import Path
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alice import Alice
from .recorder import AudioRecorder
import config


class MainWindow(Gtk.ApplicationWindow):
    """Main application window with chat interface."""

    def __init__(self, app):
        super().__init__(application=app, title="Alice")
        self.app = app
        self.set_default_size(500, 600)

        # Initialize components
        self.alice = Alice()
        self.recorder = AudioRecorder()
        self.tts_enabled = True  # TTS on by default

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

        # Toolbar for memory/knowledge buttons
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.add_css_class('toolbar')
        toolbar.set_margin_start(10)
        toolbar.set_margin_end(10)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)

        # Load Reference Doc button (temporary session memory)
        self.ref_doc_button = Gtk.Button(label="Load Reference")
        self.ref_doc_button.add_css_class('toolbar-button')
        self.ref_doc_button.set_tooltip_text("Load a document for this session (manual, book, etc.)")
        self.ref_doc_button.connect('clicked', self._on_load_reference)
        toolbar.append(self.ref_doc_button)

        # Session docs indicator
        self.session_docs_label = Gtk.Label(label="")
        self.session_docs_label.add_css_class('session-docs-label')
        toolbar.append(self.session_docs_label)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        # Add Knowledge button (permanent memory)
        self.knowledge_button = Gtk.Button(label="Add Knowledge")
        self.knowledge_button.add_css_class('toolbar-button')
        self.knowledge_button.set_tooltip_text("Add permanent knowledge (Arch commands, tips, etc.)")
        self.knowledge_button.connect('clicked', self._on_add_knowledge)
        toolbar.append(self.knowledge_button)

        main_box.append(toolbar)

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

        self.message_list = Gtk.ListBox()
        self.message_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scrolled.set_child(self.message_list)

        chat_frame.append(self.scrolled)
        main_box.append(chat_frame)

        # Input area
        input_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        input_container.add_css_class('input-container')
        input_container.set_margin_start(10)
        input_container.set_margin_end(10)
        input_container.set_margin_top(10)
        input_container.set_margin_bottom(10)

        # Text input
        self.input_entry = Gtk.Entry()
        self.input_entry.set_placeholder_text("Type or press F12 to speak...")
        self.input_entry.set_hexpand(True)
        self.input_entry.add_css_class('input-entry')
        self.input_entry.connect('activate', self._on_send)

        # Voice button
        self.voice_button = Gtk.Button(label="F12")
        self.voice_button.add_css_class('voice-button')
        self.voice_button.set_tooltip_text("Voice input (F12)")
        self.voice_button.connect('clicked', self._on_voice_toggle)

        # TTS toggle button
        self.tts_button = Gtk.Button(label="TTS")
        self.tts_button.add_css_class('tts-button')
        self.tts_button.add_css_class('active')  # On by default
        self.tts_button.set_tooltip_text("Toggle text-to-speech (Ctrl+T)")
        self.tts_button.connect('clicked', self._on_tts_toggle)

        # Send button
        self.send_button = Gtk.Button(label="Send")
        self.send_button.add_css_class('send-button')
        self.send_button.connect('clicked', self._on_send)

        input_container.append(self.input_entry)
        input_container.append(self.voice_button)
        input_container.append(self.tts_button)
        input_container.append(self.send_button)

        main_box.append(input_container)
        self.set_child(main_box)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Voice input - F12
        action_voice = Gio.SimpleAction.new("voice-input", None)
        action_voice.connect("activate", lambda a, p: self._on_voice_toggle(None))
        self.add_action(action_voice)
        self.app.set_accels_for_action("win.voice-input", ["F12"])

        # Clear chat - Ctrl+L
        action_clear = Gio.SimpleAction.new("clear-chat", None)
        action_clear.connect("activate", lambda a, p: self._on_clear())
        self.add_action(action_clear)
        self.app.set_accels_for_action("win.clear-chat", ["<Control>l"])

        # Toggle TTS - Ctrl+T
        action_tts = Gio.SimpleAction.new("toggle-tts", None)
        action_tts.connect("activate", lambda a, p: self._on_tts_toggle(None))
        self.add_action(action_tts)
        self.app.set_accels_for_action("win.toggle-tts", ["<Control>t"])

        # Cancel recording - Escape
        action_cancel = Gio.SimpleAction.new("cancel-recording", None)
        action_cancel.connect("activate", lambda a, p: self._on_cancel_recording())
        self.add_action(action_cancel)
        self.app.set_accels_for_action("win.cancel-recording", ["Escape"])

    def add_message(self, text: str, is_user: bool = False, is_system: bool = False, is_thinking: bool = False):
        """Add a message to the chat."""
        label = Gtk.Label(label=text)
        label.set_wrap(True)
        label.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        label.set_max_width_chars(50)
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

        # Process with Alice
        self.alice.process_async(text, self._on_response)

    def _on_response(self, response: dict):
        """Handle response (called from background thread)."""
        GLib.idle_add(self._display_response, response)

    def _display_response(self, response: dict):
        """Display response in chat (main thread)."""
        thinking = response.get('thinking', '')
        answer = response.get('response', '')

        # Display thinking if present (not read aloud)
        if thinking:
            self.add_message(f"[thinking]\n{thinking}", is_thinking=True)

        # Display answer
        self.add_message(answer, is_user=False)
        self._set_input_sensitive(True)
        self.input_entry.grab_focus()

        # Only speak the answer, not the thinking
        if self.tts_enabled and answer:
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

    def _on_load_reference(self, widget):
        """Open file chooser to load a reference document."""
        dialog = Gtk.FileChooserDialog(
            title="Load Reference Document",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Load", Gtk.ResponseType.ACCEPT)

        # Add file filters
        filter_all = Gtk.FileFilter()
        filter_all.set_name("Supported files")
        filter_all.add_pattern("*.pdf")
        filter_all.add_pattern("*.txt")
        filter_all.add_pattern("*.md")
        filter_all.add_pattern("*.json")
        filter_all.add_pattern("*.py")
        filter_all.add_pattern("*.sh")
        filter_all.add_pattern("*.png")
        filter_all.add_pattern("*.jpg")
        filter_all.add_pattern("*.jpeg")
        dialog.add_filter(filter_all)

        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF documents")
        filter_pdf.add_pattern("*.pdf")
        dialog.add_filter(filter_pdf)

        filter_text = Gtk.FileFilter()
        filter_text.set_name("Text files")
        filter_text.add_pattern("*.txt")
        filter_text.add_pattern("*.md")
        dialog.add_filter(filter_text)

        dialog.connect("response", self._on_reference_file_selected)
        dialog.present()

    def _on_reference_file_selected(self, dialog, response):
        """Handle reference file selection."""
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                file_path = file.get_path()
                success, message = self.alice.load_session_document(file_path)
                if success:
                    self.add_message(f"Loaded: {message}", is_system=True)
                    self._update_session_docs_label()
                else:
                    self.add_message(f"Failed to load: {message}", is_system=True)
        dialog.destroy()

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
        """Open dialog to add permanent knowledge."""
        dialog = Gtk.Dialog(
            title="Add Knowledge",
            transient_for=self,
            modal=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(400, 300)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(10)
        content.set_margin_end(10)

        # Title entry
        title_label = Gtk.Label(label="Title (e.g., 'pacman commands')")
        title_label.set_xalign(0)
        content.append(title_label)

        self.knowledge_title = Gtk.Entry()
        self.knowledge_title.set_placeholder_text("Short title...")
        content.append(self.knowledge_title)

        # Category combo
        cat_label = Gtk.Label(label="Category")
        cat_label.set_xalign(0)
        content.append(cat_label)

        self.knowledge_category = Gtk.ComboBoxText()
        self.knowledge_category.append_text("general")
        self.knowledge_category.append_text("arch-linux")
        self.knowledge_category.append_text("commands")
        self.knowledge_category.append_text("coding")
        self.knowledge_category.append_text("hardware")
        self.knowledge_category.append_text("other")
        self.knowledge_category.set_active(0)
        content.append(self.knowledge_category)

        # Content text view
        content_label = Gtk.Label(label="Content")
        content_label.set_xalign(0)
        content.append(content_label)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(100)

        self.knowledge_content = Gtk.TextView()
        self.knowledge_content.set_wrap_mode(Gtk.WrapMode.WORD)
        self.knowledge_content.get_buffer().set_text("")
        scrolled.set_child(self.knowledge_content)
        content.append(scrolled)

        # Load from file button
        load_btn = Gtk.Button(label="Load from file...")
        load_btn.connect('clicked', self._on_load_knowledge_file)
        content.append(load_btn)

        dialog.connect("response", self._on_knowledge_dialog_response)
        dialog.present()

    def _on_load_knowledge_file(self, widget):
        """Load knowledge content from a file."""
        dialog = Gtk.FileChooserDialog(
            title="Load Knowledge File",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Load", Gtk.ResponseType.ACCEPT)

        filter_text = Gtk.FileFilter()
        filter_text.set_name("Text files")
        filter_text.add_pattern("*.txt")
        filter_text.add_pattern("*.md")
        dialog.add_filter(filter_text)

        dialog.connect("response", self._on_knowledge_file_selected)
        dialog.present()

    def _on_knowledge_file_selected(self, dialog, response):
        """Handle knowledge file selection."""
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                file_path = file.get_path()
                try:
                    content = Path(file_path).read_text()
                    self.knowledge_content.get_buffer().set_text(content)
                    # Auto-fill title from filename if empty
                    if not self.knowledge_title.get_text():
                        self.knowledge_title.set_text(Path(file_path).stem)
                except Exception as e:
                    self.add_message(f"Error reading file: {e}", is_system=True)
        dialog.destroy()

    def _on_knowledge_dialog_response(self, dialog, response):
        """Handle knowledge dialog response."""
        if response == Gtk.ResponseType.ACCEPT:
            title = self.knowledge_title.get_text().strip()
            category = self.knowledge_category.get_active_text()
            buffer = self.knowledge_content.get_buffer()
            content = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

            if title and content:
                self.alice.add_knowledge(title, content, category)
                self.add_message(f"Saved knowledge: '{title}' [{category}]", is_system=True)
            else:
                self.add_message("Need both title and content to save knowledge.", is_system=True)
        dialog.destroy()
