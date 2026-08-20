"""
Central Configuration for Netools Suite.
"""

import os
import sys
from pathlib import Path

# Paths
if getattr(sys, "frozen", False):
    # Frozen (PyInstaller AppImage/EXE): asset dir lives in the bundle (_MEIPASS),
    # runtime scratch must live in a user-writable location (bundle is read-only).
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    RUNTIME_DIR = Path(os.getenv("NETOOLS_RUNTIME_DIR", Path.home() / ".local" / "share" / "netools" / "runtime"))
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    RUNTIME_DIR = BASE_DIR / "runtime"
CONFIGS_DIR = RUNTIME_DIR / "configs"
LOGS_DIR = RUNTIME_DIR / "logs"
PID_DIR = RUNTIME_DIR / "pids"
STATE_FILE = RUNTIME_DIR / "state.json"

DOCS_DIR = BASE_DIR / "docs"
STATIC_PAC_FILE = BASE_DIR / "proxy.pac"

def ensure_runtime_dirs():
    """Create runtime directories on demand (called from CLI entrypoint, not at import time)."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    PID_DIR.mkdir(parents=True, exist_ok=True)
    # Restrict access: sing-box configs and PIDs hold plaintext credentials.
    for d in (RUNTIME_DIR, CONFIGS_DIR, LOGS_DIR, PID_DIR):
        try:
            os.chmod(d, 0o700)
        except OSError:
            pass

# Port allocations
SOCKS5_PORT_START = 11080   # 11080 .. 11099
HTTP_PORT_OFFSET = 10000    # 21080 .. 21099
PAC_SERVER_PORT = 18080
WEB_APP_PORT = 8088
DOH_PROXY_PORT = 5353
MAX_INSTANCES = 20

def auto_detect_9router_token() -> str:
    """Automatically derive 9Router CLI token from local machine credentials."""
    env_token = os.getenv("NINEROUTER_CLI_TOKEN", "").strip()
    if env_token:
        return env_token

    try:
        home = Path.home()
        m_id_file = home / ".9router" / "machine-id"
        secret_file = home / ".9router" / "auth" / "cli-secret"

        if m_id_file.exists() and secret_file.exists():
            import hashlib
            m_id = m_id_file.read_text(encoding="utf-8").strip()
            secret = secret_file.read_text(encoding="utf-8").strip()
            if m_id and secret:
                return hashlib.sha256((m_id + "9r-cli-auth" + secret).encode("utf-8")).hexdigest()[:16]
    except Exception:
        pass

    return ""

# Configuration File Support (~/.config/netools/config.json)
USER_CONFIG_DIR = Path.home() / ".config" / "netools"
USER_CONFIG_FILE = Path(os.getenv("NETOOLS_CONFIG_FILE", str(USER_CONFIG_DIR / "config.json")))

def load_user_config() -> dict:
    """Load optional user configuration from ~/.config/netools/config.json."""
    if USER_CONFIG_FILE.exists():
        try:
            import json
            return json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

_user_cfg = load_user_config()

# Backend Gateways
NINEROUTER_URL = os.getenv("NINEROUTER_URL", _user_cfg.get("ninerouter_url", "http://localhost:20128"))
_ninerouter_token_cache = None

def get_ninerouter_token() -> str:
    """Lazy-load 9Router CLI token (avoids file I/O on every import)."""
    global _ninerouter_token_cache
    if _ninerouter_token_cache is None:
        _ninerouter_token_cache = _user_cfg.get("ninerouter_token") or auto_detect_9router_token()
    return _ninerouter_token_cache

OMNIROUTE_URL = os.getenv("OMNIROUTE_URL", _user_cfg.get("omniroute_url", "http://localhost:20129"))
OMNIROUTE_TOKEN = os.getenv("OMNIROUTE_TOKEN", _user_cfg.get("omniroute_token", ""))

# Upstream Proxy Subscriptions
DEFAULT_PROXY_SOURCES = [
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
]
PROXY_SOURCES = _user_cfg.get("proxy_sources", DEFAULT_PROXY_SOURCES)

# Timeouts & Intervals
UPSTREAM_TEST_TIMEOUT = float(_user_cfg.get("upstream_test_timeout", 5.0))
MONITOR_DEFAULT_INTERVAL = int(_user_cfg.get("monitor_interval", 30))
GRC_BENCHMARK_TIMEOUT = float(_user_cfg.get("grc_timeout", 2.5))

