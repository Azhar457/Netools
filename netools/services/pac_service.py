"""
PAC Service: Dynamic PAC generation and HTTP Server on 127.0.0.1:18080 with clean ON/OFF lifecycle.
"""

import http.server
import socketserver
import threading
from typing import Optional

from netools.config import PAC_SERVER_PORT
from netools.libs.logger import get_logger
from netools.libs.net import is_port_open
from netools.state import load_state, save_state

log = get_logger(__name__)

class PACHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/proxy.pac", "/pac"):
            content = self.generate_pac_content().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ns-proxy-autoconfig")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        elif self.path in ("/status", "/health", "/healthz", "/api/health"):
            import json
            state = load_state()
            instances = state.get("instances", {})
            alive_count = sum(1 for p in instances.values() if is_port_open(p.get("port", 0)))
            total_count = len(instances)
            
            if self.path == "/status":
                msg = f"PAC Server OK - {alive_count}/{total_count} proxies active\n".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
            else:
                data = {
                    "status": "healthy" if (alive_count > 0 or total_count == 0) else "degraded",
                    "pac_server": "running",
                    "pac_url": get_pac_url(PAC_SERVER_PORT),
                    "proxies_alive": alive_count,
                    "proxies_total": total_count,
                    "updated_at": state.get("updated_at", ""),
                }
                body = json.dumps(data, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


    def generate_pac_content(self) -> str:
        state = load_state()
        instances = state.get("instances", {})
        if not instances:
            # Fallback to standard range (SOCKS5, SOCKS, and HTTP proxy)
            proxy_list = [f"SOCKS5 127.0.0.1:{11080 + i}; SOCKS 127.0.0.1:{11080 + i}; PROXY 127.0.0.1:{21080 + i}" for i in range(20)]
        else:
            proxy_list = [f"SOCKS5 127.0.0.1:{info['port']}; SOCKS 127.0.0.1:{info['port']}; PROXY 127.0.0.1:{info['port'] + 10000}" for info in instances.values()]

        proxies_str = "; ".join(proxy_list) + "; DIRECT"

        return f"""function FindProxyForURL(url, host) {{
    // Fast & safe local/private bypass (avoids dnsResolve IPv6 exceptions & DNS leaks)
    if (isPlainHostName(host) ||
        shExpMatch(host, "*.local") ||
        shExpMatch(host, "localhost") ||
        shExpMatch(host, "127.*") ||
        shExpMatch(host, "10.*") ||
        shExpMatch(host, "192.168.*") ||
        shExpMatch(host, "172.16.*") ||
        shExpMatch(host, "172.17.*") ||
        shExpMatch(host, "172.18.*") ||
        shExpMatch(host, "172.19.*") ||
        shExpMatch(host, "172.2*") ||
        shExpMatch(host, "172.3*") ||
        shExpMatch(host, "*.internal") ||
        shExpMatch(host, "*.lan")) {{
        return "DIRECT";
    }}
    return "{proxies_str}";
}}
"""

    def log_message(self, format, *args):
        pass

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

_pac_httpd: Optional[ReusableTCPServer] = None
_pac_lock = threading.Lock()

def get_pac_url(port: int = PAC_SERVER_PORT) -> str:
    """Return the complete PAC URL string."""
    return f"http://127.0.0.1:{port}/proxy.pac"

def is_pac_server_running(port: int = PAC_SERVER_PORT) -> bool:
    """Check if the PAC HTTP server is currently listening on port."""
    return is_port_open(port)

def start_pac_server(port: int = PAC_SERVER_PORT) -> bool:
    """Start the PAC HTTP server in background thread."""
    global _pac_httpd
    with _pac_lock:
        if is_port_open(port):
            return True
        try:
            _pac_httpd = ReusableTCPServer(("127.0.0.1", port), PACHandler)
            t = threading.Thread(target=_pac_httpd.serve_forever, daemon=True)
            t.start()
            
            state = load_state()
            state["pac_status"] = "active"
            state["pac_url"] = get_pac_url(port)
            save_state(state)
            log.info(f"Server started on {get_pac_url(port)}")
            return True
        except Exception as e:
            log.error(f"Error starting server: {e}")
            return False

def stop_pac_server() -> bool:
    """Stop the PAC HTTP server cleanly."""
    global _pac_httpd
    with _pac_lock:
        if _pac_httpd:
            try:
                _pac_httpd.shutdown()
                _pac_httpd.server_close()
            except Exception:
                pass
            _pac_httpd = None

        state = load_state()
        state["pac_status"] = "inactive"
        save_state(state)
        log.info("Server stopped")
        return True

def start_pac_server_blocking(port: int = PAC_SERVER_PORT) -> None:
    """Run PAC HTTP server synchronously (used by CLI netools pac start)."""
    global _pac_httpd
    try:
        _pac_httpd = ReusableTCPServer(("127.0.0.1", port), PACHandler)
        log.info(f"Serving dynamic PAC on {get_pac_url(port)}")
        _pac_httpd.serve_forever()
    except KeyboardInterrupt:
        stop_pac_server()
