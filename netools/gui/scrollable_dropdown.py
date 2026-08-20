"""
Modern CustomTkinter Scrollable & Searchable Dropdown Popup.
Prevents dropdown menus with 50+ items from overflowing the screen.
"""

import tkinter as tk
from typing import Any, Callable, List, Optional

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

        self.toplevel: Optional[ctk.CTkToplevel] = None
        self.scroll_frame: Optional[ctk.CTkScrollableFrame] = None
        self.search_entry: Optional[ctk.CTkEntry] = None
        # Safely disable default CTkComboBox / CTkOptionMenu popup
        if hasattr(self.widget, "_open_dropdown_menu"):
            self.widget._open_dropdown_menu = lambda: None
        if hasattr(self.widget, "_dropdown_menu") and self.widget._dropdown_menu is not None:
            try:
                self.widget._dropdown_menu.is_open = lambda: False
            except Exception:
                pass
        elif hasattr(self.widget, "_dropdown_menu") and self.widget._dropdown_menu is None:
            class _DummyDropdown:
                def is_open(self): return False
                def close(self): pass
                def open(self): pass
            self.widget._dropdown_menu = _DummyDropdown()


        # Bind click event on widget
        self.widget.bind("<Button-1>", self._toggle_dropdown, add="+")
        if hasattr(self.widget, "_entry"):
            self.widget._entry.bind("<Button-1>", self._toggle_dropdown, add="+")


    def configure(self, values: Optional[List[str]] = None, **kwargs):
        if values is not None:
            self.values = list(values)
            if self.toplevel and self.toplevel.winfo_exists():
                self._populate_list(self.values)

    def _toggle_dropdown(self, event=None):
        if self.toplevel and self.toplevel.winfo_exists():
            self._close()
        else:
            self._open()
        return "break"

    def _open(self):
        if not self.values:
            return

        root = self.widget.winfo_toplevel()

        self.toplevel = ctk.CTkToplevel(root)
        self.toplevel.withdraw()
        self.toplevel.overrideredirect(True)
        self.toplevel.configure(fg_color=ThemeManager.surface_alt())
        self.toplevel.attributes("-topmost", True)

        # Calculate position & dimensions
        self.widget.update_idletasks()
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        w = self.custom_width or max(self.widget.winfo_width(), 280)

        # Ensure it fits on screen
        screen_height = root.winfo_screenheight()
        dropdown_h = self.max_height
        if y + dropdown_h > screen_height - 40:
            # If not enough room below, open above widget
            alt_y = self.widget.winfo_rooty() - dropdown_h - 2
            if alt_y > 40:
                y = alt_y
            else:
                dropdown_h = max(150, screen_height - y - 60)

        self.toplevel.geometry(f"{w}x{dropdown_h}+{x}+{y}")

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


        # Scrollable List Container
        self.scroll_frame = ctk.CTkScrollableFrame(
            main_card,
            fg_color="transparent",
            corner_radius=6,
            scrollbar_button_color=ThemeManager.border(),
            scrollbar_button_hover_color=ThemeManager.primary()
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._populate_list(self.values)

        self.toplevel.deiconify()
        self.toplevel.lift()

        if self.search_entry:
            self.search_entry.focus_set()

        # Click outside to dismiss
        root.bind("<Button-1>", self._check_click_outside, add="+")
        self.toplevel.bind("<Escape>", lambda _: self._close())

    def _populate_list(self, items: List[str]):
        # Clear existing buttons
        for btn in self.buttons:
            btn.destroy()
        self.buttons.clear()

        current_val = self.variable.get() if self.variable else None

        for item in items:
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
            self.buttons.append(btn)

    def _on_search(self, event=None):
        query = self.search_entry.get().strip().lower() if self.search_entry else ""
        if not query:
            filtered = self.values
        else:
            filtered = [v for v in self.values if query in v.lower()]
        self._populate_list(filtered)

    def _select_item(self, val: str):
        if self.variable:
            self.variable.set(val)
        if hasattr(self.widget, "set"):
            self.widget.set(val)
        if self.command:
            self.command(val)
        self._close()

    def _check_click_outside(self, event):
        if not self.toplevel or not self.toplevel.winfo_exists():
            return
        x, y = event.x_root, event.y_root
        top_x = self.toplevel.winfo_rootx()
        top_y = self.toplevel.winfo_rooty()
        top_w = self.toplevel.winfo_width()
        top_h = self.toplevel.winfo_height()

        widget_x = self.widget.winfo_rootx()
        widget_y = self.widget.winfo_rooty()
        widget_w = self.widget.winfo_width()
        widget_h = self.widget.winfo_height()

        inside_top = (top_x <= x <= top_x + top_w) and (top_y <= y <= top_y + top_h)
        inside_widget = (widget_x <= x <= widget_x + widget_w) and (widget_y <= y <= widget_y + widget_h)

        if not inside_top and not inside_widget:
            self._close()

    def _close(self):
        if self.toplevel and self.toplevel.winfo_exists():
            try:
                root = self.widget.winfo_toplevel()
                root.unbind("<Button-1>")
            except Exception:
                pass
            self.toplevel.destroy()
            self.toplevel = None
