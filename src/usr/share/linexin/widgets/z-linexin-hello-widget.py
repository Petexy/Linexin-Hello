#!/usr/bin/env python3
import gi
import gettext
import locale
import os
import subprocess
import threading
import webbrowser
from typing import Any

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Graphene", "1.0")
from gi.repository import Gtk, Adw, GLib, Pango, Gdk, Graphene # type: ignore # pylint: disable=import-error

APP_NAME = "linexin-hello"
LOCALE_DIR = os.path.abspath("/usr/share/locale")
locale.setlocale(locale.LC_ALL, '')
locale.bindtextdomain(APP_NAME, LOCALE_DIR)
gettext.bindtextdomain(APP_NAME, LOCALE_DIR)
gettext.textdomain(APP_NAME)
_ = gettext.gettext

# sudo_manager is injected at runtime by the widget loader
sudo_manager: Any = None
translate_dialog: Any = None  # Injected by linexin-center at runtime

# App icon directory
HELLO_ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hello-icons")

# Layout breakpoint for switching from sidebar to stacked content.
COMPACT_BREAKPOINT = 1100

# Display-name markers for the Experimental section.
EXPERIMENTAL_MARKERS = ("(beta)", "(alpha)", "(experimental)")
LOGO_BASE_SIZE = 88.0
LOGO_HOVER_SIZE = 96.0
LOGO_PRESS_SIZE = 78.0
LOGO_SHELL_SIZE = 112
LOGO_EASING = 0.20

# Welcome-section links
QUICK_LINKS = [
    {
        "label": "Source Code",
        "description": "Browse and contribute to Linexin on GitHub",
        "icon": "application-x-addon-symbolic",
        "url": "https://github.com/Petexy/Linexin",
    },
    {
        "label": "Report a Bug",
        "description": "Help us improve by reporting issues",
        "icon": "dialog-warning-symbolic",
        "url": "https://github.com/Petexy/Linexin/issues/new",
    },
    {
        "label": "Donate",
        "description": "Support the development of Linexin",
        "icon": "emblem-favorite-symbolic",
        "url": "https://paypal.me/Petexy",
    },
]

APP_CATALOG = [
    {
        "name": "Linexin Package Manager",
        "description": "Modern graphical package manager for Linexin",
        "icon_file": "linpama.svg",
        "icon_name": "system-file-manager-symbolic",
        "package": "linpama",
    },
    {
        "name": "Desktop Presets",
        "description": "A Linexin Center widget for managing desktop presets for both GNOME and KDE Plasma",
        "icon_file": "desktop-presets.svg",
        "icon_name": "multimedia-audio-player-symbolic",
        "package": "linexin-desktop-presets",
    },
    {
        "name": "Steam",
        "description": "The ultimate destination for playing, discussing, and creating games",
        "icon_file": "steam.png",
        "icon_name": "applications-games-symbolic",
        "package": "steam",
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
        "name": "Phone Mirror",
        "description": "A phone screen mirror app for Android.",
        "icon_file": "specula.svg",
        "icon_name": "web-browser-symbolic",
        "package": "specula",
        "new": True,
    },
    {
        "name": "Alexy Assistant",
        "description": "An AI-powered virtual assistant for your desktop",
        "icon_file": "alexy-assistant.svg",
        "icon_name": "web-browser-symbolic",
        "package": "alexy-ai",
    },
    {
        "name": "Package Converter (Experimental)",
        "description": "An experimental tool for converting other packages formats to be Arch-based",
        "icon_file": "linpaco.svg",
        "icon_name": "image-viewer-symbolic",
        "package": "linpaco",
    },
]

# Highlighted New-section styling.
_CSS = """
.linexin-new-section {
    background-color: alpha(@accent_bg_color, 0.08);
    border: 1px solid alpha(@accent_bg_color, 0.30);
    border-radius: 14px;
    padding: 10px;
}
.linexin-new-card {
    border: 1px solid alpha(@accent_bg_color, 0.45);
}
.linexin-app-grid > flowboxchild {
    border-radius: 12px;
    padding: 0;
}
.linexin-app-grid > flowboxchild:hover {
    border-radius: 12px;
}
.linexin-app-card {
    border-radius: 12px;
}
.linexin-new-badge {
    background-color: @accent_bg_color;
    color: @accent_fg_color;
    border-radius: 9999px;
    padding: 1px 9px;
    font-size: 0.68em;
    font-weight: 800;
}
.linexin-card-action {
    border-radius: 9999px;
    padding-left: 14px;
    padding-right: 14px;
}
"""
_CSS_LOADED = False


def _ensure_css():
    """Install the custom CSS for the widget once per display."""
    global _CSS_LOADED
    if _CSS_LOADED:
        return
    display = Gdk.Display.get_default()
    if display is None:
        return
    provider = Gtk.CssProvider()
    if hasattr(provider, "load_from_string"):
        provider.load_from_string(_CSS)
    else:  # GTK < 4.12 fallback
        provider.load_from_data(_CSS.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _CSS_LOADED = True


def _is_experimental(app):
    """True if the app's display name carries a (Beta)/(Alpha)/(Experimental) marker."""
    name = app.get("name", "").lower()
    return any(marker in name for marker in EXPERIMENTAL_MARKERS)


def _get_installed_packages():
    """Return the set of explicitly query-able installed packages via pacman."""
    try:
        result = subprocess.run(
            ["pacman", "-Qq"], capture_output=True, text=True
        )
        if result.returncode == 0:
            return set(result.stdout.split())
    except Exception:
        pass
    return set()


class _ScaleBin(Gtk.Widget):
    """Transparent single-child container that can draw its child at a scale
    factor around its centre. Used to scale the body during layout transitions
    (GtkWidget has no scale property of its own). Scaling happens at paint time
    only, so the child keeps its full allocation and nothing below it reflows."""

    def __init__(self):
        super().__init__()
        self._child = None
        self._scale = 1.0

    def set_child(self, child):
        if child is self._child:
            return
        if self._child is not None:
            self._child.unparent()
        self._child = child
        if child is not None:
            child.set_parent(self)

    def set_scale(self, scale):
        if scale != self._scale:
            self._scale = scale
            self.queue_draw()

    def do_measure(self, orientation, for_size):
        if self._child is None:
            return (0, 0, -1, -1)
        return self._child.measure(orientation, for_size)

    def do_size_allocate(self, width, height, baseline):
        if self._child is not None:
            self._child.allocate(width, height, baseline, None)

    def do_snapshot(self, snapshot):
        if self._child is None:
            return
        if self._scale == 1.0:
            self.snapshot_child(self._child, snapshot)
            return
        cx = self.get_width() * 0.5
        cy = self.get_height() * 0.5
        snapshot.save()
        snapshot.translate(Graphene.Point().init(cx, cy))
        snapshot.scale(self._scale, self._scale)
        snapshot.translate(Graphene.Point().init(-cx, -cy))
        self.snapshot_child(self._child, snapshot)
        snapshot.restore()

    def do_dispose(self):
        if self._child is not None:
            self._child.unparent()
            self._child = None
        Gtk.Widget.do_dispose(self)


class LinexinHelloWidget(Gtk.Box):
    def __init__(self, hide_sidebar=False, window=None, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.widgetname = "Linexin Hello"
        self.widgeticon = "/usr/share/icons/linexin-hello.png"
        self.widget_id = "linexin_hello"
        self.set_margin_top(18)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.window = window
        self.hide_sidebar = hide_sidebar
        self.user_password = None
        self._download_buttons = {}
        self._spinner_map = {}
        # Left-column app grids.
        self._left_grids = []
        self._is_compact = False
        # Running crossfade animation for the compact/wide transition, if any.
        self._fade_anim = None
        self._relayout_pending = False
        self._map_handler_id = 0
        self._logo_shell = None
        self._logo_image = None
        self._logo_size = LOGO_BASE_SIZE
        self._logo_target_size = LOGO_BASE_SIZE
        self._logo_hovered = False
        self._logo_pressed = False
        self._logo_tick_id = 0
        _ensure_css()
        self._setup_ui()

    def _setup_ui(self):
        """Build the Hello screen UI inside a responsive, scrollable container."""
        # Responsive container for wide and compact arrangements.
        breakpoint_bin = Adw.BreakpointBin()
        breakpoint_bin.set_size_request(360, 360)
        breakpoint_bin.set_vexpand(True)
        self._breakpoint_bin = breakpoint_bin

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        # Content width limit for wide displays.
        clamp = Adw.Clamp()
        clamp.set_maximum_size(1300)
        clamp.set_tightening_threshold(1000)

        scroll_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        # Hero header
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero.set_halign(Gtk.Align.CENTER)
        hero.set_margin_top(8)
        hero.set_margin_bottom(8)

        logo_path = os.path.join(HELLO_ICONS_DIR, "linexin-logo.png")
        if os.path.exists(logo_path):
            welcome_icon = Gtk.Image.new_from_file(logo_path)
        else:
            welcome_icon = Gtk.Image.new_from_icon_name("start-here-symbolic")
        welcome_icon.set_pixel_size(int(LOGO_BASE_SIZE))
        welcome_icon.set_halign(Gtk.Align.CENTER)
        welcome_icon.set_valign(Gtk.Align.CENTER)

        logo_shell = Gtk.Overlay()
        logo_shell.set_halign(Gtk.Align.CENTER)
        logo_shell.set_valign(Gtk.Align.CENTER)
        logo_shell.set_size_request(LOGO_SHELL_SIZE, LOGO_SHELL_SIZE)
        logo_shell.set_child(welcome_icon)
        self._setup_logo_interaction(logo_shell, welcome_icon)
        hero.append(logo_shell)

        title = Gtk.Label(label=_("Welcome to Linexin"))
        title.add_css_class("title-1")
        hero.append(title)

        subtitle = Gtk.Label(label=_("Discover apps built for your system"))
        subtitle.add_css_class("dim-label")
        hero.append(subtitle)

        scroll_content.append(hero)

        # Main app and link area.
        self._body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        self._body.set_valign(Gtk.Align.START)

        # Wide-layout columns.
        self._left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self._left_col.set_hexpand(True)
        self._left_col.set_valign(Gtk.Align.START)
        self._right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._right_col.set_size_request(290, -1)
        self._right_col.set_valign(Gtk.Align.START)
        # Fixed sidebar width keeps the app grid stable.
        self._right_col.set_hexpand(False)

        # Content blocks reparented by _apply_layout().
        self._sections_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self._new_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._links_container = self._build_quick_links()

        # Wrap the body so it can be scaled during the transition animation.
        self._scale_bin = _ScaleBin()
        self._scale_bin.set_child(self._body)
        scroll_content.append(self._scale_bin)

        # Footer
        footer = Gtk.Label(label=_("Thank you for choosing Linexin ❤️"))
        footer.add_css_class("dim-label")
        footer.set_halign(Gtk.Align.CENTER)
        footer.set_margin_top(16)
        footer.set_margin_bottom(8)
        scroll_content.append(footer)

        clamp.set_child(scroll_content)
        scrolled.set_child(clamp)
        breakpoint_bin.set_child(scrolled)

        # Breakpoint state drives _apply_layout().
        compact = Adw.Breakpoint.new(
            Adw.BreakpointCondition.parse(f"max-width: {COMPACT_BREAKPOINT}px")
        )
        breakpoint_bin.add_breakpoint(compact)
        breakpoint_bin.connect(
            "notify::current-breakpoint", self._on_breakpoint_changed
        )

        self.append(breakpoint_bin)

        # Initial layout and section content.
        self._layout_compact = None
        self._apply_layout()
        self._rebuild_app_sections()

    def _setup_logo_interaction(self, logo_shell, logo_image):
        """Attach hover and press animation behavior to the hero logo."""
        self._logo_shell = logo_shell
        self._logo_image = logo_image

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._on_logo_enter)
        motion.connect("leave", self._on_logo_leave)
        logo_shell.add_controller(motion)

        click = Gtk.GestureClick()
        click.set_button(0)
        click.connect("pressed", self._on_logo_pressed)
        click.connect("released", self._on_logo_released)
        logo_shell.add_controller(click)

        self._start_logo_transition()

    def _start_logo_transition(self):
        if self._logo_tick_id or self._logo_shell is None:
            return
        self._logo_tick_id = self._logo_shell.add_tick_callback(self._animate_logo)

    def _set_logo_target(self):
        if self._logo_pressed:
            self._logo_target_size = LOGO_PRESS_SIZE
        elif self._logo_hovered:
            self._logo_target_size = LOGO_HOVER_SIZE
        else:
            self._logo_target_size = LOGO_BASE_SIZE

    def _on_logo_enter(self, controller, x, y):
        self._logo_hovered = True
        self._set_logo_target()
        self._start_logo_transition()

    def _on_logo_leave(self, controller):
        self._logo_hovered = False
        self._logo_pressed = False
        self._set_logo_target()
        self._start_logo_transition()

    def _on_logo_pressed(self, gesture, n_press, x, y):
        self._logo_pressed = True
        self._set_logo_target()
        self._start_logo_transition()

    def _on_logo_released(self, gesture, n_press, x, y):
        self._logo_pressed = False
        self._set_logo_target()
        self._start_logo_transition()

    def _animate_logo(self, widget, frame_clock, user_data=None):
        if self._logo_image is None:
            self._logo_tick_id = 0
            return False

        self._logo_size += (self._logo_target_size - self._logo_size) * LOGO_EASING
        self._logo_image.set_pixel_size(max(1, round(self._logo_size)))
        if abs(self._logo_target_size - self._logo_size) < 0.35:
            self._logo_size = self._logo_target_size
            self._logo_image.set_pixel_size(max(1, round(self._logo_size)))
            self._logo_tick_id = 0
            return False
        return True

    def _build_quick_links(self):
        """Build the Quick Links list as a self-contained, reparentable box."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_valign(Gtk.Align.START)

        label = Gtk.Label(label=_("Quick Links"))
        label.add_css_class("title-3")
        label.set_halign(Gtk.Align.START)
        label.set_margin_top(4)
        box.append(label)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")
        for link in QUICK_LINKS:
            row = Adw.ActionRow(title=_(link["label"]), subtitle=_(link["description"]))
            row.set_activatable(True)
            row.set_subtitle_lines(2)
            row.add_prefix(Gtk.Image.new_from_icon_name(link["icon"]))
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.connect("activated", self._on_link_activated, link["url"])
            listbox.append(row)
        box.append(listbox)
        return box

    def _apply_layout(self):
        """Arrange New / app sections / Quick Links for the current width.

        Wide: app sections on the left; New + Quick Links in the right sidebar.
        Compact: one column with New pinned on top and the links at the bottom.
        """
        compact = self._is_compact
        if self._layout_compact == compact:
            return
        self._layout_compact = compact

        # Detach reusable blocks before reparenting.
        for widget in (self._new_box, self._sections_box, self._links_container,
                       self._left_col, self._right_col):
            parent = widget.get_parent()
            if parent is not None:
                parent.remove(widget)
        child = self._body.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._body.remove(child)
            child = nxt

        if compact:
            self._body.set_orientation(Gtk.Orientation.VERTICAL)
            self._body.set_spacing(24)
            self._body.append(self._new_box)        # New section stays first.
            self._body.append(self._sections_box)
            self._body.append(self._links_container)
        else:
            self._body.set_orientation(Gtk.Orientation.HORIZONTAL)
            self._body.set_spacing(20)
            self._left_col.append(self._sections_box)
            self._right_col.append(self._new_box)
            self._right_col.append(self._links_container)
            self._body.append(self._left_col)
            self._body.append(self._right_col)

    def _on_breakpoint_changed(self, *args):
        """Crossfade between the compact and wide arrangements on a width change.

        Deferred to idle: starting the animation while the breakpoint bin is
        still allocating makes it complete instantly instead of playing."""
        self._is_compact = self._breakpoint_bin.get_current_breakpoint() is not None
        if not self._relayout_pending:
            self._relayout_pending = True
            GLib.idle_add(self._relayout_idle)

    def _relayout_idle(self):
        self._relayout_pending = False
        self._animate_relayout()
        return False

    def _animate_relayout(self):
        """Animate a compact/wide change with Material-3-Expressive motion: the
        old arrangement shrinks and fades out quickly, then the new one springs
        up to full size (with a gentle overshoot) as it fades in. The animations
        honour the system "reduce animations" setting (the swap is then instant).

        An off-screen widget has its animation skipped straight to the end, and
        the body can unmap for a moment mid-resize. So when the body is mapped,
        run exit-then-enter; when it is not, swap while hidden and spring the new
        arrangement in once it is back on screen."""
        if self._layout_compact == self._is_compact:
            return
        if (self._fade_anim is not None
                and self._fade_anim.get_state() == Adw.AnimationState.PLAYING):
            return
        if self._body.get_mapped():
            target = Adw.CallbackAnimationTarget.new(self._on_exit_value)
            anim = Adw.TimedAnimation.new(self._body, 1.0, 0.0, 110, target)
            anim.set_easing(Adw.Easing.EASE_IN_CUBIC)
            anim.connect("done", self._after_exit)
            self._fade_anim = anim
            anim.play()
        else:
            self._swap_layout()
            self._on_enter_value(0.0)
            if self._map_handler_id == 0:
                self._map_handler_id = self._body.connect("map", self._on_body_remapped)

    def _swap_layout(self):
        self._apply_layout()
        for grid in self._left_grids:
            self._apply_grid_columns(grid)

    def _after_exit(self, anim):
        self._swap_layout()
        self._play_spring_enter()

    def _play_spring_enter(self):
        target = Adw.CallbackAnimationTarget.new(self._on_enter_value)
        # Underdamped spring -> an expressive overshoot before settling.
        params = Adw.SpringParams.new(0.62, 1.0, 300.0)
        anim = Adw.SpringAnimation.new(self._body, 0.0, 1.0, params, target)
        anim.set_epsilon(0.001)
        anim.connect("done", self._after_enter)
        self._fade_anim = anim
        anim.play()

    def _after_enter(self, anim):
        self._fade_anim = None
        self._body.set_opacity(1.0)
        self._scale_bin.set_scale(1.0)
        # A width change during the animation can leave the arrangement stale.
        if self._layout_compact != self._is_compact:
            self._animate_relayout()

    def _on_exit_value(self, value, *user_data):
        # value 1 -> 0: fade out and shrink slightly toward the centre.
        self._body.set_opacity(value)
        self._scale_bin.set_scale(0.96 + 0.04 * value)

    def _on_enter_value(self, value, *user_data):
        # value 0 -> 1 (may overshoot): fade in and grow up to full size.
        self._body.set_opacity(max(0.0, min(1.0, value)))
        self._scale_bin.set_scale(0.90 + 0.10 * value)

    def _on_body_remapped(self, *args):
        if self._map_handler_id:
            self._body.disconnect(self._map_handler_id)
            self._map_handler_id = 0
        # Spring in on idle so the clock is running before the animation starts.
        GLib.idle_add(self._spring_enter_remapped)

    def _spring_enter_remapped(self):
        if self._body.get_mapped():
            self._play_spring_enter()
        else:
            self._body.set_opacity(1.0)
            self._scale_bin.set_scale(1.0)
        return False

    # App sections

    def _rebuild_app_sections(self):
        """(Re)build the New / Recommended / Installed / Experimental sections."""
        # Clear section containers.
        for container in (self._sections_box, self._new_box):
            child = container.get_first_child()
            while child is not None:
                nxt = child.get_next_sibling()
                container.remove(child)
                child = nxt
        self._download_buttons.clear()
        self._spinner_map.clear()
        self._left_grids = []

        installed_set = _get_installed_packages()

        new_apps, recommended_apps, installed_apps, experimental_apps = [], [], [], []
        for app in APP_CATALOG:
            # Experimental markers override installed/recommended grouping.
            if _is_experimental(app):
                experimental_apps.append(app)
            elif app["package"] in installed_set:
                installed_apps.append(app)
            elif app.get("new"):
                new_apps.append(app)
            else:
                recommended_apps.append(app)

        # Keep the New highlight short; overflow remains in Recommended.
        if len(new_apps) > 2:
            recommended_apps = new_apps[2:] + recommended_apps
            new_apps = new_apps[:2]
        if new_apps:
            self._new_box.append(self._create_section(
                _("New"),
                _("Just landed - be among the first to try it!"),
                new_apps, installed_set, highlighted=True, sidebar=True,
            ))

        # Left-column section order.
        if recommended_apps:
            self._sections_box.append(self._create_section(
                _("Recommended Apps"),
                _("Handpicked apps for your Linexin system"),
                recommended_apps, installed_set,
            ))
        if installed_apps:
            self._sections_box.append(self._create_section(
                _("Installed"),
                _("Apps already on your system"),
                installed_apps, installed_set,
            ))
        if experimental_apps:
            self._sections_box.append(self._create_section(
                _("Experimental"),
                _("Early-stage apps that may be unstable"),
                experimental_apps, installed_set,
            ))

    def _create_section(self, title, subtitle, apps, installed_set,
                        highlighted=False, sidebar=False):
        """Build a titled section (header + card grid) for a group of apps."""
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.set_halign(Gtk.Align.FILL)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title_box.set_hexpand(True)
        title_label = Gtk.Label(label=title)
        title_label.add_css_class("title-3")
        title_label.set_halign(Gtk.Align.START)
        if highlighted:
            title_label.add_css_class("accent")
        title_box.append(title_label)

        if subtitle:
            sub = Gtk.Label(label=subtitle)
            sub.add_css_class("dim-label")
            sub.add_css_class("caption")
            sub.set_halign(Gtk.Align.START)
            sub.set_xalign(0)
            sub.set_ellipsize(Pango.EllipsizeMode.END)
            title_box.append(sub)
        header.append(title_box)

        if highlighted:
            badge = Gtk.Label(label=_("NEW"))
            badge.add_css_class("linexin-new-badge")
            badge.set_valign(Gtk.Align.CENTER)
            header.append(badge)

        section.append(header)

        grid = self._create_app_grid(apps, installed_set, highlighted, sidebar=sidebar)
        if highlighted:
            wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            wrapper.add_css_class("linexin-new-section")
            wrapper.append(grid)
            section.append(wrapper)
        else:
            section.append(grid)
        return section

    def _create_app_grid(self, apps, installed_set, highlighted=False, sidebar=False):
        """Build a FlowBox of app cards.

        Sidebar grids (the "New" highlight) are a single column. Left-column
        grids re-flow: two columns in wide mode so installed lists fill the row
        instead of one entry per line, one column when compact.
        """
        grid = Gtk.FlowBox()
        grid.set_valign(Gtk.Align.START)
        grid.set_column_spacing(12)
        grid.set_row_spacing(12)
        grid.set_homogeneous(True)
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.add_css_class("linexin-app-grid")
        for app in apps:
            card = self._create_app_card(
                app, app["package"] in installed_set, highlighted
            )
            grid.append(card)
        if sidebar:
            grid.set_max_children_per_line(1)
            grid.set_min_children_per_line(1)
        else:
            self._left_grids.append(grid)
            self._apply_grid_columns(grid)
        return grid

    def _apply_grid_columns(self, grid):
        """Choose the column count for a left-column grid:
          * a lone card always spans the full width (never a half-empty row);
          * wide mode forces two columns so installed lists fill the row;
          * compact mode reflows naturally between one and two columns.
        """
        count = 0
        child = grid.get_first_child()
        while child is not None:
            count += 1
            child = child.get_next_sibling()
        if count <= 1:
            grid.set_min_children_per_line(1)
            grid.set_max_children_per_line(1)
        elif self._is_compact:
            grid.set_min_children_per_line(1)
            grid.set_max_children_per_line(2)
        else:
            grid.set_min_children_per_line(2)
            grid.set_max_children_per_line(2)

    def _create_app_card(self, app_info, installed, highlighted=False):
        """Create a GNOME Software-style compact card with icon, text, and install button."""
        pkg = app_info["package"]

        # Card layout: icon, text, action.
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        card.add_css_class("card")
        card.add_css_class("linexin-app-card")
        card.add_css_class("activatable")
        # Fixed height keeps rows uniform.
        card.set_size_request(-1, 72)
        # Tooltip preserves text hidden by ellipsizing.
        card.set_tooltip_text(f"{_(app_info['name'])}\n{_(app_info.get('description', ''))}")
        if highlighted:
            card.add_css_class("linexin-new-card")

        # App icon lookup.
        icon_file = app_info.get("icon_file", "")
        icon_path = ""
        if icon_file:
            # Exact filename first, alternate extensions second.
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

        # Action area.
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
            btn.add_css_class("linexin-card-action")
            btn.connect("clicked", self._on_remove_clicked, app_info)
        else:
            btn = Gtk.Button(label=_("Install"))
            btn.add_css_class("suggested-action")
            btn.add_css_class("linexin-card-action")
            btn.connect("clicked", self._on_install_clicked, app_info)

        btn_box.append(btn)
        card.append(btn_box)
        self._download_buttons[pkg] = btn
        return card

    # Link handling

    def _on_link_activated(self, row, url):
        """Open the given URL in the default browser."""
        webbrowser.open(url)

    # Password prompt

    def _prompt_password(self, success_callback, message):
        """Prompt for the sudo password using Adw.MessageDialog."""
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
                    if translate_dialog:
                        translate_dialog(err)
                    err.present()
            dlg.close()

        dialog.connect("response", on_response)

        def on_entry_activate(widget):
            dialog.response("authenticate")

        entry.connect("activate", on_entry_activate)
        if translate_dialog:
            translate_dialog(dialog)
        dialog.present()

    # Installation logic

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
        spinner = self._spinner_map.get(pkg)
        if spinner:
            spinner.stop()
            spinner.set_visible(False)

        if success:
            # Refresh Linexin Center's widget list.
            if self.window and hasattr(self.window, 'refresh_widgets'):
                self.window.refresh_widgets()
            # Move the app into the Installed section.
            self._rebuild_app_sections()
        else:
            btn = self._download_buttons.get(pkg)
            if btn is not None:
                btn.set_label(_("Failed"))
                btn.add_css_class("destructive-action")
                btn.remove_css_class("suggested-action")
                # Restore retry state after a short delay.
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

    # Removal logic

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
        spinner = self._spinner_map.get(pkg)
        if spinner:
            spinner.stop()
            spinner.set_visible(False)

        if success:
            # Refresh Linexin Center's widget list.
            if self.window and hasattr(self.window, 'refresh_widgets'):
                self.window.refresh_widgets()
            # Move the app out of the Installed section.
            self._rebuild_app_sections()
        else:
            btn = self._download_buttons.get(pkg)
            if btn is not None:
                btn.set_label(_("Failed"))
                # Restore retry state after a short delay.
                GLib.timeout_add(3000, self._reset_failed_remove_button, pkg, btn)
            if error_msg:
                print(f"Removal failed for {pkg}: {error_msg}")
        return False

    def _reset_failed_remove_button(self, pkg, btn):
        """Reset a failed remove button back to Remove state."""
        btn.set_label(_("Remove"))
        btn.set_sensitive(True)
        return False


if __name__ == "__main__":
    # Standalone preview harness.
    class _DummySudo:
        user_password = None
        wrapper_path = "/bin/true"

        def validate_password(self, pwd):
            return True

        def set_password(self, pwd):
            self.user_password = pwd

        def start_privileged_session(self):
            pass

        def stop_privileged_session(self):
            pass

        def get_env(self):
            return os.environ.copy()

    sudo_manager = _DummySudo()

    class TestWindow(Gtk.ApplicationWindow):
        def __init__(self, app):
            super().__init__(application=app)
            self.set_title("Linexin Hello Widget")
            self.set_default_size(1100, 820)
            widget = LinexinHelloWidget(hide_sidebar=True, window=self)
            self.set_child(widget)

    class TestApp(Adw.Application):
        def do_activate(self):
            TestWindow(self).present()

    TestApp().run()
