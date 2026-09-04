"""
Modern CustomTkinter Scrollable & Searchable Dropdown Popup.
Uses a single native tk.Listbox (instant rendering for 90+ items, native
scrolling/keyboard) instead of per-item CTkButtons, which froze the UI.
"""

import time
import tkinter as tk
from typing import Any, Callable, List, Optional, Tuple

import customtkinter as ctk

from netools.gui.theme import (
    Fonts,
    ThemeManager,
)
from netools.gui.wm import mark_popup


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

        self._filtered: List[str] = []
        self._search_after_id: Optional[str] = None
        self.toplevel: Optional[ctk.CTkToplevel] = None
        self.listbox: Optional[tk.Listbox] = None
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
            if self.toplevel and self.toplevel.winfo_exists():
                self._populate(self.values)

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
        mark_popup(self.toplevel, root)
        self.toplevel.overrideredirect(True)
        self.toplevel.geometry(f"{w}x{dropdown_h}+{x}+{y}")
        self.toplevel.attributes("-topmost", True)
        self.toplevel.configure(fg_color=ThemeManager.surface())

        main_card = ctk.CTkFrame(
            self.toplevel,
            fg_color=ThemeManager.surface(),
            corner_radius=8,
            border_width=1,
            border_color=ThemeManager.border(),
        )
        main_card.pack(fill="both", expand=True, padx=0, pady=0)

        # Search Bar (if searchable)
        if self.searchable and len(self.values) > 6:
            self.search_entry = ctk.CTkEntry(
                main_card,
                placeholder_text=self.placeholder_text,
                font=Fonts.regular(10),
                fg_color=ThemeManager.surface_alt(),
                border_color=ThemeManager.border(),
                height=28,
            )
            self.search_entry.pack(fill="x", padx=8, pady=(8, 4))
            self.search_entry.bind("<KeyRelease>", self._on_search)
            self.search_entry.bind("<Down>", lambda e: self._focus_list())
            self.search_entry.bind("<Return>", lambda e: self._select_first())
        else:
            self.search_entry = None

        # Native Listbox: renders 90+ items instantly, scrolls natively
        list_frame = tk.Frame(main_card, bg=ThemeManager.surface())
        list_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        sb = tk.Scrollbar(list_frame, width=10)
        self.listbox = tk.Listbox(
            list_frame,
            font=Fonts.regular(11),
            bg=ThemeManager.surface(),
            fg=ThemeManager.text(),
            selectbackground=ThemeManager.border(),
            selectforeground=ThemeManager.primary(),
            highlightthickness=0,
            borderwidth=0,
            activestyle="none",
            yscrollcommand=sb.set,
        )
        sb.config(command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)

        self.listbox.bind("<ButtonRelease-1>", self._on_pick)
        self.listbox.bind("<Return>", self._on_pick)
        self.listbox.bind("<Escape>", lambda _: self._close())

        self._populate(self.values)

        self.toplevel.lift()
        self.toplevel.update_idletasks()  # NOT update(): re-entrant mainloop froze the UI

        if self.search_entry:
            self.search_entry.after(50, self._safe_focus)

        # Click outside to dismiss
        self._click_binding_id = root.bind("<Button-1>", self._check_click_outside, add="+")
        self.toplevel.bind("<Escape>", lambda _: self._close())

    def _safe_focus(self):
        try:
            if self.search_entry and self.search_entry.winfo_exists():
                self.search_entry.focus_set()
        except tk.TclError:
            pass

    def _focus_list(self):
        if self.listbox and self.listbox.size():
            self.listbox.focus_set()
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(0)
            self.listbox.activate(0)

    def _select_first(self):
        if self._filtered:
            self._select_item(self._filtered[0])

    def _populate(self, items: List[str]):
        self._filtered = list(items)
        lb = self.listbox
        if not lb:
            return
        lb.delete(0, "end")
        current_val = self.variable.get() if self.variable else None
        for i, item in enumerate(items):
            lb.insert("end", f"  {item}")
            if item == current_val:
                lb.itemconfig(i, foreground=ThemeManager.primary())
        # scroll current selection into view
        if current_val in items:
            lb.see(items.index(current_val))

    def _on_search(self, event=None):
        if event and event.keysym in ("Down", "Up", "Return", "Escape"):
            return
        # Debounce: cancel pending rebuild, schedule after idle gap.
        if self._search_after_id:
            try:
                self.widget.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.widget.after(80, self._apply_search_filter)

    def _apply_search_filter(self):
        self._search_after_id = None
        query = self.search_entry.get().strip().lower() if self.search_entry else ""
        filtered = [v for v in self.values if query in v.lower()] if query else list(self.values)
        self._populate(filtered)

    def _on_pick(self, event=None):
        if not self.listbox:
            return
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._filtered):
            self._select_item(self._filtered[idx])

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
            wx, wy, ww, wh = (
                self.widget.winfo_rootx(),
                self.widget.winfo_rooty(),
                self.widget.winfo_width(),
                self.widget.winfo_height(),
            )
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
            self.listbox = None
