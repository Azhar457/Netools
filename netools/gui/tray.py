"""
Native System Tray Integration for Netools Suite.
Allows Netools to minimize to tray when closed and provides quick 1-click actions:
- Open GUI
- Start/Stop Proxy Pool
- Flush DNS Cache
- Clean Exit
"""

import sys
import threading
from pathlib import Path
from typing import Any, Optional

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

        candidates = [
            Path(getattr(sys, "_MEIPASS", "")) / "assets" / "icon-64.png" if getattr(sys, "_MEIPASS", None) else None,
            Path(__file__).resolve().parent.parent.parent / "assets" / "icon-64.png",
            Path.cwd() / "assets" / "icon-64.png",
        ]
        image = None
        for p in candidates:
            if p and p.exists():
                try:
                    image = Image.open(str(p))
                    break
                except Exception:
                    pass
        if not image:
            image = create_fallback_image()

        dns_menu = pystray.Menu(
            pystray.MenuItem("⚡ Cloudflare (1.1.1.1)", lambda: self._on_quick_dns(["1.1.1.1", "1.0.0.1"], "Cloudflare")),
            pystray.MenuItem("⚡ Google (8.8.8.8)", lambda: self._on_quick_dns(["8.8.8.8", "8.8.4.4"], "Google")),
            pystray.MenuItem("🛡️ Quad9 (Security / No-Log)", lambda: self._on_quick_dns(["9.9.9.9", "149.112.112.112"], "Quad9")),
            pystray.MenuItem("🚫 AdGuard (Ad-Blocking)", lambda: self._on_quick_dns(["94.140.14.14", "94.140.15.15"], "AdGuard")),
            pystray.MenuItem("🇨🇳 AliDNS (Alibaba Cloud)", lambda: self._on_quick_dns(["223.5.5.5", "223.6.6.6"], "AliDNS")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("↩️ Restore DHCP Default", self._on_restore_dhcp)
        )

        menu = pystray.Menu(
            pystray.MenuItem("⚡ Buka Netools GUI", self._on_show_gui, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🌐 Quick DNS Switch", dns_menu),
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

    def _on_quick_dns(self, ips, prov_name):
        from netools.adapters import platform_dns as sys_dns
        def _bg():
            ifaces = sys_dns.get_network_interfaces()
            if not ifaces:
                return
            dev = ifaces[0]["device"]
            conn = ifaces[0].get("connection")
            success = sys_dns.apply_system_dns(dev, ips, connection_name=conn, enable_dot=True, persistent=True)
            try:
                if success:
                    self.main_app.after(0, lambda: self.main_app.show_toast(f"✓ DNS {prov_name} aktif dari System Tray!", level="success"))
                    if hasattr(self.main_app, "dns_view"):
                        self.main_app.after(0, self.main_app.dns_view.load_active_interface_dns)
                    if hasattr(self.main_app, "dashboard_view"):
                        self.main_app.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def _on_restore_dhcp(self, icon=None, item=None):
        from netools.adapters import platform_dns as sys_dns
        def _bg():
            ifaces = sys_dns.get_network_interfaces()
            if not ifaces:
                return
            dev = ifaces[0]["device"]
            conn = ifaces[0].get("connection")
            sys_dns.restore_default_dns(dev, connection_name=conn)
            try:
                self.main_app.after(0, lambda: self.main_app.show_toast("✓ Interface dikembalikan ke DHCP dari System Tray.", level="info"))
                if hasattr(self.main_app, "dns_view"):
                    self.main_app.after(0, self.main_app.dns_view.load_active_interface_dns)
                if hasattr(self.main_app, "dashboard_view"):
                    self.main_app.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

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
