"""
Privacy kill switch: blocks all outbound traffic unless a healthy proxy is alive.

Implemented as a thin wrapper around the OS firewall:
  - Linux:   iptables (requires CAP_NET_ADMIN; degrades to no-op + warning
             when iptables is missing or returns non-zero)
  - macOS:   no implementation yet (returns a safe no-op restore)
  - Windows: no implementation yet (returns a safe no-op restore)

Always returns a `restore` callable that the caller MUST invoke when the
proxy pool becomes healthy again, or the user goes offline permanently.
This module NEVER raises - any failure inside _run_iptables is logged
and treated as "best effort, no enforcement".

Typical use from proxy_service.start_proxy_pool:

    if kill_switch and not alive_count:
        from netools.adapters import kill_switch
        restore_fn = kill_switch.arm_block_all()
        state["_kill_switch_restore"] = restore_fn
    # watchdog will call state["_kill_switch_restore"]() when pool recovers
"""
from typing import Callable

from netools.libs.env import get_os_type
from netools.libs.logger import get_logger

log = get_logger(__name__)


def _run_iptables(args: list) -> tuple[bool, str]:
    """Run an iptables command. Returns (success, stderr). Never raises."""
    import shutil
    import subprocess

    if shutil.which("iptables") is None:
        return False, "iptables not found"
    try:
        r = subprocess.run(
            ["iptables"] + args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode == 0, r.stderr.strip()
    except Exception as exc:
        return False, str(exc)


def arm_block_all() -> Callable[[], None]:
    """Insert REJECT rule for all outbound (except loopback).

    Returns a `restore` callable that removes the rule. The restore
    callable is always safe to invoke - on platforms we do not support
    it is a no-op.
    """
    os_t = get_os_type()

    if os_t == "linux":
        ok, err = _run_iptables(
            [
                "-I", "OUTPUT", "!", "-o", "lo",
                "-j", "REJECT", "--reject-with", "icmp-net-unreachable",
            ]
        )
        if not ok:
            log.warning(
                f"kill_switch: iptables insert failed ({err}); "
                "running in dry-run. CAP_NET_ADMIN may be required."
            )

        def _restore() -> None:
            _run_iptables(
                [
                    "-D", "OUTPUT", "!", "-o", "lo",
                    "-j", "REJECT", "--reject-with", "icmp-net-unreachable",
                ]
            )

        return _restore

    # macOS / Windows / unknown: return a no-op restore.
    log.warning(
        f"kill_switch: no implementation for OS={os_t}; "
        "returning no-op restore (no enforcement will be applied)"
    )
    return lambda: None
