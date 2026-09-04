"""
Window-manager hints for tiling WMs (Hyprland, sway, i3).
GNOME floats dialogs automatically; tiling WMs need the explicit
_NET_WM_WINDOW_TYPE_DIALOG hint or they tile every Toplevel and
ignore geometry(). Tk exposes this via attributes("-type", ...) on
X11/XWayland only, so every call is best-effort.
"""


def mark_dialog(win, parent=None) -> None:
    """Make a Toplevel float on tiling WMs: transient + dialog type hint.

    Call right after creating the Toplevel, before it is mapped.
    """
    if parent is not None:
        try:
            win.transient(parent)
        except Exception:
            pass
    try:
        win.attributes("-type", "dialog")  # X11/XWayland only; no-op elsewhere
    except Exception:
        pass


def mark_splash(win) -> None:
    """Splash-screen type hint (floats + skips taskbar on tiling WMs)."""
    try:
        win.attributes("-type", "splash")
    except Exception:
        pass


def mark_popup(win, parent=None) -> None:
    """Popup/dropdown type hint (floats without decorations on tiling WMs)."""
    if parent is not None:
        try:
            win.transient(parent)
        except Exception:
            pass
    try:
        win.attributes("-type", "popup_menu")
    except Exception:
        pass
