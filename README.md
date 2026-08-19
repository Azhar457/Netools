<div align="center">

# ⚡ Netools Suite v2.0
**Modern DNS Searcher, GRC 3-Tier Benchmark, Sing-box Proxy Rotator & AI Gateway Router**

[![Linux AppImage](https://img.shields.io/badge/Platform-Linux%20AppImage-blue?logo=linux)](https://github.com/Azhar457/Netools)
[![Windows EXE](https://img.shields.io/badge/Platform-Windows%20EXE-blue?logo=windows)](https://github.com/Azhar457/Netools)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen?logo=python)](https://python.org)
[![Sing-box 1.13+](https://img.shields.io/badge/Sing--box-1.13%2B-orange)](https://sing-box.sagernet.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 🌟 Overview

**Netools Suite** is an all-in-one network optimization and proxy rotation utility built with **Clean Layered Architecture** (*Controller, Service, Middleware, Adapter, Libs*). It combines:

1. **⚡ DNS Jumper & Real-Time GRC 3-Tier Benchmark**:
   - Live row-by-row streaming benchmark across 50+ global & regional DNS resolvers.
   - GRC 3-Tier Latency profiling: 🟢 Cached, 🔵 Uncached, 🟡 Dot-Com / Country TLD (.id, .com, .org).
   - **Smart Mix Algorithm**: Automatically picks the fastest trio (1 best Cached + 1 best Uncached + 1 best TLD) for optimal DNS resolution.
   - 3-slot DNS Switcher (Primary, Secondary, Tertiary), DNS over TLS (DoT), Flush DNS, and Restore DHCP.

2. **🌐 Turbo Sing-box Proxy Rotator**:
   - Downloads and verifies public proxy configs in parallel (15 workers, ~3-4s total startup).
   - Manages 20 local SOCKS5 (`11080–11099`) and HTTP (`21080–21099`) outbound proxy slots.
   - Auto-Heal Watchdog: Continuously monitors proxy health and replaces dead slots automatically.

3. **📜 Dynamic PAC Auto-Config Server**:
   - Built-in HTTP server on `http://127.0.0.1:18080/proxy.pac`.
   - 1-Click Copy and integration with GNOME Network Settings and Web Browsers.

4. **🔌 9Router & OmniRoute AI Gateway Sync**:
   - Automatically binds proxy pools to active AI provider connections (OpenAI, Anthropic, DeepSeek, OpenCode, Nvidia NIM, etc.).
   - Fail-safe standalone operation when backend is offline.

5. **⚙️ Preferences, UI Scaling & DNS Management**:
   - Dynamic UI Font Scaling (80% to 140%).
   - DNS database Import (`.json`/`.txt`), Export, and Cloud Sync.

---

## 🏗️ Architecture

```text
netools/
├── config.py           # Global settings & port mapping (11080, 21080, 18080, 20128)
├── state.py            # Thread-safe runtime state manager
│
├── libs/               # 🧰 Pure Stateless Utilities
│   ├── net.py          # Socket ping, port check, upstream curl test
│   ├── parsers.py      # Universal URI parser (Shadowsocks, Trojan, VMess, VLESS)
│   └── dns_packet.py   # RFC 8484 DNS Packet wireformat builder
│
├── adapters/           # 🔌 System Drivers & Gateway Clients
│   ├── singbox.py      # Sing-box process supervisor & config generator
│   ├── systemd_dns.py  # resolvectl & NetworkManager controller
│   ├── ninerouter.py   # 9Router REST API adapter
│   └── omniroute.py    # OmniRoute REST API adapter
│
├── middlewares/        # ⚙️ Pipeline Interceptors
│   ├── dns_injector.py # Smart DoH injector for Sing-box
│   └── backend_guard.py# Fail-safe decorator for offline backends
│
├── services/           # 🧠 Core Domain Business Logic
│   ├── proxy_service.py# Proxy pool lifecycle & parallel upstream testing
│   ├── dns_service.py  # GRC benchmark & Smart Mix calculator
│   ├── pac_service.py  # Dynamic PAC HTTP server
│   └── watchdog_service.py # Auto-heal monitor loop
│
├── cli/                # 💻 CLI Controllers
│   └── main.py         # Terminal dispatcher (proxy, dns, pac, web, gui)
│
└── gui/                # 🖥️ Modern Desktop GUI (CustomTkinter)
    ├── app.py          # Container window & Tabview manager
    ├── toast.py        # In-App Non-blocking Snackbar Toast manager
    ├── view_dashboard.py   # Tab 1: Live Status Dashboard
    ├── view_dns.py         # Tab 2: DNS Switcher & GRC Launcher
    ├── view_benchmark_modal.py # Real-Time GRC Benchmark Modal
    ├── view_proxy.py       # Tab 3: Proxy Rotator & Watchdog
    ├── view_settings.py    # Tab 4: 9Router AI Gateway Sync
    └── view_preferences.py # Tab 5: Settings, Scaling & About
```

---

## 🚀 Quick Start

### Running the Desktop GUI
```bash
# Launch GUI All-In-One
netools gui
# or
./dist/Netools-x86_64.AppImage
```

### CLI Commands
```bash
# Proxy Subsystem
netools proxy start        # Start proxy pool & upstream test
netools proxy status       # View active proxy slots
netools proxy stop         # Stop pool & clean up

# DNS Subsystem
netools dns presets        # List available DNS resolvers
netools dns flush          # Flush system DNS cache

# PAC Subsystem
netools pac start          # Start PAC server on 127.0.0.1:18080
netools pac status         # Show PAC status & URL
netools pac stop           # Stop PAC server
```

---

## 📦 Building Single-File Binaries

### Linux AppImage
```bash
chmod +x scripts/build_appimage.sh
./scripts/build_appimage.sh
# Output: dist/Netools-x86_64.AppImage
```

### Windows Single .EXE
```cmd
scripts\build_windows_exe.bat
REM Output: dist\netools.exe
```

---

## 📄 License
MIT License. Created with ❤️ by Azhar & Contributors.
