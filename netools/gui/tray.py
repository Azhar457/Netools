"""
Native System Tray Integration for Netools Suite.
Allows Netools to minimize to tray when closed and provides quick 1-click actions:
- Open GUI
- Start/Stop Proxy Pool
- Flush DNS Cache
- Clean Exit
"""

import threading
import sys
from pathlib import Path
from typing import Optional, Any

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


def create_fallback_image():
    """Create a high-contrast 64x64 icon if assets/icon-64.png is not found."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Outer circle
    draw.ellipse((4, 4, 60, 60), fill=(137, 180, 250, 255), outline=(17, 17, 27, 255), width=2)
    # Inner lightning / N symbol
    draw.polygon([(32, 10), (20, 36), (32, 36), (28, 54), (44, 28), (32, 28)], fill=(17, 17, 27, 255))
    return img


class TrayManager:
    def __init__(self, main_app: Any):
        self.main_app = main_app
        self.icon: Optional[pystray.Icon] = None
        self.is_running = False

    def is_available(self) -> bool:
        return PYSTRAY_AVAILABLE

    def start(self):
        if not PYSTRAY_AVAILABLE or self.is_running:
            return

        icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "icon-64.png"
        if icon_path.exists():
            try:
                image = Image.open(str(icon_path))
            except Exception:
                image = create_fallback_image()
        else:
            image = create_fallback_image()

        menu = pystray.Menu(
            pystray.MenuItem("⚡ Buka Netools GUI", self._on_show_gui, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🚀 Start Proxy Pool", self._on_start_pool),
            pystray.MenuItem("🛑 Stop Proxy Pool", self._on_stop_pool),
            pystray.MenuItem("♻️ Flush DNS Cache", self._on_flush_dns),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Keluar (Exit)", self._on_exit)
        )

        self.icon = pystray.Icon("netools", image, "Netools Suite v2.0", menu)
        self.is_running = True

        def _run_tray():
            try:
                self.icon.run()
            except Exception as e:
                print(f"[WARN] System tray loop ended: {e}")
            finally:
                self.is_running = False

        tray_thread = threading.Thread(target=_run_tray, daemon=True)
        tray_thread.start()

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
        self.is_running = False

    def _on_show_gui(self, icon=None, item=None):
        try:
            self.main_app.after(0, self.main_app.restore_from_tray)
        except Exception:
            pass

    def _on_start_pool(self, icon=None, item=None):
        from netools.services import proxy_service
        def _bg():
            proxy_service.start_proxy_pool(max_instances=20, standalone=False)
            try:
                self.main_app.after(0, lambda: self.main_app.show_toast("✓ Proxy pool aktif dari System Tray!", level="success"))
                self.main_app.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def _on_stop_pool(self, icon=None, item=None):
        from netools.services import proxy_service
        def _bg():
            proxy_service.stop_proxy_pool()
            try:
                self.main_app.after(0, lambda: self.main_app.show_toast("Proxy pool dimatikan dari System Tray.", level="warning"))
                self.main_app.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def _on_flush_dns(self, icon=None, item=None):
        from netools.adapters import platform_dns as sys_dns
        def _bg():
            sys_dns.flush_dns_cache()
            try:
                self.main_app.after(0, lambda: self.main_app.show_toast("✓ DNS cache di-flush dari System Tray!", level="success"))
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def _on_exit(self, icon=None, item=None):
        self.stop()
        try:
            self.main_app.after(0, self.main_app.force_exit)
        except Exception:
            sys.exit(0)
