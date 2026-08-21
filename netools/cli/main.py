"""
Unified CLI Command Controller for Netools Suite.
"""

import argparse
import signal
import subprocess
import sys

from netools.adapters import platform_dns as sys_dns
from netools.config import BASE_DIR, DOH_PROXY_PORT, PAC_SERVER_PORT, WEB_APP_PORT
from netools.services import dns_service, doh_service, pac_service, proxy_service, watchdog_service


def _register_graceful_shutdown(standalone: bool = False):
    """Register SIGTERM/SIGINT handlers for clean proxy shutdown."""
    def _handler(signum, frame):
        print("\n[INFO] Shutting down gracefully...")
        proxy_service.stop_proxy_pool(standalone=standalone)
        sys.exit(0)
    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)

def cmd_proxy(args):
    """Handle proxy commands."""
    action = args.proxy_action
    standalone = args.no_9r

    if action == "start":
        _register_graceful_shutdown(standalone)
        proxy_service.start_proxy_pool(standalone=standalone)
    elif action == "stop":
        proxy_service.stop_proxy_pool(standalone=standalone)
    elif action == "refresh":
        proxy_service.refresh_proxy_pool(standalone=standalone)
    elif action == "status":
        stat = proxy_service.get_proxy_status()
        print(f"Active Sing-box instances: {stat['alive_count']}/{stat['total']}")
        for inst in stat["instances"]:
            mark = "✓" if inst["alive"] else "✗"
            print(f"  {mark} {inst['name']}: {inst['proxy_type']} → {inst['server']} → SOCKS {inst['port']} | HTTP {inst['http_port']} ({inst['started_at']})")
    elif action == "monitor":
        interval = args.interval or 30
        _register_graceful_shutdown(standalone)
        watchdog_service.run_watchdog_loop(interval=interval, standalone=standalone)
    else:
        print("Usage: netools proxy {start,stop,refresh,status,monitor}")

def cmd_dns(args):
    """Handle DNS commands."""
    action = args.dns_action
    if action == "flush":
        sys_dns.flush_dns_cache()
        print("✓ System DNS cache successfully flushed.")
    elif action == "restore":
        ifaces = sys_dns.get_network_interfaces()
        if ifaces:
            dev = ifaces[0]["device"]
            conn = ifaces[0]["connection"]
            sys_dns.restore_default_dns(dev, conn)
            print(f"✓ Network adapter '{dev}' restored to DHCP default.")
        else:
            print("❌ No active network adapter found.")
    elif action == "presets":
        provs = dns_service.get_providers()
        print(f"Available DNS Resolvers ({len(provs)} total):")
        for k, p in provs.items():
            print(f"  {p['country']} {p['name']} ({k}) - IPv4: {', '.join(p.get('ipv4', []))}")
    elif action == "apply":
        ifaces = sys_dns.get_network_interfaces()
        if not ifaces:
            print("❌ No active network adapter.")
            return
        dev = ifaces[0]["device"]
        conn = ifaces[0]["connection"]
        ips = args.ips or ["1.1.1.1", "1.0.0.1"]
        sys_dns.apply_system_dns(dev, ips, connection_name=conn)
        print(f"✓ Applied DNS ({', '.join(ips)}) to '{dev}'.")
    elif action == "doh":
        port = args.port or DOH_PROXY_PORT
        if args.stop:
            doh_service.stop_doh_forwarder()
            print("✓ DoH forwarder dihentikan.")
        elif doh_service.is_doh_forwarder_running():
            print(f"🔒 DoH forwarder sudah aktif di udp://127.0.0.1:{port} ({args.provider}).")
        elif doh_service.start_doh_forwarder(provider=args.provider, port=port):
            print(f"🔒 DoH forwarder aktif di udp://127.0.0.1:{port} ({args.provider}).")
        else:
            print(f"❌ Gagal menjalankan DoH forwarder ({args.provider}).")
    else:
        print("Usage: netools dns {apply,flush,restore,presets,doh}")

def cmd_pac(args):
    """Handle PAC server commands."""
    action = args.pac_action
    if action == "start":
        port = args.port or PAC_SERVER_PORT
        pac_service.start_pac_server_blocking(port=port)
    elif action == "stop":
        pac_service.stop_pac_server()
        print("✓ PAC Server stopped.")
    elif action == "status":
        running = pac_service.is_pac_server_running()
        stat_str = "🟢 Running" if running else "⚪ Stopped"
        print(f"PAC Server Status: {stat_str}")
        print(f"PAC URL: {pac_service.get_pac_url()}")
    else:
        print("Usage: netools pac {start,stop,status}")

def cmd_web(args):
    """Serve Web App for GitHub Pages preview."""
    port = args.port or WEB_APP_PORT
    print(f"🌐 Netools Web App running at http://127.0.0.1:{port}/")
    subprocess.run([sys.executable, "-m", "http.server", str(port), "--directory", str(BASE_DIR / "docs")])

def cmd_gui(args):
    """Launch Desktop GUI All-In-One."""
    from netools.gui.app import main as run_gui
    run_gui()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="netools",
        description="⚡ Netools Suite: Sing-box Proxy Rotator, DNS Searcher/Jumper, PAC Server & AI Gateway Sync"
    )
    subparsers = parser.add_subparsers(dest="command")

    # proxy subcommand
    p_proxy = subparsers.add_parser("proxy", help="Sing-box Proxy Pool Management")
    p_proxy.add_argument("proxy_action", choices=["start", "stop", "refresh", "status", "monitor"], default="status", nargs="?")
    p_proxy.add_argument("--no-9r", action="store_true", help="Standalone mode (skip 9Router registration)")
    p_proxy.add_argument("interval", type=int, nargs="?", default=30, help="Monitor auto-heal interval in seconds")

    # dns subcommand
    p_dns = subparsers.add_parser("dns", help="DNS Searcher & GRC Benchmark")
    p_dns.add_argument("dns_action", choices=["apply", "flush", "restore", "presets", "doh"], default="presets", nargs="?")
    p_dns.add_argument("ips", nargs="*", help="DNS IP addresses to apply")
    p_dns.add_argument("--provider", default="alidns", help="DoH provider for local forwarder")
    p_dns.add_argument("--port", type=int, default=5353, help="Port for DoH forwarder")
    p_dns.add_argument("--stop", action="store_true", help="Stop the DoH forwarder")

    # pac subcommand
    p_pac = subparsers.add_parser("pac", help="PAC Auto-Config Server")
    p_pac.add_argument("pac_action", choices=["start", "stop", "status"], default="status", nargs="?")
    p_pac.add_argument("--port", type=int, default=PAC_SERVER_PORT)

    # web subcommand
    p_web = subparsers.add_parser("web", help="Run Web App preview")
    p_web.add_argument("--port", type=int, default=WEB_APP_PORT)

    # gui subcommand
    subparsers.add_parser("gui", help="Launch Desktop GUI All-In-One")
    return parser

def main():
    from netools.libs.dns_async import init_async_loop
    init_async_loop()
    from netools.config import ensure_runtime_dirs
    ensure_runtime_dirs()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "proxy":
        cmd_proxy(args)
    elif args.command == "dns":
        cmd_dns(args)
    elif args.command == "pac":
        cmd_pac(args)
    elif args.command == "web":
        cmd_web(args)
    elif args.command == "gui" or args.command is None:
        cmd_gui(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
