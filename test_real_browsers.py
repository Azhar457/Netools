#!/usr/bin/env python3
"""
Real-world browser session extraction test.
Scans actual browser LevelDB on this machine and reports what tokens are found.
Run this while logged into Kimi/Z.ai in your browser.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from netools.services.session_extractor import (
    BROWSER_PATHS,
    decode_jwt_payload,
    extract_all_browser_sessions,
    extract_chromium_storage,
)
from netools.services.omniroute_bridge import compute_token_ttl


def scan_raw_leveldb():
    """Raw LevelDB scan to show ALL JWT tokens found, before filtering."""
    print("=" * 70)
    print("RAW LevelDB SCAN — All JWT tokens found in browser storage")
    print("=" * 70)

    import re
    jwt_pattern = re.compile(rb"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")

    for b_name, paths in BROWSER_PATHS.items():
        for base_path in paths:
            if not base_path.exists():
                continue

            if b_name == "Firefox":
                # Scan Firefox sub-profiles
                for child in base_path.iterdir():
                    if not child.is_dir():
                        continue
                    ldb = child / "Local Storage" / "leveldb"
                    if not ldb.exists():
                        continue
                    _scan_leveldb_dir(ldb, f"Firefox/{child.name}")
            else:
                ldb = base_path / "Local Storage" / "leveldb"
                if ldb.exists():
                    _scan_leveldb_dir(ldb, b_name)


def _scan_leveldb_dir(ldb_dir: Path, browser_label: str):
    """Scan a single LevelDB directory for JWT tokens."""
    files = list(ldb_dir.glob("*.ldb")) + list(ldb_dir.glob("*.log"))
    if not files:
        return

    total_jwts = 0
    providers_found = {}

    for f in files:
        try:
            raw = f.read_bytes()
            matches = jwt_pattern.findall(raw)
            for m in matches:
                total_jwts += 1
                token_str = m.decode("ascii")
                payload = decode_jwt_payload(token_str)
                if not payload:
                    continue

                # Quick provider detection
                prov = "unknown"
                aud = payload.get("aud", [])
                app_id = payload.get("app_id", "")
                email = payload.get("email", "")
                sub = payload.get("sub", "")
                raw_lower = raw[:500].decode("ascii", errors="ignore").lower()

                if app_id == "kimi" or "kimi.ai" in aud:
                    prov = "kimi-web"
                elif "email" in payload and "id" in payload and len(payload) <= 3:
                    prov = "zai-web"
                elif "deepseek" in raw_lower:
                    prov = "deepseek-web"
                elif "claude" in raw_lower or "anthropic" in raw_lower:
                    prov = "claude-web"
                elif "perplexity" in raw_lower:
                    prov = "perplexity-web"
                elif "chatgpt" in raw_lower or "openai" in raw_lower:
                    prov = "chatgpt-web"

                if prov not in providers_found:
                    providers_found[prov] = []
                providers_found[prov].append({
                    "token_preview": token_str[:50] + "...",
                    "payload_keys": list(payload.keys()),
                    "email": email or sub or "N/A",
                    "exp": payload.get("exp"),
                    "typ": payload.get("typ", "N/A"),
                    "app_id": app_id,
                })

        except Exception:
            continue

    if total_jwts == 0:
        print(f"\n  [{browser_label}] No JWT tokens found in LevelDB")
        return

    print(f"\n  [{browser_label}] {total_jwts} raw JWT tokens found in LevelDB files")
    for prov, tokens in sorted(providers_found.items()):
        print(f"    → {prov}: {len(tokens)} token(s)")
        for t in tokens[:3]:  # Show first 3
            exp_str = "no exp"
            if t["exp"]:
                remaining = t["exp"] - time.time()
                if remaining > 0:
                    exp_str = f"active ({int(remaining/60)}m remaining)"
                else:
                    exp_str = f"EXPIRED ({int(-remaining/60)}m ago)"
            print(f"      email={t['email']}, typ={t['typ']}, app_id={t['app_id']}, exp={exp_str}")
            print(f"      keys={t['payload_keys']}")


def scan_filtered_sessions():
    """Run the actual extract_all_browser_sessions and report results."""
    print("\n" + "=" * 70)
    print("FILTERED SESSION EXTRACTION (via extract_all_browser_sessions)")
    print("=" * 70)

    # Scan all providers
    sessions = extract_all_browser_sessions(
        browser_filter="all",
        provider_filter="all",
    )

    if not sessions:
        print("\n  No sessions found! Are you logged into any AI provider in your browser?")
        print("  Make sure you've visited at least one of: kimi.ai, chat.z.ai, chat.deepseek.com")
        return

    print(f"\n  Total filtered sessions: {len(sessions)}\n")

    for i, s in enumerate(sessions):
        ttl = s.get("ttl")
        ttl_label = ttl.label if ttl else "❓ Unknown"
        ttl_status = ttl.status if ttl else "unknown"

        print(f"  [{i+1}] Provider:  {s['provider']}")
        print(f"      Account:  {s['account']}")
        print(f"      Browser:  {s['browser']}")
        print(f"      TTL:      {ttl_label}")
        print(f"      Status:   {ttl_status}")
        print(f"      Token:    {s['token'][:60]}...")
        print(f"      Payload:  {list(s.get('payload', {}).keys())}")
        print()


def test_kimi_specific():
    """Deep-dive test for Kimi Web provider."""
    print("\n" + "=" * 70)
    print("KIMI WEB — Specific Test")
    print("=" * 70)

    sessions = extract_all_browser_sessions(
        browser_filter="all",
        provider_filter="kimi-web",
    )

    if not sessions:
        print("\n  ❌ No Kimi Web sessions found!")
        print("  Possible causes:")
        print("    1. Not logged into kimi.ai in any browser")
        print("    2. Kimi tokens are stored differently (not in LevelDB)")
        print("    3. Token format changed")
        return False

    print(f"\n  ✅ Found {len(sessions)} Kimi session(s):\n")
    for s in sessions:
        ttl = s.get("ttl")
        print(f"    Account: {s['account']}")
        print(f"    Browser: {s['browser']}")
        print(f"    TTL:     {ttl.label if ttl else 'unknown'}")
        print(f"    Token:   {s['token'][:80]}...")

        # Validate token structure
        payload = s.get("payload", {})
        print(f"    Payload checks:")
        print(f"      has app_id='kimi': {payload.get('app_id') == 'kimi'}")
        print(f"      has aud with kimi.ai: {'kimi.ai' in payload.get('aud', [])}")
        print(f"      has sub (account): {'sub' in payload and bool(payload['sub'])}")
        print(f"      has exp (expiry): {'exp' in payload}")
        if "exp" in payload:
            remaining = payload["exp"] - time.time()
            print(f"      exp remaining: {int(remaining/60)} minutes")
        print()
    return True


def test_zai_specific():
    """Deep-dive test for Z.ai Web provider."""
    print("\n" + "=" * 70)
    print("Z.AI WEB — Specific Test")
    print("=" * 70)

    sessions = extract_all_browser_sessions(
        browser_filter="all",
        provider_filter="zai-web",
    )

    if not sessions:
        print("\n  ❌ No Z.ai Web sessions found!")
        print("  Possible causes:")
        print("    1. Not logged into chat.z.ai in any browser")
        print("    2. Z.ai tokens are stored differently (not in LevelDB)")
        print("    3. Token format changed (payload has >3 keys now)")
        return False

    print(f"\n  ✅ Found {len(sessions)} Z.ai session(s):\n")
    for s in sessions:
        ttl = s.get("ttl")
        print(f"    Account: {s['account']}")
        print(f"    Browser: {s['browser']}")
        print(f"    TTL:     {ttl.label if ttl else 'unknown'}")
        print(f"    Token:   {s['token'][:80]}...")

        # Validate token structure
        payload = s.get("payload", {})
        print(f"    Payload checks:")
        print(f"      has email: {'email' in payload} → {payload.get('email', 'N/A')}")
        print(f"      has id: {'id' in payload} → {payload.get('id', 'N/A')}")
        print(f"      payload size: {len(payload)} keys")
        print(f"      all keys: {list(payload.keys())}")
        print()
    return True


def test_injection():
    """Test injection to OmniRoute DB (dry run — asks for confirmation)."""
    print("\n" + "=" * 70)
    print("INJECTION TEST (to OmniRoute storage.sqlite)")
    print("=" * 70)

    sessions = extract_all_browser_sessions(
        browser_filter="all",
        provider_filter="all",
    )

    kimi = [s for s in sessions if s["provider"] == "kimi-web"]
    zai = [s for s in sessions if s["provider"] == "zai-web"]

    if not kimi and not zai:
        print("\n  No Kimi or Z.ai sessions to inject.")
        return

    from netools.services.omniroute_bridge import inject_session_to_omniroute, get_db_path
    db = get_db_path()
    print(f"\n  OmniRoute DB: {db}")
    print(f"  DB exists: {db.exists()}")

    if not db.exists():
        print("  ⚠️  DB not found — skipping injection test")
        return

    for s in (kimi + zai)[:2]:  # Test first 1-2 sessions
        print(f"\n  Injecting: {s['provider']} ({s['account']})...")
        result = inject_session_to_omniroute(
            provider=s["provider"],
            token=s["token"],
            name=s["account"],
        )
        status = "✅" if result.success else "❌"
        print(f"  {status} {result.message}")
        print(f"     Action: {result.action}")


if __name__ == "__main__":
    print("Netools Cookie Extractor — Real-World Browser Test")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 1. Raw scan
    scan_raw_leveldb()

    # 2. Filtered extraction
    scan_filtered_sessions()

    # 3. Provider-specific tests
    kimi_ok = test_kimi_specific()
    zai_ok = test_zai_specific()

    # 4. Injection test
    test_injection()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Kimi Web:  {'✅ Working' if kimi_ok else '❌ Not found / broken'}")
    print(f"  Z.ai Web:  {'✅ Working' if zai_ok else '❌ Not found / broken'}")
    print()
    print("  If providers show 'Not found', make sure you are:")
    print("    1. Logged into the provider in Brave/Chrome/Firefox")
    print("    2. The browser profile path exists on this machine")
    print("    3. The provider stores tokens in LevelDB (Local Storage)")
