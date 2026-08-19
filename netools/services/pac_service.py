"""
PAC Service: Dynamic PAC generation and HTTP Server on 127.0.0.1:18080 with clean ON/OFF lifecycle.
"""

import http.server
import socketserver
import threading
from typing import Optional
from netools.config import PAC_SERVER_PORT, STATIC_PAC_FILE
from netools.libs.net import is_port_open
from netools.state import load_state, save_state

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
        elif self.path == "/status":
            state = load_state()
            active = len(state.get("instances", {}))
            msg = f"PAC Server OK - {active} proxies active\n".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(msg)
        else:
            self.send_response(404)
            self.end_headers()

    def generate_pac_content(self) -> str:
        state = load_state()
        instances = state.get("instances", {})
        if not instances:
            # Fallback to standard range
            proxy_list = [f"SOCKS5 127.0.0.1:{11080 + i}; SOCKS 127.0.0.1:{11080 + i}" for i in range(20)]
        else:
            proxy_list = [f"SOCKS5 127.0.0.1:{info['port']}; SOCKS 127.0.0.1:{info['port']}" for info in instances.values()]

        proxies_str = "; ".join(proxy_list) + "; DIRECT"

        return f"""function FindProxyForURL(url, host) {{
    // Local / private IP bypass
    if (isPlainHostName(host) ||
        shExpMatch(host, "*.local") ||
        isInNet(dnsResolve(host), "10.0.0.0", "255.0.0.0") ||
        isInNet(dnsResolve(host), "172.16.0.0", "255.240.0.0") ||
        isInNet(dnsResolve(host), "192.168.0.0", "255.255.0.0") ||
        isInNet(dnsResolve(host), "127.0.0.0", "255.0.0.0")) {{
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
            print(f"[PAC] Server started on {get_pac_url(port)}")
            return True
        except Exception as e:
            print(f"[PAC] Error starting server: {e}")
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
        print("[PAC] Server stopped.")
        return True

def start_pac_server_blocking(port: int = PAC_SERVER_PORT) -> None:
    """Run PAC HTTP server synchronously (used by CLI netools pac start)."""
    global _pac_httpd
    try:
        _pac_httpd = ReusableTCPServer(("127.0.0.1", port), PACHandler)
        print(f"[PAC] Serving dynamic PAC on {get_pac_url(port)}")
        _pac_httpd.serve_forever()
    except KeyboardInterrupt:
        stop_pac_server()
