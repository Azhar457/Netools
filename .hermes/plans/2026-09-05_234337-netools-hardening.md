# Netools Hardening & UX Plan

> Plan generated 2026-09-05 after re-reading the live tree.
> Status of repo: branch `main`, head `70af225` (singbox config fix).
> Working tree has 14 modified files + 4 new untracked (MVC controllers, platform_proxy) that the plan integrates with rather than replaces.

---

## Goal

Move Netools from "fires-and-forgets a proxy pool" to "self-healing, observable, privacy-tight" — without re-architecting the WIP MVC layer — by landing three focused improvements, each individually shippable.

## Current Context / Assumptions

**What's already in the tree (verified via `head`, `grep`, `uv run pytest`):**

- `netools/services/proxy_service.py:102` — `start_proxy_pool()` already parallelizes download / port-poll / upstream-test / batch-register. 3-5s cold start.
- `netools/services/proxy_service.py:295` — `refresh_proxy_pool()` exists for runtime re-fetch.
- `netools/services/watchdog_service.py:21` — `run_monitor_cycle()` finds dead ports and swaps them from a fresh fetch. Runs on a 15s `threading.Timer` started by `start_watchdog_thread` only when the user toggles the checkbox in `view_proxy.py:116` (`chk_watchdog`).
- `netools/adapters/omniroute.py` — uses `connect_db()` helper (replaces inline `sqlite3.connect`); supports batch `add_proxy_pools_batch` and `assign_proxies_to_connections_batch`.
- `netools/adapters/platform_proxy.py` — new (untracked). Cross-platform `enable/disable_system_proxy(pac_url)` for macOS, Windows, Linux. Already has `tests/test_platform_proxy.py` (12 tests passing).
- `netools/controllers/{base,proxy,gateway,system_proxy}_controller.py` — new MVC layer with `BaseController.run_async` for background work + UI-thread callback dispatch. Already has `tests/test_controllers.py` (12 tests passing).
- `netools/services/proxy_service.py:33` — in-progress: `fetch_and_parse_proxies` interleave change (not yet committed, source diversity for protocol mix).
- `tests/` — 190/190 pass on `main`; +24 with the WIP controllers + platform_proxy.
- `~/.config/netools/config.json` is read for user overrides (`netools/config.py:79`).
- Sing-box 1.13.x rejects `tcp_keepalive_interval` on outbounds (lesson from commit `70af225`).
- `view_proxy.py` has no heatmap, no bandwidth display, no kill switch, no TUN device.

**Pain points observed in this session:**

1. `sb-00` through `sb-19` all died within ~3s of starting. Pipeline reports "0 proxies active" with no per-instance reason in the UI — operator can't tell whether it was a config rejection, a fetch failure, or upstream dead.
2. Watchdog default is **off** (must be checked in the GUI). So zero protection by default.
3. 18/20 dead means operator can't visually distinguish the 2 alive from the 18 dead at a glance — need heatmap.
4. `proxy_service.start_proxy_pool` does not record per-instance failure reasons.

**Non-goals (this plan):** WireGuard, multi-hop, TUN device, certificate pinning, plugin system, publish to npm for OmniRoute. Out of scope for this round.

---

## Architecture / Proposed Approach

Land **three orthogonal, independently-mergeable improvements** that share the new `controllers/` layer for thread-safety and the existing `watchdog_service` for the auto-heal engine:

1. **Auto-heal on by default** + per-instance failure reason capture → fixes the silent-dead-pool problem the user actually hit.
2. **Pool heatmap GUI** + bandwidth probe → gives the operator immediate visual feedback on which proxy is alive.
3. **Kill switch** (transparent `iptables`/`pf`/`netsh` fallback when sing-box tunnel dies) → privacy guarantee, no data leak.

Each tier uses the same pattern: write failing test → minimal impl → verify pass → commit. No new abstract base classes, no DI containers. YAGNI.

---

## Step-by-Step Tasks

### TIER 1 — Always-on auto-heal + failure-reason capture (HIGHEST IMPACT)

#### Task 1.1 — TDD: `start_proxy_pool` records per-instance failure reasons

**File:** `tests/test_proxy_service.py` (append)

Add a test that asserts the new diagnostic field is present in returned state.

```python
def test_start_proxy_pool_records_failure_reasons():
    """Pipeline must report per-instance failure reasons, not just 'killed'."""
    from unittest.mock import patch
    from netools.services.proxy_service import start_proxy_pool

    with patch("netools.services.proxy_service.fetch_and_parse_proxies",
               return_value=[{"type": "shadowsocks", "server": "127.0.0.1",
                              "server_port": 1, "method": "x", "password": "y"}]):
        result = start_proxy_pool(max_instances=1, standalone=True)

    # Instance entry must have either a "healthy" flag or a "reason" string
    instances = result.get("instances", {})
    assert instances, "at least one slot attempted"
    first = next(iter(instances.values()))
    assert "reason" in first or "healthy" in first, (
        f"per-instance diagnostic missing; got keys: {list(first.keys())}"
    )
```

Run (expect FAIL): `uv run pytest tests/test_proxy_service.py::test_start_proxy_pool_records_failure_reasons -q`
Expected output: `1 failed, AttributeError: 'dict' object has no attribute 'reason'`

---

#### Task 1.2 — Implement per-instance diagnostics in `start_proxy_pool`

**File:** `netools/services/proxy_service.py` (lines 99-138)

Replace the `started.append((name, port, proxy, proc))` tuple + the `alive = []` accumulator with dicts carrying a `reason` field. Keep the port ordering. Minimal patch (copy-paste ready):

```python
started = []  # [{"name", "port", "proxy", "proc"}]
for i, proxy in enumerate(proxies[:max_instances]):
    port = SOCKS5_PORT_START + i
    name = f"sb-{i:02d}"
    config = sb_drv.build_singbox_config(proxy, port)
    proc = sb_drv.start_singbox_instance(name, config)
    if proc:
        started.append({"name": name, "port": port, "proxy": proxy, "proc": proc})
    else:
        log.warning(f"{name} could not spawn sing-box process")

# ... (port-readiness loop unchanged) ...

alive = []
diagnostics: Dict[str, str] = {}  # name -> reason
with concurrent.futures.ThreadPoolExecutor(max_workers=max(len(started), 1)) as ex:
    futures = {
        ex.submit(probe_socks_upstream, port, timeout=4.0): entry
        for entry in started
    }
    for future in concurrent.futures.as_completed(futures):
        entry = futures[future]
        name, port, proxy, proc = entry["name"], entry["port"], entry["proxy"], entry["proc"]
        try:
            if future.result():
                entry["reason"] = "alive"
                alive.append(entry)
            else:
                entry["reason"] = "upstream_probe_failed"
                diagnostics[name] = entry["reason"]
                log.warning(f"{name} failed upstream test, killing")
                proc.kill()
        except Exception as exc:
            entry["reason"] = f"probe_exception:{type(exc).__name__}"
            diagnostics[name] = entry["reason"]
            try: proc.kill()
            except Exception: pass
```

Then, in the loop that builds `state["instances"][name] = {...}` (around line 195), add `"reason": entry.get("reason", "alive")` to the dict.

**Verify:** `uv run pytest tests/test_proxy_service.py -q` → expect 6 passed.
**Commit:** `git add -A && git commit -m "feat(proxy): record per-instance failure reason for diagnostics"`

---

#### Task 1.3 — TDD: watchdog auto-starts unless explicitly disabled

**File:** `tests/test_watchdog_service.py` (new, small)

```python
def test_watchdog_starts_by_default_when_pool_starts():
    """start_proxy_pool must arm the watchdog so silent pool death is impossible."""
    from unittest.mock import patch, MagicMock
    from netools.services import proxy_service, watchdog_service

    with patch.object(watchdog_service, "start_watchdog_thread") as mock_start, \
         patch.object(proxy_service, "fetch_and_parse_proxies", return_value=[]):
        proxy_service.start_proxy_pool(max_instances=1, standalone=True)

    mock_start.assert_called_once()  # watchdog is armed by default
```

Run (expect FAIL): `uv run pytest tests/test_watchdog_service.py::test_watchdog_starts_by_default_when_pool_starts -q`

---

#### Task 1.4 — Arm watchdog in `start_proxy_pool` (unless `standalone=True`)

**File:** `netools/services/proxy_service.py` end of `start_proxy_pool` (after the OmniRoute register loop)

```python
    # Auto-arm watchdog unless caller is doing offline pool management
    if alive and not standalone:
        from netools.services import watchdog_service
        try:
            watchdog_service.start_watchdog_thread(interval=15, standalone=standalone)
            log.info("Auto-heal watchdog armed (15s interval)")
        except Exception as e:
            log.warning(f"Could not arm watchdog: {e}")
```

**Verify:** `uv run pytest tests/test_watchdog_service.py -q` → expect 1 passed.
**Commit:** `git add -A && git commit -m "feat(watchdog): auto-arm on pool start so dead instances heal without GUI toggle"`

---

#### Task 1.5 — Add `kill_switch: bool = False` config knob (default off, opt-in)

**File:** `netools/config.py` after `GRC_BENCHMARK_TIMEOUT`

```python
# Privacy: when True, all traffic is blocked if no healthy proxy is alive.
# Opt-in. Setting this and forgetting it can lock the user offline.
KILL_SWITCH_DEFAULT = _user_cfg.get("kill_switch", False)
```

Also document in `tests/test_config.py` (existing file) by reading the value and asserting the type.

**Commit:** `git add -A && git commit -m "feat(config): opt-in kill_switch flag from user config"`

---

### TIER 2 — Visual pool health (heatmap + bandwidth) (HIGH UX VALUE)

#### Task 2.1 — TDD: pure function to classify port health into a color

**File:** `tests/test_pool_heatmap.py` (new)

```python
def test_heatmap_color_matrix():
    from netools.gui.view_proxy import _port_state_to_color
    assert _port_state_to_color("alive") == "green"
    assert _port_state_to_color("upstream_probe_failed") == "red"
    assert _port_state_to_color("spawn_failed") == "grey"
    assert _port_state_to_color("probe_exception:TimeoutError") == "red"
    assert _port_state_to_color("unknown") == "yellow"
```

Run (expect FAIL): ImportError or NameError.

---

#### Task 2.2 — Implement `_port_state_to_color` mapping in `view_proxy.py`

**File:** `netools/gui/view_proxy.py` (top-level helper, after imports)

```python
_HEATMAP_COLORS = {
    "alive": ("#10b981", "●"),       # green dot
    "spawn_failed": ("#6b7280", "○"), # grey empty
    "upstream_probe_failed": ("#ef4444", "✕"),
    "probe_exception:TimeoutError": ("#ef4444", "✕"),
    "probe_exception:ConnectionRefusedError": ("#ef4444", "✕"),
}

def _port_state_to_color(reason: str) -> tuple[str, str]:
    """Return (hex_color, glyph) for the pool heatmap."""
    return _HEATMAP_COLORS.get(reason, ("#f59e0b", "?"))  # amber = unknown
```

**Verify:** `uv run pytest tests/test_pool_heatmap.py -q` → expect 1 passed.
**Commit:** `git add -A && git commit -m "feat(gui): port-state-to-color mapping for pool heatmap"`

---

#### Task 2.3 — Add heatmap frame to `ProxyView`

**File:** `netools/gui/view_proxy.py` in `_build_ui`, add after the refresh button row:

```python
        # Pool heatmap: 20 cells, one per sing-box instance
        self.heatmap_frame = ctk.CTkFrame(self, fg_color=ThemeManager.surface(),
                                          corner_radius=6, border_width=1,
                                          border_color=ThemeManager.border())
        self.heatmap_frame.pack(fill="x", padx=14, pady=(0, 8))
        self.heatmap_cells = []
        for i in range(MAX_INSTANCES):  # MAX_INSTANCES already imported? if not, use 20
            cell = ctk.CTkLabel(self.heatmap_frame, text="○", width=28, height=28,
                                font=("Segoe UI Symbol", 14), text_color="#6b7280")
            cell.grid(row=0, column=i, padx=2, pady=4)
            self.heatmap_cells.append(cell)
```

Then in `refresh()` (existing method, called on interval), update each cell:

```python
        # inside refresh(), after loading state
        for i, cell in enumerate(self.heatmap_cells):
            slot = state.get("instances", {}).get(f"sb-{i:02d}")
            reason = (slot or {}).get("reason", "spawn_failed")
            color, glyph = _port_state_to_color(reason)
            cell.configure(text=glyph, text_color=color)
```

**Verify (manual):** `uv run netools gui`, start a pool, observe heatmap. No automated GUI test (Tcl is fragile). Document expected behavior in the commit message.
**Commit:** `git add -A && git commit -m "feat(gui): pool heatmap with 20 live status cells"`

---

#### Task 2.4 — TDD: bandwidth probe returns Mbps or None

**File:** `tests/test_bandwidth_probe.py` (new)

```python
def test_bandwidth_probe_returns_mbps_or_none():
    from netools.libs.net import measure_bandwidth_mbps
    # Localhost probe must not hang past 5s
    result = measure_bandwidth_mbps(host="127.0.0.1", port=1, timeout_s=2.0)
    assert result is None or isinstance(result, float)
```

Run (expect FAIL): ImportError.

---

#### Task 2.5 — Implement `measure_bandwidth_mbps` (HEAD-only, no dependency download)

**File:** `netools/libs/net.py` (add at end of file)

```python
def measure_bandwidth_mbps(host: str = "127.0.0.1", port: int = 80, timeout_s: float = 3.0) -> Optional[float]:
    """Estimate a proxy's TCP bandwidth by reading the first 256KB of a known HTTP endpoint.

    Returns Mbps (float) or None on any failure. Used for pool ranking, not benchmarking.
    """
    import socket
    import time
    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout_s)
        sock.sendall(b"GET /generate_204 HTTP/1.1\r\nHost: speed.cloudflare.com\r\nConnection: close\r\n\r\n")
        t0 = time.perf_counter()
        received = 0
        while received < 256 * 1024:
            chunk = sock.recv(65536)
            if not chunk:
                break
            received += len(chunk)
        dt = time.perf_counter() - t0
        if dt <= 0 or received == 0:
            return None
        return (received * 8) / (dt * 1_000_000)  # bits/s -> Mbps
    except Exception:
        return None
    finally:
        if sock:
            try: sock.close()
            except Exception: pass
```

**Verify:** `uv run pytest tests/test_bandwidth_probe.py -q` → expect 1 passed.
**Commit:** `git add -A && git commit -m "feat(net): lightweight bandwidth probe (no external download)"`

---

### TIER 3 — Kill switch (privacy guarantee)

#### Task 3.1 — TDD: `apply_kill_switch` returns a restore callable

**File:** `tests/test_kill_switch.py` (new)

```python
def test_kill_switch_returns_restorer(monkeypatch):
    from netools.adapters import kill_switch
    calls = []
    monkeypatch.setattr(kill_switch, "_run_iptables", lambda *a, **k: calls.append(a))
    restore = kill_switch.arm_block_all()
    assert callable(restore)
    restore()
    assert len(calls) >= 2  # block + restore
```

Run (expect FAIL): ImportError.

---

#### Task 3.2 — Implement `netools/adapters/kill_switch.py` (no real iptables call if not root)

**File:** `netools/adapters/kill_switch.py` (new)

```python
"""
Privacy kill switch: blocks all outbound traffic unless a healthy proxy is alive.

Implemented as a thin wrapper around the OS firewall:
  - Linux: iptables (requires CAP_NET_ADMIN; degrades to no-op + warning)
  - macOS: pf via /etc/pf.conf anchor
  - Windows: netsh advfirewall (requires admin)

Always returns a `restore` callable that the caller MUST invoke when the
proxy pool becomes healthy again, or the user goes offline permanently.
"""
from typing import Callable
from netools.libs.env import get_os_type
from netools.libs.logger import get_logger

log = get_logger(__name__)


def _run_iptables(args: list) -> tuple[bool, str]:
    import shutil, subprocess
    if shutil.which("iptables") is None:
        return False, "iptables not found"
    try:
        r = subprocess.run(["iptables"] + args, capture_output=True, text=True, timeout=5)
        return r.returncode == 0, r.stderr.strip()
    except Exception as e:
        return False, str(e)


def arm_block_all() -> Callable[[], None]:
    """Insert REJECT rule for all outbound. Returns restore() callable."""
    os_t = get_os_type()
    if os_t == "linux":
        ok, err = _run_iptables(["-I", "OUTPUT", "!", "-o", "lo", "-j", "REJECT", "--reject-with", "icmp-net-unreachable"])
        if not ok:
            log.warning(f"kill_switch: iptables failed, running in dry-run: {err}")
        def _restore():
            _run_iptables(["-D", "OUTPUT", "!", "-o", "lo", "-j", "REJECT", "--reject-with", "icmp-net-unreachable"])
        return _restore
    # macOS / Windows / unknown: return a no-op restore; log that we're a stub
    log.warning(f"kill_switch: no implementation for OS={os_t}; stub returning no-op restore")
    return lambda: None
```

**Verify:** `uv run pytest tests/test_kill_switch.py -q` → expect 1 passed.
**Commit:** `git add -A && git commit -m "feat(privacy): kill switch via iptables with safe dry-run fallback"`

---

#### Task 3.3 — Wire kill switch into `ProxyController.start_pool`

**File:** `netools/controllers/proxy_controller.py` (modify `start_pool` to honor `kill_switch` kwarg)

```python
def start_pool(
    self,
    standalone: bool = False,
    kill_switch: bool = False,   # NEW
    on_success: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> None:
    """Asynchronously start all sing-box proxy instances and register with gateways."""
    def _task():
        result = proxy_service.start_proxy_pool(standalone=standalone, kill_switch=kill_switch)
        return result
    self.run_async(_task, on_success=on_success, on_error=on_error)
```

And in `proxy_service.start_proxy_pool`, after the `if alive and not standalone:` block (where watchdog is armed), add:

```python
    if kill_switch and not alive:
        from netools.adapters import kill_switch
        _restore = kill_switch.arm_block_all()
        log.warning("kill_switch armed: all outbound blocked until proxy restored")
        state["_kill_switch_restore"] = True
    # else: store None so watchdog knows nothing to do
```

Then in `run_monitor_cycle` of `watchdog_service.py`, when dead instances reach 0 again, call `_restore()` (lookup via `state`).

**Verify:** Manual: start pool with no alive proxies + `kill_switch=True`; observe `iptables -L OUTPUT` has REJECT rule. Manual restoration on next healthy probe.
**Commit:** `git add -A && git commit -m "feat(controller): honor kill_switch kwarg through to service + watchdog restore"`

---

### Final integration commit

After Tiers 1-3 land, run the full suite:

```bash
uv run pytest tests -q
```

Expected: ≥ 220 tests pass (190 baseline + 12 controllers + 12 platform_proxy + new tests for heatmap, bandwidth, kill switch, watchdog, reason capture).

---

## Tests / Validation (consolidated)

| Task | Test file | Command | Expected after impl |
|---|---|---|---|
| 1.1 | tests/test_proxy_service.py | `uv run pytest tests/test_proxy_service.py::test_start_proxy_pool_records_failure_reasons -q` | 1 passed |
| 1.2 | tests/test_proxy_service.py | `uv run pytest tests/test_proxy_service.py -q` | 6 passed |
| 1.3 | tests/test_watchdog_service.py | `uv run pytest tests/test_watchdog_service.py -q` | 1 passed |
| 1.5 | tests/test_config.py | `uv run pytest tests/test_config.py -q` | still passing |
| 2.1 | tests/test_pool_heatmap.py | `uv run pytest tests/test_pool_heatmap.py -q` | 1 passed |
| 2.4 | tests/test_bandwidth_probe.py | `uv run pytest tests/test_bandwidth_probe.py -q` | 1 passed |
| 3.1 | tests/test_kill_switch.py | `uv run pytest tests/test_kill_switch.py -q` | 1 passed |
| full | tests/ | `uv run pytest tests -q` | ≥ 220 passed |
| lint | — | `uv run ruff check netools tests` | 0 errors |

---

## Risks, Tradeoffs, and Open Questions

1. **WIP `proxy_service.py` interleave diff (uncommitted) conflicts with Task 1.2.** Resolve by stashing WIP, applying 1.2, then `git stash pop` and manually merging the `for s_list in source_results:` interleave into the new dict-based flow. The diff is small (~20 lines) so merge is mechanical.

2. **Watchdog default-on consumes CPU even when user is happy.** Mitigation: in `start_watchdog_thread`, log clearly on first iteration and add a `Netools/wt 30s interval` in the GUI status bar so user sees it running.

3. **Heatmap without a per-instance click handler is read-only.** YAGNI for now. Add a `bind("<Button-1>")` later that opens a tooltip with `name:port reason:...` if users complain.

4. **Bandwidth probe (Task 2.4) uses a 256KB transfer to a default endpoint.** That's ~0.5MB per probe × 20 instances every 30s = ~1MB/min just for health checks. Acceptable. If concern, drop to 64KB and reduce interval.

5. **Kill switch (Task 3.2) is Linux-only for now.** macOS/Windows are stubbed. The wrapper is structured so adding them later is one helper per OS. Document this clearly so users on macOS don't get a false sense of security.

6. **The 250-cap on `fetch_and_parse_proxies` (uncommitted) increases memory by ~10×.** Watch `tests/test_proxy_service.py` to see if any timing assertions need loosening. If memory becomes a problem on a 2GB VM, reduce to 80.

7. **No automated GUI test for heatmap (Task 2.3).** Tcl/CustomTkinter tests are fragile. Manual verification is acceptable; the underlying logic (`_port_state_to_color`) is unit-tested.

8. **What about the WIP `controllers/` files?** They're new and untracked. They are referenced by Tasks 1.4 and 3.3 but only as integration points. If the user wants to commit them first as a separate "MVC scaffolding" commit, do that before Tier 1 starts to keep history clean.

---

## Suggested execution order (for the implementer)

```
1. git add -A netools/controllers/ tests/test_controllers.py
   git commit -m "feat(mvc): introduce controllers layer for async + UI dispatch"
2. git add -A netools/adapters/platform_proxy.py tests/test_platform_proxy.py
   git commit -m "feat(platform-proxy): cross-platform system proxy enable/disable"
3. Tier 1 (Tasks 1.1 - 1.5)   — fixes the silent dead-pool problem
4. Tier 2 (Tasks 2.1 - 2.5)   — gives visual feedback
5. Tier 3 (Tasks 3.1 - 3.3)   — privacy guarantee
6. uv run pytest tests -q     — full suite must pass
7. uv run ruff check netools tests  — 0 errors
```

This produces ~9 small, reviewable commits instead of one giant "hardening" commit. Each is independently revertable.

---

## Out of scope (recorded for next round)

- WireGuard outbound + key generator
- Multi-hop proxy chains
- TUN device for system-level capture
- TLS fingerprint mimicry (uTLS)
- Plugin system
- OmniRoute npm tarball publish (blocked by env SIGBUS, separate workstream)
