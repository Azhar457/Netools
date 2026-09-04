"""
Interactive Browser Login & Auto-Capture Service (OAuth-like flow).
Launches real browser window (Brave / Chrome / Firefox), waits for user login,
captures session tokens automatically, and closes the browser window.
"""

import os
import shutil
import subprocess
import threading
import time
from typing import Callable, Optional

from netools.libs.logger import get_logger
from netools.services.session_extractor import (
    extract_all_browser_sessions,
)

log = get_logger(__name__)

PROVIDER_URLS = {
    "adapta-web": "https://adapta.org/",
    "lmarena": "https://lmarena.ai/",
    "blackbox-web": "https://www.blackbox.ai/",
    "chatgpt-web": "https://chatgpt.com/",
    "claude-web": "https://claude.ai/login",
    "deepseek-web": "https://chat.deepseek.com/",
    "doubao-web": "https://www.dola.com/",
    "gemini-business": "https://gemini.google.com/",
    "gemini-web": "https://gemini.google.com/",
    "grok-web": "https://grok.com/",
    "huggingchat": "https://huggingface.co/chat/",
    "inner-ai": "https://inner.ai/",
    "kimi-web": "https://www.kimi.ai/",
    "copilot-m365-web": "https://www.microsoft365.com/",
    "copilot-web": "https://copilot.microsoft.com/",
    "muse-spark-web": "https://meta.ai/",
    "perplexity-web": "https://www.perplexity.ai/",
    "poe-web": "https://www.poe.com/",
    "t3-web": "https://t3.chat/",
    "yuanbao-web": "https://yuanbao.tencent.com/",
    "v0-vercel-web": "https://v0.dev/",
    "venice-web": "https://venice.ai/",
    "zai-web": "https://chat.z.ai/",
    "zenmux-free": "https://zenmux.com/",
}


def find_browser_executable(browser_name: str) -> Optional[str]:
    """Find absolute path to browser binary."""
    name_lower = browser_name.lower()
    if "brave" in name_lower:
        return shutil.which("brave-browser") or shutil.which("brave")
    elif "chrome" in name_lower or "chromium" in name_lower:
        return (
            shutil.which("google-chrome")
            or shutil.which("google-chrome-stable")
            or shutil.which("chromium")
            or shutil.which("chromium-browser")
        )
    elif "firefox" in name_lower:
        return shutil.which("firefox")
    # Default fallback
    return shutil.which("brave-browser") or shutil.which("google-chrome") or shutil.which("firefox")


class BrowserLoginSession:
    """Manages an active browser login & token capture lifecycle."""

    def __init__(
        self,
        browser_name: str,
        provider_key: str,
        target_url: Optional[str] = None,
        on_captured: Optional[Callable[[dict], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ):
        self.browser_name = browser_name
        self.provider_key = provider_key
        self.target_url = target_url or PROVIDER_URLS.get(provider_key, "https://chat.z.ai/")
        self.on_captured = on_captured
        self.on_status = on_status
        self.proc: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Launch browser and start background capture listener."""
        exe = find_browser_executable(self.browser_name)
        if not exe:
            if self.on_status:
                self.on_status(f"❌ Browser {self.browser_name} tidak ditemukan di sistem!")
            return False

        # Build command
        if "firefox" in exe.lower():
            cmd = [exe, "--new-window", self.target_url]
        else:
            # Chromium / Brave app-mode popup
            cmd = [exe, f"--app={self.target_url}"]

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )
        except Exception as e:
            if self.on_status:
                self.on_status(f"❌ Gagal meluncurkan browser: {e}")
            return False

        if self.on_status:
            self.on_status(f"🌐 Menunggu kamu login di {self.browser_name}...")

        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """Cancel capture and close browser process if open."""
        self._stop_event.set()
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None

    def _watch_loop(self):
        """Poll storage until matching token is found or session closed."""
        # Initial snapshot of existing tokens
        b_key = (
            "Brave"
            if "brave" in self.browser_name.lower()
            else ("Chrome" if "chrome" in self.browser_name.lower() else "all")
        )
        initial_tokens = {
            s["token"]
            for s in extract_all_browser_sessions(
                browser_filter=b_key,
                provider_filter=self.provider_key if self.provider_key != "custom" else "all",
                custom_keyword=self.target_url if self.provider_key == "custom" else "",
            )
        }

        # Watch for up to 5 minutes (300 iterations x 1s)
        for _ in range(300):
            if self._stop_event.is_set():
                break

            # Check if browser process is still alive
            if self.proc and self.proc.poll() is not None:
                # Browser was closed by user
                break

            time.sleep(1.0)

            # Check for new tokens
            current_sessions = extract_all_browser_sessions(
                browser_filter=b_key,
                provider_filter=self.provider_key if self.provider_key != "custom" else "all",
                custom_keyword=self.target_url if self.provider_key == "custom" else "",
            )

            # Look for newly created token or valid active session
            for s in current_sessions:
                if s["token"] not in initial_tokens or len(initial_tokens) == 0:
                    # Captured!
                    if self.on_status:
                        self.on_status(f"✓ Sesi login berhasil ditangkap: {s['label']}")
                    if self.on_captured:
                        self.on_captured(s)
                    self.stop()
                    return

            # If user already had an active valid session and clicked login
            if current_sessions and len(initial_tokens) > 0:
                # User might have refreshed or session already exists
                pass

        if not self._stop_event.is_set() and self.on_status:
            self.on_status("ℹ️ Jendela browser ditutup atau waktu login berakhir.")
