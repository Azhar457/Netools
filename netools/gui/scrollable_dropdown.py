"""
Modern CustomTkinter Scrollable & Searchable Dropdown Popup.
Prevents dropdown menus with 50+ items from overflowing the screen.
Supports keyboard search, mouse wheel scrolling on Linux/Win/Mac, and click-to-select.
"""

import sys
import time
import tkinter as tk
from typing import Any, Callable, List, Optional, Tuple

import customtkinter as ctk

from netools.gui.theme import (
    Fonts,
    ThemeManager,
)


class CTkScrollableDropdown:
    def __init__(
        self,
        attach_widget: Any,
        values: List[str],
        command: Optional[Callable[[str], None]] = None,
        variable: Optional[tk.StringVar] = None,
        max_height: int = 280,
        width: Optional[int] = None,
        searchable: bool = True,
        placeholder_text: str = "🔍 Search presets...",
    ):
        self.widget = attach_widget
        self.values = list(values)
        self.command = command
        self.variable = variable
        self.max_height = max_height
        self.custom_width = width
        self.searchable = searchable
        self.placeholder_text = placeholder_text

        self.buttons: List[ctk.CTkButton] = []
        self._render_limit: int = 40
        self._last_rendered: Optional[List[str]] = None
        self._search_after_id: Optional[str] = None
        self.toplevel: Optional[ctk.CTkToplevel] = None
        self.scroll_frame: Optional[ctk.CTkScrollableFrame] = None
        self.search_entry: Optional[ctk.CTkEntry] = None
        self._click_binding_id: Optional[str] = None
        self._open_ts: float = 0.0
        self._geo: Tuple[int, int, int, int] = (0, 0, 0, 0)

        # Route CTkComboBox internal dropdown trigger to our scrollable popup
        if hasattr(self.widget, "_open_dropdown_menu"):
            self.widget._open_dropdown_menu = self._toggle_dropdown

        # When readonly entry is clicked, toggle dropdown
        if hasattr(self.widget, "_entry"):
            self.widget._entry.bind("<Button-1>", self._toggle_dropdown, add="+")

    def configure(self, values: Optional[List[str]] = None, **kwargs):
        if values is not None:
            self.values = list(values)
            self._last_rendered = None
            if self.toplevel and self.toplevel.winfo_exists():
                self._populate_list(self.values)

    def _toggle_dropdown(self, event=None):
        now = time.monotonic()
        if now - self._open_ts < 0.15:
            return "break"

        if self.toplevel and self.toplevel.winfo_exists():
            self._close()
        else:
            self._open()
        return "break"

    def _open(self):
        if not self.values:
            return

        root = self.widget.winfo_toplevel()
        self._open_ts = time.monotonic()

        # Calculate position & dimensions
        self.widget.update_idletasks()
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        w = self.custom_width or max(self.widget.winfo_width(), 280)

        # Ensure it fits on screen
        screen_height = root.winfo_screenheight()
        dropdown_h = self.max_height
        if y + dropdown_h > screen_height - 40:
            alt_y = self.widget.winfo_rooty() - dropdown_h - 2
            if alt_y > 40:
                y = alt_y
            else:
                dropdown_h = max(150, screen_height - y - 60)

        self._geo = (x, y, w, dropdown_h)

        self.toplevel = ctk.CTkToplevel(root)
        self.toplevel.overrideredirect(True)
        self.toplevel.geometry(f"{w}x{dropdown_h}+{x}+{y}")
        self.toplevel.attributes("-topmost", True)
        self.toplevel.configure(fg_color=ThemeManager.surface())
        try:
            self.toplevel.transient(root)
        except Exception:
            pass

        # Main Card Frame
        main_card = ctk.CTkFrame(
            self.toplevel,
            fg_color=ThemeManager.surface(),
            corner_radius=8,
            border_width=1,
            border_color=ThemeManager.border()
        )
        main_card.pack(fill="both", expand=True, padx=0, pady=0)

        # Search Bar (if searchable)
        if self.searchable and len(self.values) > 6:
            search_box = ctk.CTkFrame(main_card, fg_color=ThemeManager.surface(), height=36)
            search_box.pack(fill="x", padx=6, pady=(6, 2))
            search_box.pack_propagate(False)

            self.search_entry = ctk.CTkEntry(
                search_box,
                placeholder_text=self.placeholder_text,
                font=Fonts.regular(10),
                fg_color=ThemeManager.surface_alt(),
                border_color=ThemeManager.border(),
                height=26
            )
            self.search_entry.pack(fill="x", padx=4, pady=2)
            self.search_entry.bind("<KeyRelease>", self._on_search)
        else:
            self.search_entry = None

        # Scrollable List Container
        self.scroll_frame = ctk.CTkScrollableFrame(
            main_card,
            fg_color="transparent",
            corner_radius=6,
            scrollbar_button_color=ThemeManager.border(),
            scrollbar_button_hover_color=ThemeManager.primary()
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # Bind mouse wheel on container for Linux X11/Wayland & Win/Mac
        self._bind_mousewheel(self.scroll_frame)
        if hasattr(self.scroll_frame, "_parent_canvas"):
            self._bind_mousewheel(self.scroll_frame._parent_canvas)

        self._populate_list(self.values)

        self.toplevel.lift()
        self.toplevel.update()

        # focus_set() can race window creation on some WMs (esp. inside AppImage
        # where the popup maps late) -> "bad window path name". Retry briefly.
        if self.search_entry:
            for _ in range(6):
                try:
                    if self.search_entry.winfo_exists():
                        self.search_entry.focus_set()
                    break
                except tk.TclError:
                    root.update_idletasks()
                    self.widget.after(20, lambda: None)

        # Click outside to dismiss
        self._click_binding_id = root.bind("<Button-1>", self._check_click_outside, add="+")
        self.toplevel.bind("<Escape>", lambda _: self._close())

    def _bind_mousewheel(self, widget: Any):
        """Cross-platform mouse wheel scrolling attachment."""
        if sys.platform.startswith("linux"):
            widget.bind("<Button-4>", lambda e: self._scroll_units(-1), add="+")
            widget.bind("<Button-5>", lambda e: self._scroll_units(1), add="+")
        else:
            widget.bind("<MouseWheel>", lambda e: self._scroll_units(int(-1 * (e.delta / 120))), add="+")

    def _scroll_units(self, units: int):
        if self.scroll_frame and hasattr(self.scroll_frame, "_parent_canvas"):
            try:
                self.scroll_frame._parent_canvas.yview_scroll(units, "units")
            except Exception:
                pass

    def _populate_list(self, items: List[str], hide_tail_note: bool = False):
        if self._last_rendered == items:
            return
        self._last_rendered = items

        # Clear existing buttons
        for btn in self.buttons:
            try:
                btn.destroy()
            except Exception:
                pass
        self.buttons.clear()

        current_val = self.variable.get() if self.variable else None

        # Freeze guard: rendering dozens of CTkButtons per keystroke janks the
        # UI. Show the first RENDER_LIMIT matches plus a tail note.
        shown = items
        tail_note = ""
        if len(items) > self._render_limit:
            shown = items[: self._render_limit]
            tail_note = f"… {len(items) - self._render_limit} more — refine search"

        for item in shown:
            is_selected = (item == current_val)
            btn = ctk.CTkButton(
                self.scroll_frame,
                text=item,
                font=Fonts.bold(10) if is_selected else Fonts.regular(10),
                text_color=ThemeManager.primary() if is_selected else ThemeManager.text(),
                fg_color=ThemeManager.border() if is_selected else "transparent",
                hover_color=ThemeManager.surface_alt(),
                anchor="w",
                height=26,
                corner_radius=4,
                command=lambda val=item: self._select_item(val)
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._bind_mousewheel(btn)
            self.buttons.append(btn)

        if tail_note or hide_tail_note:
            note = ctk.CTkLabel(
                self.scroll_frame,
                text=(tail_note or "refine search to see more"),
                font=Fonts.regular(9),
                text_color=ThemeManager.text_muted(),
                anchor="w",
            )
            note.pack(fill="x", padx=6, pady=(0, 2))

    def _on_search(self, event=None):
        # Debounce: cancel pending rebuild, schedule after idle gap.
        if self._search_after_id:
            try:
                self.widget.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.widget.after(120, self._apply_search_filter)

    def _apply_search_filter(self):
        self._search_after_id = None
        query = self.search_entry.get().strip().lower() if self.search_entry else ""
        if not query:
            filtered = list(self.values)
        else:
            filtered = [v for v in self.values if query in v.lower()]
        self._populate_list(filtered)

    def _select_item(self, val: str):
        if self.variable:
            self.variable.set(val)
        if hasattr(self.widget, "set"):
            try:
                self.widget.set(val)
            except Exception as e:
                from netools.libs.logger import get_logger
                get_logger(__name__).warning(f"combobox.set failed: {e}")
        # Keep the combobox's value list in sync
        if hasattr(self.widget, "configure"):
            try:
                current = list(self.widget.cget("values") or [])
                if val not in current:
                    current.append(val)
                    self.widget.configure(values=current)
            except Exception as e:
                from netools.libs.logger import get_logger
                get_logger(__name__).warning(f"combobox values sync failed: {e}")
        if self.command:
            try:
                self.command(val)
            except Exception as e:
                from netools.libs.logger import get_logger
                get_logger(__name__).error(f"Dropdown callback error: {e}", exc_info=True)
        self._close()

    def _check_click_outside(self, event):
        if not self.toplevel or not self.toplevel.winfo_exists():
            return
        # Ignore clicks during the first 150ms of opening
        if time.monotonic() - self._open_ts < 0.15:
            return
        try:
            w_str = str(event.widget)
            top_str = str(self.toplevel)
            widget_str = str(self.widget)
            # If clicked inside the dropdown popup or on the combobox, do not close
            if w_str.startswith(top_str) or w_str.startswith(widget_str):
                return

            x, y = event.x_root, event.y_root
            gx, gy, gw, gh = self._geo
            if (gx <= x <= gx + gw) and (gy <= y <= gy + gh):
                return
            wx, wy, ww, wh = self.widget.winfo_rootx(), self.widget.winfo_rooty(), self.widget.winfo_width(), self.widget.winfo_height()
            if (wx <= x <= wx + ww) and (wy <= y <= wy + wh):
                return
        except Exception:
            pass
        self._close()

    def _close(self):
        if self.toplevel and self.toplevel.winfo_exists():
            try:
                root = self.widget.winfo_toplevel()
                if self._click_binding_id:
                    root.unbind("<Button-1>", self._click_binding_id)
            except Exception:
                pass
            try:
                self.toplevel.destroy()
            except Exception:
                pass
            self.toplevel = None
