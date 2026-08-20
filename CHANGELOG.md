# Changelog 📜

All notable changes to **Netools Suite** are documented in this file.

---

## [2.0.0] - 2026-08-20

### 🚀 Added
- **GRC 3-Tier Benchmark Engine:** Real-time streaming DNS benchmarking across 90+ global & regional resolvers for IPv4, IPv6, DoH, and DoT.
- **Universal DNS & Encryption Inspector:** Provider-agnostic live socket & TLS 853 handshake diagnostics.
- **VLESS Proxy Parser:** Full support for `vless://` URIs with WebSocket, gRPC, TLS, and REALITY.
- **Category Preset Filter:** Dynamic DNS preset filtering (Security & Privacy, Gaming / Fast, Ad-Blocking, Family Safe, Asia-Pacific, Global Anycast).
- **System Tray Quick DNS Switcher:** 1-click DNS and Proxy switching directly from the OS taskbar / tray.
- **Deterministic Verification Gate (`verify_all.sh`):** Automated pre-commit and CI verification pipeline.
- **Packaging:** Added `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, and `Dockerfile`.

### 🛠️ Fixed
- Fixed thread safety in `view_settings.py` by capturing widget values on the main thread.
- Fixed `+DNSOverTLS` persistence in `systemd_dns.py` by ordering NetworkManager updates before resolvectl.
- Prevented window modal duplication with Singleton Focus management.
- Removed hardcoded fallback tokens in `config.py`.

---

## [1.0.0] - Initial Release
- Basic Sing-box proxy rotator and 9Router connection sync.
- Static PAC auto-config server on port 18080.
- CustomTkinter desktop interface.
