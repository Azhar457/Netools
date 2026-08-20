"""
Universal Proxy URI parser: Shadowsocks, Trojan, VMess, VLESS.
"""

import base64
import json
from urllib.parse import unquote, urlparse, parse_qs
from typing import Optional, Dict, Any, List

def decode_base64_if_needed(text: str) -> str:
    """If entire text looks like base64, decode it."""
    stripped = text.strip()
    if stripped.startswith(("ss://", "trojan://", "vmess://", "vless://")):
        return stripped
    try:
        decoded = base64.b64decode(stripped + "==").decode("utf-8", errors="ignore")
        if "://" in decoded:
            return decoded
    except Exception:
        pass
    return stripped

def parse_ss_uri(uri: str) -> Optional[Dict[str, Any]]:
    """Parse ss://... URI into config dict."""
    try:
        rest = uri.split("://", 1)[1]
        if "@" in rest:
            encoded_part, server_part = rest.rsplit("@", 1)
        else:
            return None

        try:
            decoded = base64.b64decode(encoded_part + "==").decode()
            method, password = decoded.split(":", 1)
        except Exception:
            method, password = encoded_part, ""

        if "#" in server_part:
            server_part, tag = server_part.rsplit("#", 1)
            tag = unquote(tag)
        else:
            tag = f"ss-{server_part.split(':')[0]}"

        host, port = server_part.rsplit(":", 1)
        return {
            "type": "shadowsocks",
            "tag": tag,
            "server": host,
            "server_port": int(port),
            "method": method,
            "password": password,
        }
    except Exception:
        return None

def parse_trojan_uri(uri: str) -> Optional[Dict[str, Any]]:
    """Parse trojan://... URI."""
    try:
        rest = uri.split("://", 1)[1]
        if "@" in rest:
            password, server_part = rest.rsplit("@", 1)
        else:
            return None

        if "#" in server_part:
            server_part, tag = server_part.rsplit("#", 1)
            tag = unquote(tag)
        else:
            tag = f"trojan-{server_part.split(':')[0]}"

        host_port, *query_parts = server_part.split("?", 1)
        host, port = host_port.rsplit(":", 1)

        sni = host
        if query_parts:
            params = parse_qs(query_parts[0])
            sni = params.get("sni", [host])[0]

        return {
            "type": "trojan",
            "tag": tag,
            "server": host,
            "server_port": int(port),
            "password": password,
            "tls": {
                "enabled": True,
                "server_name": sni,
                "insecure": True,
            },
        }
    except Exception:
        return None

def parse_vmess_uri(uri: str) -> Optional[Dict[str, Any]]:
    """Parse vmess://... (base64 JSON) URI."""
    try:
        b64 = uri.split("://", 1)[1]
        data = json.loads(base64.b64decode(b64 + "==").decode("utf-8", errors="ignore"))
        return {
            "type": "vmess",
            "tag": data.get("ps", f"vmess-{data.get('add', '')}"),
            "server": data["add"],
            "server_port": int(data["port"]),
            "uuid": data["id"],
            "alter_id": int(data.get("aid", 0)),
            "security": "auto",
            "transport": {
                "type": data.get("net", "tcp"),
                "path": data.get("path", ""),
                "headers": {"Host": data.get("host", "")} if data.get("host") else {},
            } if data.get("net") in ("ws", "grpc") else None,
            "tls": {
                "enabled": data.get("tls") == "tls",
                "server_name": data.get("sni", data.get("host", data["add"])),
                "insecure": True,
            } if data.get("tls") == "tls" else None,
        }
    except Exception:
        return None

def parse_vless_uri(uri: str) -> Optional[Dict[str, Any]]:
    """Parse vless://uuid@host:port?query#tag URI."""
    try:
        rest = uri.split("://", 1)[1]
        if "@" in rest:
            uuid_str, server_part = rest.rsplit("@", 1)
        else:
            return None

        if "#" in server_part:
            server_part, tag = server_part.rsplit("#", 1)
            tag = unquote(tag)
        else:
            tag = f"vless-{server_part.split(':')[0]}"

        host_port, *query_parts = server_part.split("?", 1)
        host, port = host_port.rsplit(":", 1)

        params: Dict[str, List[str]] = {}
        if query_parts:
            params = parse_qs(query_parts[0])

        net_type = params.get("type", ["tcp"])[0]
        security = params.get("security", ["none"])[0]
        sni = params.get("sni", [host])[0]
        flow = params.get("flow", [""])[0]
        path = params.get("path", [""])[0]
        host_header = params.get("host", [""])[0]

        proxy_dict: Dict[str, Any] = {
            "type": "vless",
            "tag": tag,
            "server": host,
            "server_port": int(port),
            "uuid": uuid_str,
        }

        if flow:
            proxy_dict["flow"] = flow

        if security in ("tls", "reality"):
            proxy_dict["tls"] = {
                "enabled": True,
                "server_name": sni,
                "insecure": True,
            }
            if security == "reality":
                pbk = params.get("pbk", [""])[0]
                sid = params.get("sid", [""])[0]
                if pbk:
                    proxy_dict["tls"]["reality"] = {
                        "enabled": True,
                        "public_key": pbk,
                        "short_id": sid,
                    }

        if net_type in ("ws", "grpc"):
            proxy_dict["transport"] = {
                "type": net_type,
                "path": path,
                "headers": {"Host": host_header} if host_header else {},
            }

        return proxy_dict
    except Exception:
        return None

def parse_proxy_uri(uri: str) -> Optional[Dict[str, Any]]:
    """Parse any supported proxy URI (ss, trojan, vmess, vless)."""
    uri = uri.strip()
    if uri.startswith("ss://"):
        return parse_ss_uri(uri)
    elif uri.startswith("trojan://"):
        return parse_trojan_uri(uri)
    elif uri.startswith("vmess://"):
        return parse_vmess_uri(uri)
    elif uri.startswith("vless://"):
        return parse_vless_uri(uri)
    return None

def extract_all_proxies(raw_text: str, max_count: int = 20) -> List[Dict[str, Any]]:
    """Parse entire proxy subscription text and deduplicate by host:port."""
    text = decode_base64_if_needed(raw_text)
    lines = text.strip().splitlines()

    proxies = []
    seen = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        p = parse_proxy_uri(line)
        if p and p.get("server") and p.get("server_port"):
            key = f"{p['server']}:{p['server_port']}"
            if key not in seen:
                seen.add(key)
                proxies.append(p)
                if len(proxies) >= max_count:
                    break
    return proxies
