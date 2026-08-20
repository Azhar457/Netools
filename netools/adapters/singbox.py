from netools.libs.logger import get_logger

log = get_logger(__name__)

"""
Sing-box Process Supervisor & Config Builder Adapter (Compatible with Sing-box 1.13+).
"""

import json
import os
import shutil
import signal
import subprocess
import sys
from typing import Any, Dict, Optional

from netools.config import CONFIGS_DIR, HTTP_PORT_OFFSET, LOGS_DIR, PID_DIR


def build_singbox_config(proxy: Dict[str, Any], local_port: int) -> Dict[str, Any]:
    """Build exact clean sing-box config for a single outbound proxy."""
    outbound = {
        "type": proxy["type"],
        "tag": "proxy",
        "server": proxy["server"],
        "server_port": proxy["server_port"],
    }

    if proxy["type"] == "shadowsocks":
        outbound["method"] = proxy["method"]
        outbound["password"] = proxy["password"]
    elif proxy["type"] == "trojan":
        outbound["password"] = proxy["password"]
        outbound["tls"] = proxy.get("tls", {"enabled": True, "server_name": proxy["server"]})
    elif proxy["type"] in ("vmess", "vless"):
        outbound["uuid"] = proxy["uuid"]
        if proxy.get("security"):
            outbound["security"] = proxy["security"]
        if proxy.get("flow"):
            outbound["flow"] = proxy["flow"]
        if proxy.get("tls"):
            outbound["tls"] = proxy["tls"]
        if proxy.get("transport"):
            outbound["transport"] = proxy["transport"]

    return {
        "log": {"level": "warn"},
        "inbounds": [
            {
                "type": "socks",
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "listen_port": local_port,
            },
            {
                "type": "http",
                "tag": "http-in",
                "listen": "127.0.0.1",
                "listen_port": local_port + HTTP_PORT_OFFSET,
            },
        ],
        "outbounds": [
            outbound,
            {"type": "direct", "tag": "direct"},
        ],
        "route": {
            "auto_detect_interface": True,
        },
    }

def start_singbox_instance(name: str, config: Dict[str, Any]) -> Optional[subprocess.Popen]:
    """Write config file, spawn sing-box subprocess, and store PID."""
    config_path = CONFIGS_DIR / f"{name}.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    try:
        os.chmod(config_path, 0o600)
    except OSError:
        pass

    log_path = LOGS_DIR / f"{name}.log"
    pid_path = PID_DIR / f"{name}.pid"

    log_file = open(log_path, "w")
    try:
        singbox_bin = shutil.which("sing-box") or shutil.which("sing-box.exe") or "sing-box"
        creationflags = 0x08000000 if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            [singbox_bin, "run", "-c", str(config_path)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        pid_path.write_text(str(proc.pid), encoding="utf-8")
        return proc
    except Exception as e:
        log.warning(f"Failed to start {name}: {e}")
        return None
    finally:
        log_file.close()  # parent closes its handle; child keeps the dup'd fd

def stop_singbox_instance(name: str) -> None:
    """Kill sing-box instance by name, remove pid and config."""
    pid_file = PID_DIR / f"{name}.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, ValueError):
            pass
        except Exception:
            pass
        finally:
            pid_file.unlink(missing_ok=True)

    config_file = CONFIGS_DIR / f"{name}.json"
    config_file.unlink(missing_ok=True)

def stop_all_singbox_instances() -> None:
    """Kill all active singbox instances recorded in PID_DIR (only our managed PIDs)."""
    for pid_file in PID_DIR.glob("*.pid"):
        name = pid_file.stem
        stop_singbox_instance(name)
    # NOTE: deliberately NOT running pkill — we only kill PIDs we spawned
