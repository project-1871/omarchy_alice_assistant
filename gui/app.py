"""Alice GTK4 Application."""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')

from gi.repository import Gtk, Gdk, Gio
import os


class AliceApp(Gtk.Application):
    """Main GTK4 application."""

    def __init__(self):
        super().__init__(
            application_id='com.local.alice',
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.window = None

    def do_startup(self):
        """Called when the application starts."""
        Gtk.Application.do_startup(self)
        self._load_css()

    def do_activate(self):
        """Called when the application is activated."""
        if not self.window:
            from .window import MainWindow
            self.window = MainWindow(self)
        self.window.present()

    def _load_css(self):
        """Load CSS styling."""
        css_provider = Gtk.CssProvider()

        css_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'style.css'
        )

        if os.path.exists(css_path):
            css_provider.load_from_path(css_path)

            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
