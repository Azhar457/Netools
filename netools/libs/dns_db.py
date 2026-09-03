#!/usr/bin/env python3
"""
DNS Jumper / DNS Searcher Database Module
Curated Global & Regional DNS/DoH Providers with Cloud Sync & Regional TLD Datasets.
"""

import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from netools.config import USER_CONFIG_DIR
from netools.libs.logger import get_logger

log = get_logger(__name__)

APP_DIR = Path.home() / ".local" / "share" / "dns-jumper"
APP_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = APP_DIR / "providers.json"

# Core Curated Database of 50+ Major DNS & DoH Providers
def _load_builtin_providers() -> Dict[str, Dict[str, Any]]:
    """Built-in resolver catalog lives in assets/dns_providers.json so it can
    be updated without touching code. Falls back to an empty catalog if the
    data file is missing/corrupt (CACHE merge still applies user overrides)."""
    data_file = Path(__file__).resolve().parent.parent / "assets" / "dns_providers.json"
    try:
        with open(data_file, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception as e:
        get_logger(__name__).warning(f"builtin providers load failed: {e}")
    return {}


BUILTIN_PROVIDERS: Dict[str, Dict[str, Any]] = _load_builtin_providers()


def load_providers() -> Dict[str, Dict[str, Any]]:
    """Load providers from local cache JSON or fallback to built-in presets."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
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
            with open(filepath, encoding="utf-16le", errors="ignore") as f:
                text = f.read()
        except Exception:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
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
        "country": "ID",
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
    "ai_gateways": {
        "name": "🤖 AI Gateways & LLM Providers (.ai, .com, .io)",
        "domains": [
            # Primary Gateways & Aggregators
            "openrouter.ai",
            "opencode.ai",
            "kilo.ai",
            "tokenrouter.io",
            "sdk.vercel.ai",
            "api.airforce",
            "bazaarlink.com",
            # Major LLM Labs & Endpoints
            "api.openai.com",
            "chatgpt.com",
            "api.anthropic.com",
            "claude.ai",
            "generativelanguage.googleapis.com",
            "api.deepseek.com",
            "api.x.ai",
            "grok.com",
            "api.mistral.ai",
            "api.cohere.com",
            "api.perplexity.ai",
            "ollama.com",
            # High-Speed Inference Engines
            "api.groq.com",
            "api.cerebras.ai",
            "api.together.xyz",
            "api.fireworks.ai",
            "integrate.api.nvidia.com",
            "ai.cloudflare.com",
            "api.studio.nebius.ai",
            "api.hyperbolic.xyz",
            "chutes.ai",
            "featherless.ai",
            # Asian & Global Providers
            "dashscope.aliyuncs.com",
            "api.moonshot.cn",
            "api.minimax.chat",
            "open.bigmodel.cn",
            "api.siliconflow.cn",
            "byteplus.com",
            "qianfan.baidubce.com",
            "huggingface.co",
            "cursor.com",
            "copilot.github.com",
        ]
    },
    # --- Country ccTLD presets (auto-selected via netools.libs.geo) ---
    "united_states": {
        "country": "US",
        "name": "🇺🇸 United States (.gov, .edu, .us)",
        "domains": [
            "usa.gov", "irs.gov", "nih.gov", "weather.gov",
            "mit.edu", "stanford.edu", "craigslist.org", "nytimes.com",
        ],
    },
    "india": {
        "country": "IN",
        "name": "🇮🇳 India (.in, .gov.in, .co.in)",
        "domains": [
            "india.gov.in", "irctc.co.in", "sbi.co.in", "nic.in",
            "flipkart.com", "hotstar.com", "ndtv.com", "timesofindia.indiatimes.com",
        ],
    },
    "japan": {
        "country": "JP",
        "name": "🇯🇵 Japan (.jp, .co.jp, .go.jp)",
        "domains": [
            "japan.go.jp", "rakuten.co.jp", "yahoo.co.jp", "nhk.or.jp",
            "u-tokyo.ac.jp", "jreast.co.jp", "mufg.jp", "nikkei.com",
        ],
    },
    "germany": {
        "country": "DE",
        "name": "🇩🇪 Germany (.de)",
        "domains": [
            "bund.de", "deutschebahn.com", "spiegel.de", "zdf.de",
            "otto.de", "web.de", "gmx.de", "tu-muenchen.de",
        ],
    },
    "brazil": {
        "country": "BR",
        "name": "🇧🇷 Brazil (.br, .com.br, .gov.br)",
        "domains": [
            "gov.br", "uol.com.br", "globo.com", "mercadolivre.com.br",
            "itau.com.br", "bb.com.br", "usp.br", "registro.br",
        ],
    },
    "united_kingdom": {
        "country": "GB",
        "name": "🇬🇧 United Kingdom (.uk, .co.uk, .gov.uk)",
        "domains": [
            "gov.uk", "bbc.co.uk", "nhs.uk", "barclays.co.uk",
            "rightmove.co.uk", "ox.ac.uk", "theguardian.com", "argos.co.uk",
        ],
    },
    "singapore": {
        "country": "SG",
        "name": "🇸🇬 Singapore (.sg, .gov.sg, .com.sg)",
        "domains": [
            "gov.sg", "singpass.gov.sg", "dbs.com.sg", "nus.edu.sg",
            "straitstimes.com", "carousell.sg", "singtel.com", "sgx.com",
        ],
    },
    "china": {
        "country": "CN",
        "name": "🇨🇳 China (.cn, .com.cn)",
        "domains": [
            "gov.cn", "baidu.com", "qq.com", "taobao.com",
            "jd.com", "bilibili.com", "tsinghua.edu.cn", "sina.com.cn",
        ],
    },
    "south_korea": {
        "country": "KR",
        "name": "🇰🇷 South Korea (.kr, .co.kr, .go.kr)",
        "domains": [
            "korea.kr", "naver.com", "daum.net", "kakaocorp.com",
            "coupang.com", "snu.ac.kr", "kbstar.com", "yna.co.kr",
        ],
    },
    "australia": {
        "country": "AU",
        "name": "🇦🇺 Australia (.au, .com.au, .gov.au)",
        "domains": [
            "australia.gov.au", "abc.net.au", "commbank.com.au", "seek.com.au",
            "realestate.com.au", "unimelb.edu.au", "telstra.com.au", "woolworths.com.au",
        ],
    },
}

# ---------------------------------------------------------------------------
# User-customizable TLD categories (CRUD) for GRC Benchmark Tier-3 targets.
# Built-in TLD_PRESETS are defaults; user edits live in tld_presets.json
# (USER_CONFIG_DIR) and are merged over them. Deleting a built-in hides it.
# ---------------------------------------------------------------------------

TLD_USER_CONFIG_FILE = USER_CONFIG_DIR / "tld_presets.json"


def load_tld_presets() -> Dict[str, Dict[str, Any]]:
    """Effective TLD categories = built-ins merged with user overrides.

    Returns {key: {"name": str, "domains": [..], "builtin": bool, "modified": bool}}
    """
    effective: Dict[str, Dict[str, Any]] = {}
    for k, v in TLD_PRESETS.items():
        effective[k] = {
            "name": v["name"],
            "domains": list(v["domains"]),
            "country": v.get("country", ""),
            "builtin": True,
            "modified": False,
        }

    user_data = _read_user_tld_config()
    # deletions of built-ins
    deleted = set(user_data.get("deleted", []))
    for k in deleted:
        effective.pop(k, None)
    # overrides & additions
    for k, v in user_data.get("categories", {}).items():
        base = effective.get(k, {})
        effective[k] = {
            "name": v.get("name", base.get("name", k)),
            "domains": list(v.get("domains", [])),
            "country": v.get("country", base.get("country", "")),
            "builtin": k in TLD_PRESETS,
            "modified": True,
        }
    return effective


def preset_key_for_country(country_code: str, presets: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
    """Preset key matching an ISO country code, or '' if none."""
    if not country_code:
        return ""
    cc = country_code.upper()
    for k, v in (presets or load_tld_presets()).items():
        if v.get("country", "").upper() == cc:
            return k
    return ""


def _read_user_tld_config() -> Dict[str, Any]:
    if not TLD_USER_CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(TLD_USER_CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_tld_category(key: str, name: str, domains: List[str]) -> bool:
    """Create or update a TLD category (user-level; overlays built-ins)."""
    key = key.strip().lower().replace(" ", "_")
    domains = [d.strip().lower() for d in domains if d.strip()]
    if not key or not name.strip():
        return False
    cfg = _read_user_tld_config()
    cats = cfg.setdefault("categories", {})
    cats[key] = {"name": name.strip(), "domains": domains}
    try:
        TLD_USER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        TLD_USER_CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        log.warning(f"save_tld_category failed: {e}")
        return False


def delete_tld_category(key: str) -> bool:
    """Delete a category. Built-ins are recorded as hidden; customs removed."""
    key = key.strip().lower().replace(" ", "_")
    cfg = _read_user_tld_config()
    cats = cfg.setdefault("categories", {})
    changed = False
    if key in cats:
        del cats[key]
        changed = True
    if key in TLD_PRESETS:
        cfg.setdefault("deleted", [])
        if key not in cfg["deleted"]:
            cfg["deleted"].append(key)
        changed = True
    if not changed:
        return False
    try:
        TLD_USER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        TLD_USER_CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        log.warning(f"delete_tld_category failed: {e}")
        return False


def reset_tld_presets() -> None:
    """Remove all user customization, restoring built-in presets."""
    try:
        TLD_USER_CONFIG_FILE.unlink(missing_ok=True)
    except Exception as e:
        log.debug(f"reset_tld_presets: {e}")


def reset_to_default_providers() -> Dict[str, Dict[str, Any]]:
    """Reset providers cache to built-in presets."""
    if CACHE_FILE.exists():
        try:
            CACHE_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    return dict(BUILTIN_PROVIDERS)
