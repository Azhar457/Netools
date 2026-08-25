"""
Scalable & Modular i18n Localization Engine for Netools Suite.
Supports English ("en") and Bahasa Indonesia ("id") with one-line extensibility for future languages.

Usage:
    from netools.gui.i18n import tr, get_locale, set_locale
    tr("Check Now")                       # returns translated string for current locale
    tr("Connected to {target}", target="1.1.1.1") # with formatting
    tr("Applied", lang="id")              # explicit locale

Extensibility:
    register_locale("ja", "🇯🇵 日本語", ja_strings_dict)
"""

from __future__ import annotations

import json
from typing import Any, Optional

from netools.config import USER_CONFIG_DIR, USER_CONFIG_FILE
from netools.libs.logger import get_logger

log = get_logger(__name__)

# Registry of supported locales: code -> display label
_LOCALE_REGISTRY: dict[str, str] = {
    "en": "🇬🇧 English",
    "id": "🇮🇩 Bahasa Indonesia",
}

_current_locale: Optional[str] = None

# Master translation dictionary: key (English canonical) -> {locale_code: translated_text}
_TRANSLATIONS: dict[str, dict[str, str]] = {
    # -----------------------------------------------------------------------
    # Navigation & Header
    # -----------------------------------------------------------------------
    "⚡ Netools Suite v2.0": {"id": "⚡ Netools Suite v2.0"},
    "Unified Sing-box Rotator, Real-Time GRC DNS Benchmark & AI Gateway Router": {
        "id": "Rotator Sing-box Terpadu, Benchmark DNS GRC Real-Time & Router AI Gateway",
    },
    "● System Ready": {"id": "● Sistem Siap"},
    "● Initializing...": {"id": "● Menginisialisasi..."},
    "📊 Dashboard": {"id": "📊 Dasbor"},
    "⚡ DNS Suite": {"id": "⚡ DNS Suite"},
    "🌐 Proxy Rotator": {"id": "🌐 Proxy Rotator"},
    "🔌 9Router & AI Sync": {"id": "🔌 9Router & AI Sync"},
    "⚙️ Settings & About": {"id": "⚙️ Pengaturan & Info"},

    # -----------------------------------------------------------------------
    # Window & Tray Notifications
    # -----------------------------------------------------------------------
    "Netools aktif di latar belakang (System Tray). PAC & proxy tetap berjalan.": {
        "id": "Netools aktif di latar belakang (System Tray). PAC & proxy tetap berjalan.",
    },
    "Netools diminimalkan ke taskbar. PAC & proxy tetap berjalan.": {
        "id": "Netools diminimalkan ke taskbar. PAC & proxy tetap berjalan.",
    },
    "Netools active in background (System Tray). PAC & proxy remain running.": {
        "id": "Netools aktif di latar belakang (System Tray). PAC & proxy tetap berjalan.",
    },
    "Netools minimized to taskbar. PAC & proxy remain running.": {
        "id": "Netools diminimalkan ke taskbar. PAC & proxy tetap berjalan.",
    },
    "⚡ Buka Netools GUI": {"id": "⚡ Buka Netools GUI"},
    "⚡ Open Netools GUI": {"id": "⚡ Buka Netools GUI"},
    "🌐 Quick DNS Switch": {"id": "🌐 Ganti DNS Cepat"},
    "🚀 Start Proxy Pool": {"id": "🚀 Jalankan Proxy Pool"},
    "🛑 Stop Proxy Pool": {"id": "🛑 Hentikan Proxy Pool"},
    "♻️ Flush DNS Cache": {"id": "♻️ Bersihkan Cache DNS"},
    "❌ Keluar (Exit)": {"id": "❌ Keluar (Exit)"},
    "❌ Exit Netools": {"id": "❌ Keluar (Exit)"},
    "↩️ Restore DHCP Default": {"id": "↩️ Kembalikan ke DHCP"},

    # -----------------------------------------------------------------------
    # Tab 1: Dashboard View
    # -----------------------------------------------------------------------
    "📊 System Overview & Live Telemetry": {"id": "📊 Ringkasan Sistem & Telemetri Langsung"},
    "🚀 1-Click Operations": {"id": "🚀 Operasi 1-Klik Cepat"},
    "⚡ 1-Click Fix & Optimize": {"id": "⚡ 1-Klik Optimasi & Perbaiki"},
    "♻️ Flush OS DNS": {"id": "♻️ Bersihkan DNS OS"},
    "🔍 DPI Flow Inspector": {"id": "🔍 Visual DPI Flow Inspector"},
    "🔄 Refresh Status": {"id": "🔄 Segarkan Status"},
    "🌐 Active DNS Resolver": {"id": "🌐 DNS Resolver Aktif"},
    "🔄 Proxy Pool Status": {"id": "🔄 Status Proxy Pool"},
    "🛡️ Threat Watchdog": {"id": "🛡️ Pemantau Ancaman Jaringan"},
    "📜 PAC Auto-Config Server": {"id": "📜 Server PAC Auto-Config"},
    "Active System DNS:": {"id": "DNS Sistem Aktif:"},
    "DNS Latency:": {"id": "Latensi DNS:"},
    "Running Instances:": {"id": "Node Berjalan:"},
    "Active HTTP Port:": {"id": "Port HTTP Aktif:"},
    "Watchdog State:": {"id": "Status Pemantau:"},
    "Network Integrity:": {"id": "Integritas Jaringan:"},
    "PAC Server URL:": {"id": "URL Server PAC:"},
    "PAC System Proxy:": {"id": "Proxy Sistem PAC:"},
    "● ACTIVE": {"id": "● AKTIF"},
    "● STOPPED": {"id": "● BERHENTI"},
    "● PROTECTED": {"id": "● TERLINDUNGI"},
    "● READY": {"id": "● SIAP"},
    "● ENABLED": {"id": "● AKTIF"},
    "● DISABLED": {"id": "● NONAKTIF"},
    "Enable PAC": {"id": "Aktifkan PAC"},
    "Disable PAC": {"id": "Nonaktifkan PAC"},
    "Copy URL": {"id": "Salin URL"},
    "Copy PAC URL": {"id": "Salin URL PAC"},
    "✓ PAC URL disalin ke clipboard!": {"id": "✓ URL PAC disalin ke clipboard!"},
    "✓ PAC proxy sistem berhasil diaktifkan!": {"id": "✓ Proxy sistem PAC berhasil diaktifkan!"},
    "✓ PAC proxy sistem berhasil dinonaktifkan.": {"id": "✓ Proxy sistem PAC berhasil dinonaktifkan."},
    "✓ Cache DNS sistem berhasil dibersihkan!": {"id": "✓ Cache DNS sistem berhasil dibersihkan!"},
    "✓ Optimasi 1-Klik selesai! DNS tercepat diterapkan dan cache dibersihkan.": {
        "id": "✓ Optimasi 1-Klik selesai! DNS tercepat diterapkan dan cache dibersihkan.",
    },

    # -----------------------------------------------------------------------
    # Tab 2: DNS Suite View
    # -----------------------------------------------------------------------
    "⚡ Advanced Multi-Tier DNS Suite": {"id": "⚡ Multi-Tier DNS Suite & Pengelola Resolver"},
    "⚙️ Custom DNS Servers": {"id": "⚙️ Server DNS Kustom"},
    "Custom DNS Servers": {"id": "⚙️ Server DNS Kustom"},
    "Preset:": {"id": "Pilihan Preset:"},
    "Select Preset...": {"id": "Pilih Preset..."},
    "Protocol / IP:": {"id": "Protokol / IP:"},
    "IPv4 (Standard)": {"id": "IPv4 (Standar)"},
    "IPv6 (Next-Gen)": {"id": "IPv6 (Generasi Baru)"},
    "DoH (Encrypted HTTPS)": {"id": "DoH (Terkripsi HTTPS)"},
    "DoT (Encrypted TLS)": {"id": "DoT (Terkripsi TLS)"},
    "DoQ (DNS over QUIC)": {"id": "DoQ (DNS over QUIC)"},
    "Slot 1 (Primary DNS):": {"id": "Slot 1 (DNS Utama):"},
    "Slot 2 (Secondary DNS):": {"id": "Slot 2 (DNS Cadangan):"},
    "Slot 3 (Tertiary / Fallback):": {"id": "Slot 3 (DNS Tersier / Fallback):"},
    "Ping": {"id": "Uji Ping"},
    "⚡ GRC Smart Benchmark": {"id": "⚡ Benchmark DNS GRC"},
    "✓ Apply Custom DNS": {"id": "✓ Terapkan DNS Kustom"},
    "↩️ Restore DHCP": {"id": "↩️ Kembalikan DHCP"},
    "🛡️ DNS Canary (Interception Check)": {"id": "🛡️ DNS Canary (Cek Intersepsi)"},
    "DNS Canary (Interception Check)": {"id": "🛡️ DNS Canary (Cek Intersepsi)"},
    "● Not Checked": {"id": "● Belum Dicek"},
    "🔄 Check Now": {"id": "🔄 Cek Sekarang"},
    "ℹ️ What is this?": {"id": "ℹ️ Apa ini?"},
    "Click 'Check Now' to test Mozilla + Apple + Custom canary domains (system + custom resolver).": {
        "id": "Klik 'Cek Sekarang' untuk menguji domain canary Mozilla + Apple + Kustom (resolver sistem + kustom).",
    },
    "Running canary sweep... (please wait ~2-5s)": {
        "id": "Menjalankan pemeriksaan canary... (tunggu ~2-5 detik)",
    },
    "● Clean (No Intercept)": {"id": "● Bersih (Tanpa Intersepsi)"},
    "No interception detected. DoH / Apple Relay safe to use.": {
        "id": "Tidak ada intersepsi terdeteksi. DoH / Apple Relay aman digunakan.",
    },
    "● INTERCEPTED!": {"id": "● TERINTERSEPSI!"},
    "DoH may be blocked.": {"id": "DoH mungkin diblokir oleh ISP."},
    "● Offline / Unknown": {"id": "● Offline / Tidak Diketahui"},
    "Pre-check failed (offline / broken resolver). Cannot determine interception.": {
        "id": "Pra-cek gagal (offline / resolver rusak). Tidak dapat menentukan intersepsi.",
    },
    "● Partial": {"id": "● Sebagian"},
    "DNS Canary Domains — How It Works": {"id": "Domain Canary DNS — Cara Kerja"},
    "Add Custom Canary Domain or TLD": {"id": "Tambah Domain / TLD Canary Kustom"},
    "e.g. use-application-dns.net  or  .co.id  or  example.com": {
        "id": "mis. use-application-dns.net  atau  .co.id  atau  example.com",
    },
    "➕ Add": {"id": "➕ Tambah"},
    "🗑 Remove Selected": {"id": "🗑 Hapus Terpilih"},
    "Your Canaries ({n})": {"id": "Canary Anda ({n})"},
    "Close": {"id": "Tutup"},
    "Ping All": {"id": "Ping Semua"},
    "✓ DNS berhasil diterapkan ke sistem!": {"id": "✓ DNS berhasil diterapkan ke sistem!"},
    "✓ Pengaturan DNS berhasil dikembalikan ke default DHCP!": {
        "id": "✓ Pengaturan DNS berhasil dikembalikan ke default DHCP!",
    },

    # -----------------------------------------------------------------------
    # Tab 3: Proxy Rotator View
    # -----------------------------------------------------------------------
    "🌐 High-Performance Sing-box Proxy Rotator": {"id": "🌐 Sing-box Proxy Pool Rotator Berperforma Tinggi"},
    "🚀 Start Pool": {"id": "🚀 Jalankan Pool"},
    "🛑 Stop Pool": {"id": "🛑 Hentikan Pool"},
    "🔄 Rotate Now": {"id": "🔄 Rotasi Sekarang"},
    "⚡ Test All Latency": {"id": "⚡ Uji Semua Latensi"},
    "🧹 Clear Dead Nodes": {"id": "🧹 Bersihkan Node Mati"},
    "Auto-Rotate Interval:": {"id": "Interval Rotasi Otomatis:"},
    "Proxy Nodes Status": {"id": "Daftar Node Proxy & Latensi"},
    "Slot / Instance": {"id": "Slot / Instance"},
    "Protocol": {"id": "Protokol"},
    "Outbound Node": {"id": "Node Outbound"},
    "SOCKS5 Port": {"id": "Port SOCKS5"},
    "HTTP Port": {"id": "Port HTTP"},
    "Latency": {"id": "Latensi"},
    "Health Status": {"id": "Status Kesehatan"},
    "● POOL ACTIVE": {"id": "● POOL AKTIF"},
    "● POOL STOPPED": {"id": "● POOL BERHENTI"},

    # -----------------------------------------------------------------------
    # Tab 4: 9Router & AI Gateway View
    # -----------------------------------------------------------------------
    "🔌 9Router & AI Gateway Integration": {"id": "🔌 Integrasi 9Router & AI Gateway Multi-Provider"},
    "9Router API Endpoint:": {"id": "Endpoint API 9Router:"},
    "CLI Auth Secret / Token:": {"id": "Secret / Token Otentikasi CLI:"},
    "🔍 Auto-Detect Token": {"id": "🔍 Deteksi Otomatis Token"},
    "Target Interface / Outbound:": {"id": "Interface Target / Outbound:"},
    "⚡ Test Connection": {"id": "⚡ Uji Koneksi"},
    "✓ Apply & Bind to 9Router": {"id": "✓ Terapkan & Hubungkan ke 9Router"},
    "Status:": {"id": "Status:"},
    "Active Providers:": {"id": "Penyedia Model Aktif:"},
    "Routing Strategy:": {"id": "Strategi Routing:"},
    "✓ Berhasil terhubung ke 9Router Gateway!": {"id": "✓ Berhasil terhubung ke 9Router Gateway!"},
    "Gagal terhubung ke 9Router: {error}": {"id": "Gagal terhubung ke 9Router: {error}"},
    "✓ Successfully connected {assigned} connections to 9Router!": {"id": "✓ Berhasil menghubungkan {assigned} koneksi ke 9Router!"},
    "✓ Returned {cleared} 9Router proxies to Direct connection.": {"id": "✓ {cleared} proxy 9Router dikembalikan ke koneksi Direct."},
    "✓ Berhasil menghubungkan {assigned} koneksi ke 9Router!": {"id": "✓ Berhasil menghubungkan {assigned} koneksi ke 9Router!"},
    "✓ {cleared} proxy 9Router dikembalikan ke koneksi Direct.": {"id": "✓ {cleared} proxy 9Router dikembalikan ke koneksi Direct."},

    # -----------------------------------------------------------------------
    # Tab 5: Preferences & About View
    # -----------------------------------------------------------------------
    "⚙️ Settings, Cross-Platform Diagnostics & About": {"id": "⚙️ Pengaturan, Diagnostik Sistem & Info"},
    "🎨 Appearance & UI Font Scaling": {"id": "🎨 Tampilan, Skala Font & Bahasa"},
    "UI Scale / Font Size:": {"id": "Skala Font UI:"},
    "Theme Palette:": {"id": "Palet Tema:"},
    "|  Theme Palette:": {"id": "|  Palet Tema:"},
    "Language:": {"id": "Bahasa (Language):"},
    "|  Language:": {"id": "|  Bahasa (Language):"},
    "Minimize to System Tray on Close (Tetap aktif di background saat ditutup)": {
        "id": "Kecilkan ke System Tray saat tombol close diklik (Tetap aktif di latar belakang)",
    },
    "🔍 Cross-Platform Environment & Dependency Diagnostics": {
        "id": "🔍 Diagnostik Lingkungan & Ketergantungan Sistem",
    },
    "🔄 Refresh Diagnostics": {"id": "🔄 Segarkan Diagnostik"},
    "💾 DNS Database Backup & Cloud Sync": {"id": "💾 Backup Database DNS & Sinkronisasi Cloud"},
    "📥 Import JSON DNS": {"id": "📥 Impor JSON DNS"},
    "📥 Import DnsJumper INI": {"id": "📥 Impor DnsJumper INI"},
    "📤 Export DNS to JSON": {"id": "📤 Ekspor DNS ke JSON"},
    "☁️ Sync Cloud Preset DB": {"id": "☁️ Sinkronisasi Database Cloud"},
    "♻️ Reset Default Providers": {"id": "♻️ Reset Preset Default"},
    "ℹ️ About Netools Suite": {"id": "ℹ️ Tentang Netools Suite"},
    "⚡ Netools Suite v2.0.0 (Clean Architecture Edition)": {
        "id": "⚡ Netools Suite v2.0.0 (Clean Architecture Edition)",
    },
    "Cross-platform High-performance Desktop Suite for GRC-style 3-Tier DNS Benchmarking, Smart Split-DNS Switching, Turbo Sing-box Proxy Pool Rotation, PAC Auto-Configuration & AI Multi-Provider Router Routing on Linux, Windows & macOS.": {
        "id": "Aplikasi Desktop Berperforma Tinggi Lintas Platform untuk Benchmark DNS 3-Tier Gaya GRC, Smart Split-DNS Switching, Rotator Proxy Sing-box Turbo, PAC Auto-Configuration & Routing AI Multi-Provider pada Linux, Windows & macOS.",
    },
    "🚀 Check for Updates": {"id": "🚀 Periksa Pembaruan"},
    "📖 GitHub Repository": {"id": "📖 Repositori GitHub"},
    "✓ Bahasa berhasil diubah ke Bahasa Indonesia!": {"id": "✓ Bahasa berhasil diubah ke Bahasa Indonesia!"},
    "✓ Language changed to English!": {"id": "✓ Language changed to English!"},

    # -----------------------------------------------------------------------
    # GRC Benchmark Modal
    # -----------------------------------------------------------------------
    "⚡ GRC-Style 3-Tier DNS Benchmark": {"id": "⚡ Benchmark DNS 3-Tier Gaya GRC"},
    "Select and test response times across all DNS providers in real-time.": {
        "id": "Pilih dan uji waktu respons seluruh resolver DNS secara real-time.",
    },
    "🚀 Run Full Benchmark": {"id": "🚀 Jalankan Benchmark Lengkap"},
    "⚡ GRC Smart Mix (Fastest 3)": {"id": "⚡ GRC Smart Mix (3 Tercepat)"},
    "✓ Apply Selected DNS": {"id": "✓ Terapkan DNS Terpilih"},
    "Status: Idle": {"id": "Status: Siap"},
    "Status: Running Benchmark...": {"id": "Status: Menjalankan Benchmark..."},
    "Status: Completed": {"id": "Status: Benchmark Selesai"},
    "Provider Name": {"id": "Nama Resolver"},
    "Primary IP": {"id": "IP Utama"},
    "Secondary IP": {"id": "IP Cadangan"},
    "Avg Latency": {"id": "Rata-rata Latensi"},
    "Reliability": {"id": "Keandalan"},

    # -----------------------------------------------------------------------
    # Visual DPI & Censorship Flow Inspector Modal
    # -----------------------------------------------------------------------
    "🔍 Visual Multi-Layer Censorship & DPI Flow Inspector": {
        "id": "🔍 Visual Multi-Layer Censorship & DPI Flow Inspector",
    },
    "Enter Domain to Analyze:": {"id": "Masukkan Domain untuk Dianalisis:"},
    "Quick Presets:": {"id": "Preset Cepat:"},
    "🚀 Analyze Censorship Flow": {"id": "🚀 Analisis Alur Pemblokiran"},
    "Node A: DNS Resolution": {"id": "Node A: Resolusi DNS"},
    "Node B: TCP Port 443": {"id": "Node B: Koneksi TCP 443"},
    "Node C: TLS SNI Handshake": {"id": "Node C: Handshake TLS SNI"},
    "Node D: SSL / MITM Cert": {"id": "Node D: Verifikasi Sertifikat SSL"},
    "● PENDING": {"id": "● MENUNGGU"},
    "● ANALYZING": {"id": "● MENGANALISIS"},
    "🟢 PASS": {"id": "🟢 LOLOS"},
    "🔴 BLOCKED": {"id": "🔴 TERBLOKIR"},
    "🟡 WARN": {"id": "🟡 PERINGATAN"},
    "⚪ SKIPPED": {"id": "⚪ DILEWATI"},
    "Findings & Actionable Recommendations:": {"id": "Temuan & Rekomendasi Tindakan:"},
    "Click 'Analyze Censorship Flow' to inspect domain reachability through 4 network layers.": {
        "id": "Klik 'Analisis Alur Pemblokiran' untuk memeriksa keterjangkauan domain melalui 4 lapisan jaringan.",
    },
    "🌐 Route Domain through Proxy Rotator": {"id": "🌐 Rute Domain Lewat Proxy Rotator"},
    "⚡ Switch to Encrypted DoH DNS": {"id": "⚡ Beralih ke DNS Terenkripsi DoH"},
}

_CANARY_INFO: dict[str, list[str]] = {
    "en": [
        "What are canary domains?",
        "Canary domains are special hostnames that must NEVER resolve to an IP address. "
        "They are published by Mozilla and Apple as tripwires: if your network operator "
        "(ISP) tampers with DNS, these domains suddenly 'resolve' to a forged answer.",

        "How the check works:",
        "1. Netools queries each canary hostname through your system resolver "
        "(and any custom upstream you configured).",
        "2. A correct resolver answers NXDOMAIN ('this domain does not exist'). "
        "That means your DNS path is clean.",
        "3. If an answer comes back anyway (an IP, CNAME, or SOA record), someone on "
        "the path forged it -> DNS interception detected. Your plain-DNS queries are "
        "being watched or redirected.",
        "4. Before judging, a pre-check resolves firefox.com / mozilla.org to make "
        "sure you are actually online - otherwise results would be false positives.",

        "Why this matters:",
        "If interception is detected, websites may be blocked or redirected by your "
        "provider even before you connect. Encrypted DNS (DoH via Netools' forwarder, "
        "or DoT) bypasses this tampering because the ISP can no longer read or forge "
        "your DNS responses.",
        "You can add your own canary domains or even whole TLDs (like .co.id) below. "
        "A good custom canary is a domain that is guaranteed not to exist.",
    ],
    "id": [
        "Apa itu domain canary?",
        "Domain canary adalah hostname khusus yang TIDAK PERNAH boleh resolve ke alamat IP. "
        "Domain ini diterbitkan oleh Mozilla dan Apple sebagai tripwire/alarm: jika operator jaringan "
        "(ISP) mengintervensi DNS, domain ini tiba-tiba 'ter-resolve' ke jawaban palsu.",

        "Cara kerja pemeriksaan:",
        "1. Netools menanyakan setiap hostname canary melalui resolver sistem "
        "(dan upstream kustom yang Anda konfigurasi).",
        "2. Resolver yang benar menjawab NXDOMAIN ('domain ini tidak ada'). "
        "Artinya jalur DNS Anda bersih tanpa gangguan.",
        "3. Jika jawaban tetap muncul (rekaman IP, CNAME, atau SOA), ada pihak yang "
        "memalsukannya -> intersepsi DNS terdeteksi. Kueri DNS biasa Anda sedang "
        "dipantau atau dialihkan oleh ISP/Middlebox.",
        "4. Sebelum menilai, pra-cek me-resolve firefox.com / mozilla.org untuk "
        "memastikan Anda benar-benar online - jika tidak, hasil bisa salah.",

        "Mengapa ini penting:",
        "Jika intersepsi terdeteksi, situs web dapat diblokir atau dialihkan oleh penyedia "
        "Anda bahkan sebelum Anda terhubung. DNS terenkripsi (DoH via forwarder Netools, "
        "atau DoT) melewati gangguan ini karena ISP tidak lagi dapat membaca atau memalsukan "
        "respons DNS Anda.",
        "Anda dapat menambahkan domain canary sendiri, bahkan seluruh TLD (seperti .co.id) "
        "di bawah. Canary kustom yang baik adalah domain yang dijamin tidak ada.",
    ],
}


# ---------------------------------------------------------------------------
# Core i18n Functions & Extensibility
# ---------------------------------------------------------------------------

def register_locale(code: str, label: str, strings: dict[str, str], canary_info: Optional[list[str]] = None) -> None:
    """
    Register a new locale dynamically (Scalability interface).
    Allows adding new languages (e.g. Japanese, Chinese, German) with 1 line.
    """
    code = code.lower().strip()
    _LOCALE_REGISTRY[code] = label
    for key, translation in strings.items():
        if key not in _TRANSLATIONS:
            _TRANSLATIONS[key] = {}
        _TRANSLATIONS[key][code] = translation
    if canary_info:
        _CANARY_INFO[code] = canary_info
    log.info(f"Registered new i18n locale: {code} ({label}) with {len(strings)} strings")


def get_available_locales() -> dict[str, str]:
    """Return dictionary of available locales {code: display_label}."""
    return dict(_LOCALE_REGISTRY)


def get_locale_labels() -> list[str]:
    """Return list of formatted locale display labels."""
    return list(_LOCALE_REGISTRY.values())


def locale_from_label(label: str) -> str:
    """Map display label or raw code to standardized locale code."""
    clean = label.strip()
    for code, lbl in _LOCALE_REGISTRY.items():
        if clean == lbl or clean.lower() == code:
            return code
    if "indo" in clean.lower() or "id" in clean.lower():
        return "id"
    return "en"


def label_from_locale(code: str) -> str:
    """Map standardized locale code to display label."""
    return _LOCALE_REGISTRY.get(code.lower(), _LOCALE_REGISTRY.get("en", "🇬🇧 English"))


def get_locale() -> str:
    """Get active locale from memory or persist file (~/.config/netools/config.json)."""
    global _current_locale
    if _current_locale:
        return _current_locale

    try:
        if USER_CONFIG_FILE.exists():
            data = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
            lang = str(data.get("language", "en")).lower().strip()
            if lang in _LOCALE_REGISTRY:
                _current_locale = lang
                return lang
    except Exception as e:
        log.debug(f"Failed reading locale from config: {e}")

    _current_locale = "en"
    return _current_locale


def set_locale(lang: str) -> None:
    """Set and persist active locale to ~/.config/netools/config.json."""
    global _current_locale
    code = locale_from_label(lang)
    _current_locale = code

    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cfg: dict[str, Any] = {}
        if USER_CONFIG_FILE.exists():
            try:
                cfg = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                cfg = {}
        cfg["language"] = code
        USER_CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        log.info(f"Persisted language preference: {code}")
    except Exception as e:
        log.warning(f"Failed persisting locale to {USER_CONFIG_FILE}: {e}")


def tr(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """
    Translate `key` (English canonical text) into the active locale.
    Supports dynamic string formatting using kwargs (e.g. tr("Hello {name}", name="User")).
    """
    loc = (lang or get_locale()).lower()
    text = key

    if loc != "en":
        entry = _TRANSLATIONS.get(key)
        if entry and loc in entry:
            text = entry[loc]

    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def canary_info_paragraphs(lang: Optional[str] = None) -> list[str]:
    """Localized explanatory paragraphs for the canary info dialog."""
    loc = (lang or get_locale()).lower()
    return list(_CANARY_INFO.get(loc, _CANARY_INFO.get("en", [])))
