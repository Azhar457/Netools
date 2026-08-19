#!/usr/bin/env python3
"""
DNS Jumper / DNS Searcher Database Module
Curated Global & Regional DNS/DoH Providers with Cloud Sync & Regional TLD Datasets.
"""

import json
import urllib.request
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

APP_DIR = Path.home() / ".local" / "share" / "dns-jumper"
APP_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = APP_DIR / "providers.json"

# Core Curated Database of 50+ Major DNS & DoH Providers
BUILTIN_PROVIDERS: Dict[str, Dict[str, Any]] = {
    # ==================== ASIA-PACIFIC (APAC / ID / SG / JP / CN / TW) ====================
    "alidns": {
        "name": "AliDNS (Alibaba Cloud)",
        "country": "🇨🇳 CN/SG",
        "region": "asia",
        "doh_url": "https://dns.alidns.com/dns-query",
        "ipv4": ["223.5.5.5", "223.6.6.6"],
        "category": "general",
        "description": "Alibaba Cloud Anycast DNS - fast peering in Indonesia, Singapore, and Asia.",
    },
    "iij": {
        "name": "IIJ Public DNS (Japan)",
        "country": "🇯🇵 JP",
        "region": "asia",
        "doh_url": "https://public.dns.iij.jp/dns-query",
        "ipv4": ["203.180.164.45", "203.180.166.45"],
        "category": "general",
        "description": "Internet Initiative Japan public high-speed Anycast DNS.",
    },
    "dnspod": {
        "name": "DNSPod Public (Tencent)",
        "country": "🇨🇳 CN",
        "region": "asia",
        "doh_url": "https://dns.pub/dns-query",
        "ipv4": ["119.29.29.29", "182.254.116.116"],
        "category": "general",
        "description": "Tencent DNSPod Anycast network with fast regional nodes.",
    },
    "openbld": {
        "name": "OpenBLD ADA",
        "country": "🇰🇿 KZ",
        "region": "asia",
        "doh_url": "https://ada.openbld.net/dns-query",
        "ipv4": ["146.112.41.2", "146.112.41.102"],
        "category": "security",
        "description": "OpenBLD - privacy-focused anti-tracking & anti-malware DNS in Central Asia.",
    },
    "twnic": {
        "name": "Quad101 (TWNIC Taiwan)",
        "country": "🇹🇼 TW",
        "region": "asia",
        "doh_url": "https://101.101.101.101/dns-query",
        "ipv4": ["101.101.101.101", "101.102.103.104"],
        "category": "privacy",
        "description": "Taiwan Network Information Center privacy-focused public resolver.",
    },

    # ==================== GLOBAL ANYCAST (JKT / SG Local Nodes) ====================
    "cloudflare": {
        "name": "Cloudflare Standard",
        "country": "🌐 US/Global",
        "region": "global",
        "doh_url": "https://cloudflare-dns.com/dns-query",
        "ipv4": ["1.1.1.1", "1.0.0.1"],
        "ipv6": ["2606:4700:4700::1111", "2606:4700:4700::1001"],
        "category": "general",
        "description": "Cloudflare 1.1.1.1 - fastest Anycast network with Jakarta & Singapore PoPs.",
    },
    "cloudflare-security": {
        "name": "Cloudflare Security (Malware)",
        "country": "🌐 US/Global",
        "region": "global",
        "doh_url": "https://security.cloudflare-dns.com/dns-query",
        "ipv4": ["1.1.1.2", "1.0.0.2"],
        "ipv6": ["2606:4700:4700::1112", "2606:4700:4700::1002"],
        "category": "security",
        "description": "Cloudflare 1.1.1.2 - automated malware & phishing domain blocking.",
    },
    "cloudflare-family": {
        "name": "Cloudflare Family",
        "country": "🌐 US/Global",
        "region": "global",
        "doh_url": "https://family.cloudflare-dns.com/dns-query",
        "ipv4": ["1.1.1.3", "1.0.0.3"],
        "ipv6": ["2606:4700:4700::1113", "2606:4700:4700::1003"],
        "category": "family",
        "description": "Cloudflare 1.1.1.3 - blocks malware and adult content.",
    },
    "google": {
        "name": "Google Public DNS",
        "country": "🌐 US/Global",
        "region": "global",
        "doh_url": "https://dns.google/dns-query",
        "ipv4": ["8.8.8.8", "8.8.4.4"],
        "ipv6": ["2001:4860:4860::8888", "2001:4860:4860::8844"],
        "category": "general",
        "description": "Google 8.8.8.8 - robust global DNS with local Jakarta Anycast node.",
    },
    "quad9": {
        "name": "Quad9 (Threat Blocking)",
        "country": "🇨🇭 CH/Global",
        "region": "global",
        "doh_url": "https://dns.quad9.net/dns-query",
        "ipv4": ["9.9.9.9", "149.112.112.112", "149.112.112.9"],
        "ipv6": ["2620:fe::fe", "2620:fe::9"],
        "category": "security",
        "description": "Quad9 - Swiss non-profit with automated malware intelligence blocking.",
    },
    "quad9-unfiltered": {
        "name": "Quad9 (Unfiltered)",
        "country": "🇨🇭 CH/Global",
        "region": "global",
        "doh_url": "https://dns10.quad9.net/dns-query",
        "ipv4": ["9.9.9.10", "149.112.112.10"],
        "ipv6": ["2620:fe::10", "2620:fe::fe:10"],
        "category": "privacy",
        "description": "Quad9 Unfiltered - no censorship or filtering, strict privacy.",
    },
    "adguard": {
        "name": "AdGuard Default (Adblock)",
        "country": "🇨🇾 CY/Global",
        "region": "global",
        "doh_url": "https://dns.adguard-dns.com/dns-query",
        "ipv4": ["94.140.14.14", "94.140.15.15"],
        "ipv6": ["2a10:50c0::ad1:ff", "2a10:50c0::ad2:ff"],
        "category": "adblock",
        "description": "AdGuard DNS - blocks advertisements, trackers, and malicious domains.",
    },
    "adguard-unfiltered": {
        "name": "AdGuard Non-filtering",
        "country": "🇨🇾 CY/Global",
        "region": "global",
        "doh_url": "https://unfiltered.adguard-dns.com/dns-query",
        "ipv4": ["94.140.14.140", "94.140.14.141"],
        "ipv6": ["2a10:50c0::1:ff", "2a10:50c0::2:ff"],
        "category": "privacy",
        "description": "AdGuard Unfiltered - privacy-first without ad-blocking filters.",
    },
    "adguard-family": {
        "name": "AdGuard Family",
        "country": "🇨🇾 CY/Global",
        "region": "global",
        "doh_url": "https://family.adguard-dns.com/dns-query",
        "ipv4": ["94.140.14.15", "94.140.15.16"],
        "ipv6": ["2a10:50c0::bad1:ff", "2a10:50c0::bad2:ff"],
        "category": "family",
        "description": "AdGuard Family - blocks ads + adult sites + enforces safe search.",
    },
    "controld": {
        "name": "ControlD Unfiltered",
        "country": "🇨🇦 CA/Global",
        "region": "global",
        "doh_url": "https://freedns.controld.com/p0",
        "ipv4": ["76.76.2.0", "76.223.122.150"],
        "category": "general",
        "description": "ControlD P0 - high-speed unfiltered Anycast resolver.",
    },
    "controld-malware": {
        "name": "ControlD Malware Block",
        "country": "🇨🇦 CA/Global",
        "region": "global",
        "doh_url": "https://freedns.controld.com/p1",
        "ipv4": ["76.76.2.1", "76.223.122.151"],
        "category": "security",
        "description": "ControlD P1 - blocks malware and security threats.",
    },
    "controld-adblock": {
        "name": "ControlD Ads & Malware",
        "country": "🇨🇦 CA/Global",
        "region": "global",
        "doh_url": "https://freedns.controld.com/p2",
        "ipv4": ["76.76.2.2", "76.223.122.152"],
        "category": "adblock",
        "description": "ControlD P2 - blocks ads, tracking, and malware.",
    },
    "nextdns": {
        "name": "NextDNS Public",
        "country": "🇺🇸 US/Global",
        "region": "global",
        "doh_url": "https://dns.nextdns.io",
        "ipv4": ["45.90.28.0", "45.90.30.0"],
        "category": "privacy",
        "description": "NextDNS Anycast - modern customizable encrypted DNS.",
    },

    # ==================== EUROPE (EU / CH / DE / NL / SE / AT / GR) ====================
    "dns_sb": {
        "name": "DNS.SB (Privacy DNS)",
        "country": "🇩🇪 DE",
        "region": "europe",
        "doh_url": "https://doh.dns.sb/dns-query",
        "ipv4": ["185.222.222.222", "45.11.45.11"],
        "category": "privacy",
        "description": "DNS.SB - privacy-first with DNSSEC validation and zero logging.",
    },
    "mullvad-base": {
        "name": "Mullvad Base",
        "country": "🇸🇪 SE",
        "region": "europe",
        "doh_url": "https://base.dns.mullvad.net/dns-query",
        "ipv4": ["194.242.2.4"],
        "category": "privacy",
        "description": "Mullvad VPN Public DNS - strict no-log privacy policy in Sweden.",
    },
    "mullvad-adblock": {
        "name": "Mullvad Adblock",
        "country": "🇸🇪 SE",
        "region": "europe",
        "doh_url": "https://adblock.dns.mullvad.net/dns-query",
        "ipv4": ["194.242.2.3"],
        "category": "adblock",
        "description": "Mullvad Adblock - blocks ads, trackers, and malware.",
    },
    "dns4eu": {
        "name": "DNS4EU",
        "country": "🇨🇿 CZ",
        "region": "europe",
        "doh_url": "https://unfiltered.joindns4.eu/dns-query",
        "ipv4": ["86.54.11.100", "86.54.11.200"],
        "category": "general",
        "description": "European Union official DNS infrastructure project.",
    },
    "applied-privacy": {
        "name": "Applied Privacy",
        "country": "🇦🇹 AT",
        "region": "europe",
        "doh_url": "https://doh.applied-privacy.net/query",
        "ipv4": ["146.255.56.98"],
        "category": "privacy",
        "description": "Austrian non-profit Foundation for Applied Privacy DNS.",
    },
    "digitale-gesellschaft": {
        "name": "Digitale Gesellschaft",
        "country": "🇨🇭 CH",
        "region": "europe",
        "doh_url": "https://dns.digitale-gesellschaft.ch/dns-query",
        "ipv4": ["185.95.218.42", "185.95.218.43"],
        "category": "privacy",
        "description": "Swiss non-profit Digital Society DNS with GDPR & Swiss law compliance.",
    },
    "switch": {
        "name": "Switch DNS",
        "country": "🇨🇭 CH",
        "region": "europe",
        "doh_url": "https://dns.switch.ch/dns-query",
        "ipv4": ["130.59.31.248", "130.59.31.251"],
        "category": "general",
        "description": "Swiss Education & Research Network public DNS.",
    },
    "uncensoreddns": {
        "name": "UncensoredDNS",
        "country": "🇩🇰 DK",
        "region": "europe",
        "doh_url": "https://anycast.uncensoreddns.org/dns-query",
        "ipv4": ["91.239.100.100", "89.233.43.71"],
        "category": "privacy",
        "description": "Independently operated, unfiltered, non-censoring DNS in Denmark.",
    },
    "libredns": {
        "name": "LibreDNS Greece",
        "country": "🇬🇷 GR",
        "region": "europe",
        "doh_url": "https://doh.libredns.gr/dns-query",
        "ipv4": ["116.202.176.26", "147.135.76.183"],
        "category": "privacy",
        "description": "LibreOps community privacy DNS in Greece.",
    },
    "flashstart": {
        "name": "FlashStart Cloud",
        "country": "🇮🇹 IT",
        "region": "europe",
        "doh_url": "https://doh.flashstart.com/f17c9ee5",
        "ipv4": ["185.236.104.104"],
        "category": "security",
        "description": "FlashStart Italian Cloud Threat Protection DNS.",
    },

    # ==================== NORTH AMERICA (US & CANADA) ====================
    "opendns": {
        "name": "Cisco OpenDNS Home",
        "country": "🇺🇸 US",
        "region": "north_america",
        "doh_url": "https://doh.opendns.com/dns-query",
        "ipv4": ["208.67.222.222", "208.67.220.220"],
        "category": "general",
        "description": "Cisco OpenDNS - reliable global Anycast enterprise network.",
    },
    "opendns-family": {
        "name": "Cisco OpenDNS FamilyShield",
        "country": "🇺🇸 US",
        "region": "north_america",
        "doh_url": "https://doh.familyshield.opendns.com/dns-query",
        "ipv4": ["208.67.222.123", "208.67.220.123"],
        "category": "family",
        "description": "OpenDNS FamilyShield - automatically blocks adult sites.",
    },
    "cleanbrowsing": {
        "name": "CleanBrowsing Security",
        "country": "🇺🇸 US",
        "region": "north_america",
        "doh_url": "https://doh.cleanbrowsing.org/doh/security-filter/",
        "ipv4": ["185.228.168.9", "185.228.169.9"],
        "category": "security",
        "description": "CleanBrowsing Security - blocks phishing, malware, malicious sites.",
    },
    "cleanbrowsing-family": {
        "name": "CleanBrowsing Family",
        "country": "🇺🇸 US",
        "region": "north_america",
        "doh_url": "https://doh.cleanbrowsing.org/doh/family-filter/",
        "ipv4": ["185.228.168.168", "185.228.169.168"],
        "category": "family",
        "description": "CleanBrowsing Family - strict adult content filter + safe search.",
    },
    "canadian-shield": {
        "name": "CIRA Canadian Shield",
        "country": "🇨🇦 CA",
        "region": "north_america",
        "doh_url": "https://private.canadianshield.cira.ca/dns-query",
        "ipv4": ["149.112.121.10", "149.112.122.10"],
        "category": "privacy",
        "description": "CIRA Canadian Shield Private DNS for privacy & security.",
    },
    "rethinkdns": {
        "name": "RethinkDNS",
        "country": "🇺🇸 US",
        "region": "north_america",
        "doh_url": "https://sky.rethinkdns.com/dns-query",
        "ipv4": ["104.21.83.62", "172.67.214.246"],
        "category": "security",
        "description": "RethinkDNS - open source privacy and anti-censorship DNS.",
    },
    "level3": {
        "name": "Level3 / Lumen Tier-1",
        "country": "🇺🇸 US",
        "region": "north_america",
        "doh_url": "",
        "ipv4": ["4.2.2.1", "4.2.2.2", "4.2.2.3"],
        "category": "general",
        "description": "Tier-1 backbone global Anycast DNS resolver.",
    },
    "comodo": {
        "name": "Comodo Secure DNS",
        "country": "🇺🇸 US",
        "region": "north_america",
        "doh_url": "",
        "ipv4": ["8.26.56.26", "8.20.247.20"],
        "category": "security",
        "description": "Comodo Secure DNS with threat filtering.",
    },
    "neustar": {
        "name": "Neustar UltraDNS",
        "country": "🇺🇸 US",
        "region": "north_america",
        "doh_url": "",
        "ipv4": ["156.154.70.1", "156.154.71.1"],
        "category": "general",
        "description": "Neustar enterprise public Anycast DNS.",
    },
    "verisign": {
        "name": "Verisign Public DNS",
        "country": "🇺🇸 US",
        "region": "north_america",
        "doh_url": "",
        "ipv4": ["64.6.64.6", "64.6.65.6"],
        "category": "general",
        "description": "Verisign reliable stability-oriented DNS.",
    },
}


def load_providers() -> Dict[str, Dict[str, Any]]:
    """Load providers from local cache JSON or fallback to built-in presets."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and len(data) > 0:
                    merged = {k: dict(v) for k, v in BUILTIN_PROVIDERS.items()}
                    for k, v in data.items():
                        if k in merged:
                            merged[k].update(v)
                            if "ipv6" not in v and "ipv6" in BUILTIN_PROVIDERS[k]:
                                merged[k]["ipv6"] = BUILTIN_PROVIDERS[k]["ipv6"]
                        else:
                            merged[k] = v
                    return merged
        except Exception:
            pass
    return {k: dict(v) for k, v in BUILTIN_PROVIDERS.items()}


def save_providers(providers: Dict[str, Dict[str, Any]]):
    """Save providers dictionary to local cache JSON."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(providers, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[!] Failed to save providers cache: {e}")


def filter_providers(
    providers: Dict[str, Dict[str, Any]],
    region: Optional[str] = None,
    category: Optional[str] = None,
    only_doh: bool = False
) -> Dict[str, Dict[str, Any]]:
    """Filter provider dictionary based on region, category, and DoH availability."""
    filtered = {}
    for k, p in providers.items():
        if only_doh and not p.get("doh_url"):
            continue
        if region and region != "all":
            if region == "asia" and p.get("region") not in ("asia", "global"):
                continue
            elif region == "europe" and p.get("region") not in ("europe", "global"):
                continue
            elif region == "north_america" and p.get("region") not in ("north_america", "global"):
                continue
            elif region == "global" and p.get("region") != "global":
                continue
        if category and category != "all":
            if p.get("category") != category:
                continue
        filtered[k] = p
    return filtered


def sync_cloud_providers() -> Tuple[bool, str, int]:
    """Fetch verified DoH resolver database from official DNSCrypt repository."""
    url = "https://raw.githubusercontent.com/DNSCrypt/dnscrypt-resolvers/master/v3/public-resolvers.md"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DNSJumper-Linux/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        current = load_providers()
        added = 0
        blocks = re.findall(r"## ([^\n]+)\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
        for name, body in blocks:
            name_clean = name.strip()
            key_clean = re.sub(r"[^a-zA-Z0-9_-]", "_", name_clean.lower())
            
            doh_m = re.search(r"https://[a-zA-Z0-9.-]+/[a-zA-Z0-9_/?=-]+", body)
            doh_url = doh_m.group(0) if doh_m else ""
            
            country_m = re.search(r"country\s*=\s*([^\n]+)", body)
            country = country_m.group(1).strip().upper() if country_m else "Global"
            
            ips = re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", body)
            valid_ips = [ip for ip in ips if not ip.startswith(("127.", "10.", "192.168.", "0."))]

            if valid_ips and key_clean not in current:
                current[key_clean] = {
                    "name": name_clean.replace("-", " ").title(),
                    "country": f"🌐 {country}",
                    "region": "global",
                    "doh_url": doh_url,
                    "ipv4": valid_ips[:2],
                    "category": "privacy",
                    "description": f"Community verified resolver from DNSCrypt database ({country}).",
                }
                added += 1

        save_providers(current)
        return True, f"Successfully synchronized database! Added {added} new verified resolvers (Total: {len(current)}).", len(current)
    except Exception as e:
        return False, f"Sync error: {e}", len(BUILTIN_PROVIDERS)


def import_from_dnsjumper_ini(filepath: str) -> Tuple[int, str]:
    """Parse and import DNS resolvers from a standard Windows DnsJumper.ini file."""
    try:
        try:
            with open(filepath, "r", encoding="utf-16le", errors="ignore") as f:
                text = f.read()
        except Exception:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

        imported = 0
        current_sec = ""
        current_providers = load_providers()

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_sec = line[1:-1]
                continue
            if "=" in line and ("ipv4" in current_sec.lower() or "ipv6" in current_sec.lower()):
                k, v = line.split("=", 1)
                k = k.strip()
                parts = [p.strip() for p in v.split(",") if p.strip() and p.strip() not in ("True", "False")]
                if not parts:
                    continue

                slug = re.sub(r'[^a-zA-Z0-9_-]', '_', k).lower().strip('_')
                country_code = k[:2].upper() if (len(k) >= 3 and k[2:4] in (" -", "- ")) else "🌐"

                if "ipv6" in current_sec.lower():
                    if slug in current_providers:
                        current_providers[slug]["ipv6"] = parts
                    else:
                        current_providers[slug] = {
                            "name": k,
                            "country": f"🌐 {country_code}",
                            "region": "global",
                            "ipv4": [],
                            "ipv6": parts,
                            "doh_url": "",
                            "category": "general",
                            "description": f"Imported from DnsJumper.ini ({k})"
                        }
                    imported += 1
                else:
                    if slug in current_providers:
                        current_providers[slug]["ipv4"] = parts
                    else:
                        cat = "family" if "family" in current_sec.lower() else ("security" if "secure" in current_sec.lower() else "general")
                        current_providers[slug] = {
                            "name": k,
                            "country": f"🌐 {country_code}",
                            "region": "global",
                            "ipv4": parts,
                            "ipv6": [],
                            "doh_url": "",
                            "category": cat,
                            "description": f"Imported from DnsJumper.ini ({k})"
                        }
                    imported += 1

        save_providers(current_providers)
        return imported, f"Berhasil mengimpor {imported} resolver dari DnsJumper.ini (Total Database: {len(current_providers)})!"
    except Exception as e:
        return 0, f"Gagal mengimpor DnsJumper.ini: {e}"


# Target Domain Presets for 3-Tier GRC Benchmark (Including Wide Note Dataset)
TLD_PRESETS = {
    "indonesia": {
        "name": "🇮🇩 Indonesia (.id, .my.id, .go.id, .co.id - IIX/OpenIXP)",
        "domains": [
            # Perbankan
            "bca.co.id",
            "klikbca.com",
            "bankmandiri.co.id",
            "bni.co.id",
            "bri.co.id",
            "cimbniaga.co.id",
            # E-Commerce & Tech
            "tokopedia.com",
            "shopee.co.id",
            "gojek.com",
            "grab.com",
            "traveloka.com",
            # Media & Informasi
            "detik.com",
            "kompas.com",
            "tribunnews.com",
            "tempo.co",
            "vidio.com",
            # Pemerintahan & Kampus
            "indonesia.go.id",
            "kemkes.go.id",
            "pajak.go.id",
            "kominfo.go.id",
            "ui.ac.id",
            "itb.ac.id",
            "ugm.ac.id",
            "pandi.id",
        ]
    },
    "global_com": {
        "name": "🌐 Global Commercial (.com, .net)",
        "domains": [
            "google.com",
            "youtube.com",
            "facebook.com",
            "chatgpt.com",
            "x.com",
            "reddit.com",
            "amazon.com",
            "netflix.com",
        ]
    },
    "non_profit_org": {
        "name": "🏛️ Non-Profit & Tech (.org, .io, .dev)",
        "domains": [
            "wikipedia.org",
            "github.com",
            "archive.org",
            "mozilla.org",
            "kernel.org",
            "python.org",
            "eff.org",
            "debian.org",
        ]
    },
}

def reset_to_default_providers() -> Dict[str, Dict[str, Any]]:
    """Reset providers cache to built-in presets."""
    if CACHE_FILE.exists():
        try:
            CACHE_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    return dict(BUILTIN_PROVIDERS)
