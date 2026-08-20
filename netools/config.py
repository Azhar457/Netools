"""
Central Configuration for Netools Suite.
"""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "runtime"
CONFIGS_DIR = RUNTIME_DIR / "configs"
LOGS_DIR = RUNTIME_DIR / "logs"
PID_DIR = RUNTIME_DIR / "pids"
STATE_FILE = RUNTIME_DIR / "state.json"

DOCS_DIR = BASE_DIR / "docs"
STATIC_PAC_FILE = BASE_DIR / "proxy.pac"

# Ensure runtime directories exist
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
PID_DIR.mkdir(parents=True, exist_ok=True)

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

# Backend Gateways
NINEROUTER_URL = os.getenv("NINEROUTER_URL", "http://localhost:20128")
NINEROUTER_CLI_TOKEN = auto_detect_9router_token()

OMNIROUTE_URL = os.getenv("OMNIROUTE_URL", "http://localhost:20129")
OMNIROUTE_TOKEN = os.getenv("OMNIROUTE_TOKEN", "")

# Upstream Proxy Subscriptions
PROXY_SOURCES = [
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
]

# Timeouts & Intervals
UPSTREAM_TEST_TIMEOUT = 5.0
MONITOR_DEFAULT_INTERVAL = 30
GRC_BENCHMARK_TIMEOUT = 2.5
