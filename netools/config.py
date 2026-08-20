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

# Backend Gateways
NINEROUTER_URL = os.getenv("NINEROUTER_URL", "http://localhost:20128")
NINEROUTER_CLI_TOKEN = os.getenv("NINEROUTER_CLI_TOKEN", "cb9bee27d95c976e")

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
