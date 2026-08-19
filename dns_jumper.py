#!/usr/bin/env python3
"""
DNS Jumper CLI for Linux (Fedora & systemd-resolved / NetworkManager)
Real-time 3-Tier GRC Benchmark, Regional Filters, Auto-Jump, and Local Encrypted DoH Proxy.
"""

import os
import sys
import time
import json
import socket
import struct
import signal
import asyncio
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Ensure correct base directory for imports
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import dns_jumper_db as db
import dns_jumper_benchmark as bm

try:
    import httpx
except ImportError:
    print("[ERROR] 'httpx' is required. Install via: pip install 'httpx[http2]'")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich import print as rprint
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None

APP_DIR = Path.home() / ".local" / "share" / "dns-jumper"
PID_FILE = APP_DIR / "doh_proxy.pid"
STATE_FILE = APP_DIR / "state.json"


def get_active_interface() -> Tuple[Optional[str], Optional[str]]:
    """Detect default network interface and active NetworkManager connection."""
    interface = None
    connection = None
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        for line in out.splitlines():
            parts = line.split()
            if "dev" in parts:
                idx = parts.index("dev")
                if idx + 1 < len(parts):
                    interface = parts[idx + 1]
                    break
    except Exception:
        pass

    try:
        out = subprocess.check_output(["nmcli", "-t", "-f", "NAME,DEVICE,TYPE", "connection", "show", "--active"], text=True)
        for line in out.splitlines():
            parts = line.strip().split(":")
            if len(parts) >= 2:
                conn_name, dev = parts[0], parts[1]
                if interface and dev == interface:
                    connection = conn_name
                    break
                elif not interface and parts[2] not in ("loopback", "bridge"):
                    connection = conn_name
                    interface = dev
                    break
    except Exception:
        pass

    return interface, connection


def get_current_system_dns(interface: Optional[str]) -> List[str]:
    """Retrieve currently active DNS servers from resolvectl or nmcli."""
    dns_servers = []
    if interface:
        try:
            out = subprocess.check_output(["resolvectl", "dns", interface], text=True)
            if ":" in out:
                servers_part = out.split(":", 1)[1].strip()
                dns_servers = servers_part.split()
        except Exception:
            pass

    if not dns_servers:
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.startswith("nameserver") and not line.split()[1].startswith("127.0.0.53"):
                        dns_servers.append(line.split()[1])
        except Exception:
            pass
    return dns_servers


async def run_cli_grc_benchmark(
    providers_dict: Dict[str, Any],
    tld_domains: List[str],
    mode: str = "doh",
    show_progress: bool = True
) -> List[bm.GRCBenchmarkResult]:
    """Run 3-tier GRC benchmark over DoH or UDP."""
    prov_list = list(providers_dict.items())
    results: List[bm.GRCBenchmarkResult] = []

    if mode == "doh":
        headers = {"Content-Type": "application/dns-message", "Accept": "application/dns-message"}
        sem = asyncio.Semaphore(10)
        async with httpx.AsyncClient(http2=True, headers=headers, verify=True) as client:
            if HAS_RICH and show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task("[bold cyan]Running 3-Tier GRC Benchmark...", total=len(prov_list))

                    async def sem_task(k, p):
                        async with sem:
                            res = await bm.benchmark_provider_grc_doh(client, k, p, tld_domains)
                            progress.advance(task)
                            return res

                    tasks = [sem_task(k, p) for k, p in prov_list if p.get("doh_url")]
                    raw_res = await asyncio.gather(*tasks)
                    results = [r for r in raw_res if r is not None]
            else:
                async def sem_task(k, p):
                    async with sem:
                        return await bm.benchmark_provider_grc_doh(client, k, p, tld_domains)
                tasks = [sem_task(k, p) for k, p in prov_list if p.get("doh_url")]
                raw_res = await asyncio.gather(*tasks)
                results = [r for r in raw_res if r is not None]
    else:
        # UDP Mode
        for k, p in prov_list:
            res = bm.benchmark_provider_grc_udp(k, p, tld_domains)
            results.append(res)

    results.sort(key=lambda r: (0 if r.status == "Stable" else (1 if "Partial" in r.status else 2), r.grc_score))
    return results


def display_grc_table(results: List[bm.GRCBenchmarkResult], current_dns: List[str], tld_name: str):
    """Render Rich table of GRC 3-tier results."""
    if not HAS_RICH:
        print(f"\n=== GRC 3-TIER DNS BENCHMARK ({tld_name}) ===")
        for i, r in enumerate(results, 1):
            is_active = any(ip in current_dns for ip in r.ipv4)
            print(f"{i:2d}. {r.name:<24} ({r.country}) | Cached: {r.cached_ms:5.1f}ms | Uncached: {r.uncached_ms:5.1f}ms | TLD: {r.tld_ms:5.1f}ms | Score: {r.grc_score:5.1f} {'[*ACTIVE*]' if is_active else ''}")
        return

    table = Table(title=f"⚡ GRC 3-Tier DNS Benchmark Results ({tld_name})", header_style="bold magenta", border_style="dim")
    table.add_column("Rank", justify="center", style="bold")
    table.add_column("DNS Provider", style="bold white")
    table.add_column("Origin", justify="center")
    table.add_column("🟢 Cached", justify="right", style="green")
    table.add_column("🔵 Uncached", justify="right", style="blue")
    table.add_column("🟡 TLD Latency", justify="right", style="yellow")
    table.add_column("GRC Score", justify="right", style="bold cyan")
    table.add_column("Status", justify="center")
    table.add_column("Primary IPv4", style="dim")

    for i, r in enumerate(results, 1):
        rank_str = f"🥇 #{i}" if i == 1 else (f"🥈 #{i}" if i == 2 else (f"🥉 #{i}" if i == 3 else f"#{i}"))
        is_active = any(ip in current_dns for ip in r.ipv4)
        name_display = f"{r.name} [bold green]● ACTIVE[/bold green]" if is_active else r.name

        c_str = f"{r.cached_ms:.1f} ms" if r.cached_lats else "N/A"
        u_str = f"{r.uncached_ms:.1f} ms" if r.uncached_lats else "N/A"
        t_str = f"{r.tld_ms:.1f} ms" if r.tld_lats else "N/A"
        score_str = f"[bold green]{r.grc_score:.1f}[/bold green]" if r.status == "Stable" else f"[red]{r.grc_score:.1f}[/red]"

        if r.status == "Stable":
            status_style = "[bold green]Stable[/bold green]"
        elif "Partial" in r.status:
            status_style = f"[yellow]{r.status}[/yellow]"
        else:
            status_style = "[red]Failed[/red]"

        table.add_row(
            rank_str,
            name_display,
            r.country,
            c_str,
            u_str,
            t_str,
            score_str,
            status_style,
            ", ".join(r.ipv4[:2]),
        )

    console.print(table)
    if results:
        fastest = results[0]
        console.print(Panel(
            f"[bold green]Fastest Recommended DNS:[/bold green] [bold cyan]{fastest.name}[/bold cyan] ({fastest.country})\n"
            f"Cached: [green]{fastest.cached_ms:.1f} ms[/green] | Uncached: [blue]{fastest.uncached_ms:.1f} ms[/blue] | TLD: [yellow]{fastest.tld_ms:.1f} ms[/yellow] | Score: [bold cyan]{fastest.grc_score:.1f}[/bold cyan]\n"
            f"Primary IPv4: [bold white]{', '.join(fastest.ipv4)}[/bold white]",
            title="🏆 GRC Recommendation",
            border_style="green"
        ))


def apply_dns_system(provider_key_or_ips: Any, persistent: bool = False, enable_dot: bool = False) -> bool:
    """Apply DNS settings to active network interface."""
    providers = db.load_providers()
    if isinstance(provider_key_or_ips, list):
        ips = provider_key_or_ips
        prov_name = ", ".join(ips)
    elif provider_key_or_ips in providers:
        p = providers[provider_key_or_ips]
        ips = p.get("ipv4", [])
        prov_name = p["name"]
    else:
        ips = [ip.strip() for ip in str(provider_key_or_ips).split(",") if ip.strip()]
        prov_name = ", ".join(ips)

    interface, connection = get_active_interface()
    if not interface:
        print("[ERROR] Could not detect active network interface.")
        return False

    print(f"\n[+] Applying DNS '{prov_name}' ({', '.join(ips)}) to {interface}...")
    success = True
    try:
        cmd = ["resolvectl", "dns", interface] + ips
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            res_sudo = subprocess.run(["sudo", "resolvectl", "dns", interface] + ips, capture_output=True, text=True)
            if res_sudo.returncode != 0:
                print(f"[!] resolvectl notice: {res_sudo.stderr.strip() or res_sudo.stdout.strip()}")
                success = False
            else:
                print(f"[✓] Set resolvectl DNS on {interface}.")
        else:
            print(f"[✓] Set resolvectl DNS on {interface}.")

        if enable_dot:
            subprocess.run(["resolvectl", "dnsovertls", interface, "opportunistic"], capture_output=True)
            print(f"[✓] Enabled DNS-over-TLS on {interface}.")
    except Exception as e:
        print(f"[!] resolvectl error: {e}")
        success = False

    if persistent and connection:
        try:
            ip_str = " ".join(ips)
            cmd_nm = ["nmcli", "connection", "modify", connection, "ipv4.dns", ip_str, "ipv4.ignore-auto-dns", "yes"]
            subprocess.run(cmd_nm, capture_output=True)
            subprocess.run(["nmcli", "connection", "up", connection], capture_output=True)
            print(f"[✓] NetworkManager connection '{connection}' updated persistently.")
        except Exception as e:
            print(f"[!] nmcli update error: {e}")

    try:
        subprocess.run(["resolvectl", "flush-caches"], capture_output=True)
        print("[✓] DNS cache flushed.")
    except Exception:
        pass

    return success


def flush_dns():
    try:
        subprocess.run(["resolvectl", "flush-caches"], capture_output=True)
        subprocess.run(["resolvectl", "reset-server-features"], capture_output=True)
        print("[✓] DNS cache flushed successfully via resolvectl.")
    except Exception as e:
        print(f"[!] Flush error: {e}")


def revert_dns():
    interface, connection = get_active_interface()
    if not interface:
        return
    print(f"\n[+] Reverting DNS on {interface} to default DHCP...")
    subprocess.run(["resolvectl", "revert", interface], capture_output=True)
    if connection:
        subprocess.run(["nmcli", "connection", "modify", connection, "ipv4.ignore-auto-dns", "no", "ipv4.dns", ""], capture_output=True)
        subprocess.run(["nmcli", "connection", "up", connection], capture_output=True)
    subprocess.run(["resolvectl", "flush-caches"], capture_output=True)
    print(f"[✓] Restored {interface} to DHCP DNS.")


def launch_gui():
    gui_script = BASE_DIR / "dns_jumper_gui.py"
    subprocess.run([sys.executable, str(gui_script)])


def main():
    parser = argparse.ArgumentParser(description="DNS Jumper for Linux - GRC 3-Tier Benchmark, Regional Filter, and DNS Switcher")
    parser.add_argument("--gui", action="store_true", help="Launch graphical user interface (GUI)")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Command: gui
    subparsers.add_parser("gui", help="Launch graphical user interface (GUI)")

    # Command: test
    test_p = subparsers.add_parser("test", help="Run 3-tier GRC DNS benchmark")
    test_p.add_argument("--region", choices=["all", "asia", "europe", "north_america", "global"], default="all", help="Filter by region (default: all)")
    test_p.add_argument("--tld", choices=["indonesia", "global_com", "non_profit_org"], default="indonesia", help="Target TLD preset (default: indonesia)")
    test_p.add_argument("--mode", choices=["doh", "udp"], default="doh", help="Benchmark protocol (doh or udp)")

    # Command: jump
    jump_p = subparsers.add_parser("jump", help="Benchmark and jump to fastest DNS")
    jump_p.add_argument("--region", choices=["all", "asia", "europe", "north_america", "global"], default="all", help="Filter by region")
    jump_p.add_argument("--tld", choices=["indonesia", "global_com", "non_profit_org"], default="indonesia", help="Target TLD preset")
    jump_p.add_argument("--persistent", action="store_true", help="Make persistent in NetworkManager")

    # Command: apply
    apply_p = subparsers.add_parser("apply", help="Apply specific DNS provider or IPs")
    apply_p.add_argument("provider", help="Provider key (e.g. alidns, cloudflare, quad9) or comma-separated IPs")
    apply_p.add_argument("--persistent", action="store_true", help="Make persistent in NetworkManager")
    apply_p.add_argument("--dot", action="store_true", help="Enable DNS-over-TLS")

    # Command: sync-db
    subparsers.add_parser("sync-db", help="Synchronize DoH resolver database from cloud")

    # Command: flush
    subparsers.add_parser("flush", help="Flush DNS resolver cache")

    # Command: reset
    subparsers.add_parser("reset", help="Revert system DNS to default DHCP")

    # Command: status
    subparsers.add_parser("status", help="Show current system DNS status")

    # Command: list
    list_p = subparsers.add_parser("list", help="List available DNS providers")
    list_p.add_argument("--region", choices=["all", "asia", "europe", "north_america", "global"], default="all")

    args = parser.parse_args()

    if args.gui or args.command == "gui":
        launch_gui()
        return

    if not args.command:
        if "DISPLAY" in os.environ or "WAYLAND_DISPLAY" in os.environ:
            launch_gui()
        else:
            interface, _ = get_active_interface()
            dns_list = get_current_system_dns(interface)
            print(f"Interface: {interface} | Active DNS: {', '.join(dns_list)}")
        return

    providers = db.load_providers()
    interface, _ = get_active_interface()
    current_dns = get_current_system_dns(interface)

    if args.command == "test":
        filtered = db.filter_providers(providers, region=args.region, only_doh=(args.mode == "doh"))
        tld_domains = db.TLD_PRESETS.get(args.tld, db.TLD_PRESETS["indonesia"])["domains"]
        tld_name = db.TLD_PRESETS.get(args.tld, db.TLD_PRESETS["indonesia"])["name"]
        results = asyncio.run(run_cli_grc_benchmark(filtered, tld_domains, mode=args.mode))
        display_grc_table(results, current_dns, tld_name)

    elif args.command == "jump":
        filtered = db.filter_providers(providers, region=args.region)
        tld_domains = db.TLD_PRESETS.get(args.tld, db.TLD_PRESETS["indonesia"])["domains"]
        results = asyncio.run(run_cli_grc_benchmark(filtered, tld_domains, mode="doh"))
        if results and results[0].status == "Stable":
            fastest = results[0]
            display_grc_table(results, current_dns, args.tld)
            apply_dns_system(fastest.key, persistent=args.persistent)

    elif args.command == "apply":
        apply_dns_system(args.provider, persistent=args.persistent, enable_dot=args.dot)

    elif args.command == "sync-db":
        succ, msg, count = db.sync_cloud_providers()
        print(f"[+] {msg}")

    elif args.command == "flush":
        flush_dns()

    elif args.command == "reset":
        revert_dns()

    elif args.command == "status":
        if HAS_RICH:
            grid = Table.grid(padding=(0, 2))
            grid.add_column(style="bold cyan")
            grid.add_column(style="white")
            grid.add_row("Active Interface:", interface or "Unknown")
            grid.add_row("Current DNS:", ", ".join(current_dns) if current_dns else "None")
            console.print(Panel(grid, title="ℹ️ System DNS Status", border_style="cyan"))
        else:
            print(f"Interface: {interface} | Current DNS: {', '.join(current_dns)}")

    elif args.command == "list":
        filtered = db.filter_providers(providers, region=args.region)
        if HAS_RICH:
            table = Table(title=f"DNS Providers ({args.region.title()})", border_style="dim")
            table.add_column("Key", style="bold cyan")
            table.add_column("Name", style="bold white")
            table.add_column("Origin", justify="center")
            table.add_column("IPv4", style="green")
            table.add_column("DoH URL", style="dim")
            for k, p in filtered.items():
                table.add_row(k, p["name"], p.get("country", ""), ", ".join(p.get("ipv4", [])[:2]), p.get("doh_url", ""))
            console.print(table)
        else:
            for k, p in filtered.items():
                print(f"{k:<20} {p['name']} ({p.get('country','')}) -> {', '.join(p.get('ipv4', []))}")


if __name__ == "__main__":
    main()
