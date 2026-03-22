#!/usr/bin/env python3
import gi
import gettext
import locale
import os
import subprocess
import threading
from typing import Any

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Pango # type: ignore # pylint: disable=import-error

APP_NAME = "linexin-hello"
LOCALE_DIR = os.path.abspath("/usr/share/locale")
locale.setlocale(locale.LC_ALL, '')
locale.bindtextdomain(APP_NAME, LOCALE_DIR)
gettext.bindtextdomain(APP_NAME, LOCALE_DIR)
gettext.textdomain(APP_NAME)
_ = gettext.gettext

# sudo_manager is injected at runtime by the widget loader
sudo_manager: Any = None

# Icon directory for hello widget app icons
HELLO_ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hello-icons")

# Real Arch repository packages — replace with Linexin apps later
APP_CATALOG = [
    {
        "name": "Alexy Assistant",
        "description": "An AI-powered virtual assistant for your desktop",
        "icon_file": "alexy-assistant.svg",
        "icon_name": "web-browser-symbolic",
        "package": "alexy-ai",
    },
    {
        "name": "Package Manager",
        "description": "Modern graphical package manager for Linexin",
        "icon_file": "linpama.svg",
        "icon_name": "system-file-manager-symbolic",
        "package": "linpama",
    },
    {
        "name": "DaVinci Installer",
        "description": "A Linexin Center widget for the DaVinci Resolve installation helper",
        "icon_file": "davinci-installer.png",
        "icon_name": "utilities-terminal-symbolic",
        "package": "davinci-installer",
    },
    {
        "name": "Affinity Installer",
        "description": "A Linexin Center widget for the Affinity suite installation helper",
        "icon_file": "affinity-installer.png",
        "icon_name": "utilities-terminal-symbolic",
        "package": "affinity-installer2",
    },
    {
        "name": "Desktop Presets",
        "description": "A Linexin Center widget for managing desktop presets for both GNOME and KDE Plasma",
        "icon_file": "desktop-presets.svg",
        "icon_name": "multimedia-audio-player-symbolic",
        "package": "linexin-desktop-presets",
    },
    {
        "name": "Package Converter",
        "description": "An experimental tool for converting other packages formats to be Arch-based",
        "icon_file": "linpaco.svg",
        "icon_name": "image-viewer-symbolic",
        "package": "linpaco",
    },
]


def _is_package_installed(package_name):
    """Check if an Arch package is installed via pacman."""
    try:
        result = subprocess.run(
            ["pacman", "-Qi", package_name],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


class LinexinHelloWidget(Gtk.Box):
    def __init__(self, hide_sidebar=False, window=None, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.widgetname = "Linexin Hello"
        self.widgeticon = "/usr/share/icons/linexin-hello.png"
        self.widget_id = "linexin_hello"
        self.set_margin_top(20)
        self.set_margin_bottom(50)
        self.set_margin_start(40)
        self.set_margin_end(40)
        self.window = window
        self.hide_sidebar = hide_sidebar
        self.user_password = None
        self._download_buttons = {}
        self._spinner_map = {}
        self._setup_ui()

    def _setup_ui(self):
        """Build the Hello screen UI."""
        # --- Hero header ---
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero.set_halign(Gtk.Align.CENTER)
        hero.set_margin_bottom(12)

        logo_path = os.path.join(HELLO_ICONS_DIR, "linexin-logo.png")
        if os.path.exists(logo_path):
            welcome_icon = Gtk.Image.new_from_file(logo_path)
        else:
            welcome_icon = Gtk.Image.new_from_icon_name("start-here-symbolic")
        welcome_icon.set_pixel_size(64)
        hero.append(welcome_icon)

        title = Gtk.Label(label=_("Welcome to Linexin"))
        title.add_css_class("title-1")
        hero.append(title)

        subtitle = Gtk.Label(label=_("Discover apps built for your system"))
        subtitle.add_css_class("dim-label")
        hero.append(subtitle)

        self.append(hero)

        # --- Separator ---
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        self.append(sep)

        # --- Scrollable app grid ---
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        self._grid = Gtk.FlowBox()
        self._grid.set_valign(Gtk.Align.START)
        self._grid.set_max_children_per_line(3)
        self._grid.set_min_children_per_line(2)
        self._grid.set_column_spacing(12)
        self._grid.set_row_spacing(12)
        self._grid.set_homogeneous(True)
        self._grid.set_selection_mode(Gtk.SelectionMode.NONE)

        for app_info in APP_CATALOG:
            card = self._create_app_card(app_info)
            self._grid.append(card)

        scrolled.set_child(self._grid)
        self.append(scrolled)

    def _create_app_card(self, app_info):
        """Create a GNOME Software-style compact card with icon, text, and install button."""
        pkg = app_info["package"]
        installed = _is_package_installed(pkg)

        # Single horizontal row: icon | text | button
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        card.add_css_class("card")

        # Load icon from hello-icons folder, fall back to symbolic icon name
        icon_file = app_info.get("icon_file", "")
        icon_path = ""
        if icon_file:
            # Try the exact filename first, then check alternate extensions
            candidate = os.path.join(HELLO_ICONS_DIR, icon_file)
            if os.path.exists(candidate):
                icon_path = candidate
            else:
                base = os.path.splitext(icon_file)[0]
                for ext in (".svg", ".png"):
                    alt = os.path.join(HELLO_ICONS_DIR, base + ext)
                    if os.path.exists(alt):
                        icon_path = alt
                        break
        if icon_path:
            icon = Gtk.Image.new_from_file(icon_path)
        else:
            icon = Gtk.Image.new_from_icon_name(
                app_info.get("icon_name", "application-x-addon-symbolic")
            )
        icon.set_pixel_size(36)
        icon.set_valign(Gtk.Align.CENTER)
        icon.set_margin_start(10)
        card.append(icon)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)
        text_box.set_margin_top(10)
        text_box.set_margin_bottom(10)

        name_label = Gtk.Label(label=_(app_info["name"]))
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.add_css_class("heading")
        text_box.append(name_label)

        desc_label = Gtk.Label(label=_(app_info.get("description", "")))
        desc_label.set_halign(Gtk.Align.START)
        desc_label.add_css_class("dim-label")
        desc_label.add_css_class("caption")
        desc_label.set_ellipsize(Pango.EllipsizeMode.END)
        desc_label.set_max_width_chars(22)
        desc_label.set_lines(2)
        desc_label.set_wrap(True)
        desc_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        text_box.append(desc_label)

        card.append(text_box)

        # Spinner + button on the right
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.set_valign(Gtk.Align.CENTER)
        btn_box.set_margin_end(10)

        spinner = Gtk.Spinner()
        spinner.set_visible(False)
        btn_box.append(spinner)
        self._spinner_map[pkg] = spinner

        if installed:
            btn = Gtk.Button(label=_("Remove"))
            btn.add_css_class("destructive-action")
            btn.add_css_class("pill")
            btn.connect("clicked", self._on_remove_clicked, app_info)
        else:
            btn = Gtk.Button(label=_("Install"))
            btn.add_css_class("suggested-action")
            btn.add_css_class("pill")
            btn.connect("clicked", self._on_install_clicked, app_info)

        btn_box.append(btn)
        card.append(btn_box)
        self._download_buttons[pkg] = btn
        return card

    # ---- Password prompt (mirrors Linexin Center pattern) ----

    def _prompt_password(self, success_callback, message):
        """Prompt user for sudo password using Adw.MessageDialog."""
        parent_window = self.window
        if parent_window is None:
            w = self.get_root()
            if isinstance(w, Gtk.Window):
                parent_window = w

        dialog = Adw.MessageDialog(
            heading=_("Authentication Required"),
            body=message,
            transient_for=parent_window,
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("authenticate", _("Authenticate"))
        dialog.set_response_appearance("authenticate", Adw.ResponseAppearance.SUGGESTED)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        entry = Gtk.PasswordEntry()
        entry.set_property("placeholder-text", _("Password"))
        box.append(entry)
        dialog.set_extra_child(box)

        def on_response(dlg, response):
            if response == "authenticate":
                pwd = entry.get_text()
                if pwd and sudo_manager.validate_password(pwd):
                    sudo_manager.set_password(pwd)
                    self.user_password = pwd
                    success_callback()
                else:
                    err = Adw.MessageDialog(
                        heading=_("Authentication Failed"),
                        body=_("Incorrect password."),
                        transient_for=parent_window,
                    )
                    err.add_response("ok", _("OK"))
                    err.connect("response", lambda d, r: d.close())
                    err.present()
            dlg.close()

        dialog.connect("response", on_response)

        def on_entry_activate(widget):
            dialog.response("authenticate")

        entry.connect("activate", on_entry_activate)
        dialog.present()

    # ---- Installation logic ----

    def _on_install_clicked(self, button, app_info):
        """Handle install button click — authenticate then install."""
        if not self.user_password or not sudo_manager.user_password:
            self.user_password = None
            self._prompt_password(
                lambda: self._start_install(button, app_info),
                _("Enter your password to install {}.").format(app_info["name"]),
            )
        else:
            self._start_install(button, app_info)

    def _start_install(self, button, app_info):
        """Begin the actual pacman installation in a background thread."""
        pkg = app_info["package"]
        button.set_sensitive(False)
        button.set_label(_("Installing..."))
        spinner = self._spinner_map.get(pkg)
        if spinner:
            spinner.set_visible(True)
            spinner.start()

        thread = threading.Thread(
            target=self._run_install, args=(pkg,), daemon=True
        )
        thread.start()

    def _run_install(self, pkg):
        """Run pacman -S in a background thread using wrapper_path."""
        success = False
        error_msg = ""
        try:
            sudo_manager.start_privileged_session()
            env = sudo_manager.get_env()
            process = subprocess.Popen(
                [sudo_manager.wrapper_path, "pacman", "-S", "--noconfirm", pkg],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            output = ""
            assert process.stdout is not None
            for line in iter(process.stdout.readline, ""):
                if line:
                    output += line
            process.stdout.close()
            return_code = process.wait()
            success = return_code == 0
            if not success:
                error_msg = output.strip()
        except Exception as e:
            error_msg = str(e)
        finally:
            sudo_manager.stop_privileged_session()

        GLib.idle_add(self._finish_install, pkg, success, error_msg)

    def _finish_install(self, pkg, success, error_msg):
        """Update the UI after installation completes."""
        btn = self._download_buttons.get(pkg)
        spinner = self._spinner_map.get(pkg)
        if spinner:
            spinner.stop()
            spinner.set_visible(False)

        if btn is None:
            return False

        if success:
            btn.set_label(_("Remove"))
            btn.remove_css_class("suggested-action")
            btn.add_css_class("destructive-action")
            btn.set_sensitive(True)
            # Reconnect to remove handler
            btn.disconnect_by_func(self._on_install_clicked)
            # Find app_info for this pkg
            app_info = next((a for a in APP_CATALOG if a["package"] == pkg), None)
            if app_info:
                btn.connect("clicked", self._on_remove_clicked, app_info)
            # Refresh Linexin Center's widget list to pick up newly installed widgets
            if self.window and hasattr(self.window, 'refresh_widgets'):
                self.window.refresh_widgets()
        else:
            btn.set_label(_("Failed"))
            btn.add_css_class("destructive-action")
            btn.remove_css_class("suggested-action")
            # Re-enable after a delay so the user can retry
            GLib.timeout_add(3000, self._reset_failed_button, pkg, btn)
            if error_msg:
                print(f"Installation failed for {pkg}: {error_msg}")
        return False

    def _reset_failed_button(self, pkg, btn):
        """Reset a failed button back to installable state."""
        btn.set_label(_("Install"))
        btn.set_sensitive(True)
        btn.remove_css_class("destructive-action")
        btn.add_css_class("suggested-action")
        return False

    # ---- Removal logic ----

    def _on_remove_clicked(self, button, app_info):
        """Handle remove button click — authenticate then remove."""
        if not self.user_password or not sudo_manager.user_password:
            self.user_password = None
            self._prompt_password(
                lambda: self._start_remove(button, app_info),
                _("Enter your password to remove {}.").format(app_info["name"]),
            )
        else:
            self._start_remove(button, app_info)

    def _start_remove(self, button, app_info):
        """Begin the actual pacman removal in a background thread."""
        pkg = app_info["package"]
        button.set_sensitive(False)
        button.set_label(_("Removing..."))
        spinner = self._spinner_map.get(pkg)
        if spinner:
            spinner.set_visible(True)
            spinner.start()

        thread = threading.Thread(
            target=self._run_remove, args=(pkg,), daemon=True
        )
        thread.start()

    def _run_remove(self, pkg):
        """Run pacman -R in a background thread using wrapper_path."""
        success = False
        error_msg = ""
        try:
            sudo_manager.start_privileged_session()
            env = sudo_manager.get_env()
            process = subprocess.Popen(
                [sudo_manager.wrapper_path, "pacman", "-R", "--noconfirm", pkg],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            output = ""
            assert process.stdout is not None
            for line in iter(process.stdout.readline, ""):
                if line:
                    output += line
            process.stdout.close()
            return_code = process.wait()
            success = return_code == 0
            if not success:
                error_msg = output.strip()
        except Exception as e:
            error_msg = str(e)
        finally:
            sudo_manager.stop_privileged_session()

        GLib.idle_add(self._finish_remove, pkg, success, error_msg)

    def _finish_remove(self, pkg, success, error_msg):
        """Update the UI after removal completes."""
        btn = self._download_buttons.get(pkg)
        spinner = self._spinner_map.get(pkg)
        if spinner:
            spinner.stop()
            spinner.set_visible(False)

        if btn is None:
            return False

        if success:
            btn.set_label(_("Install"))
            btn.remove_css_class("destructive-action")
            btn.add_css_class("suggested-action")
            btn.set_sensitive(True)
            # Reconnect to install handler
            btn.disconnect_by_func(self._on_remove_clicked)
            app_info = next((a for a in APP_CATALOG if a["package"] == pkg), None)
            if app_info:
                btn.connect("clicked", self._on_install_clicked, app_info)
        else:
            btn.set_label(_("Failed"))
            btn.set_sensitive(True)
            # Re-enable after a delay so the user can retry
            GLib.timeout_add(3000, self._reset_failed_remove_button, pkg, btn)
            if error_msg:
                print(f"Removal failed for {pkg}: {error_msg}")
        return False

    def _reset_failed_remove_button(self, pkg, btn):
        """Reset a failed remove button back to Remove state."""
        btn.set_label(_("Remove"))
        btn.set_sensitive(True)
        return False
