"""
RFC 8484 DNS Packet Builder & Base64URL Converter.
"""

import base64
import struct


def uint8_to_base64url(data: bytes) -> str:
    """Convert bytes to URL-safe Base64 without padding."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

def build_dns_query_packet(domain: str, tx_id: int = 0x1234, qtype: int = 1) -> bytes:
    """Construct a raw RFC 1035 / RFC 8484 DNS query packet (default Type 1 = A record)."""
    clean_domain = domain.strip().strip(".")
    parts = clean_domain.split(".")

    qname = bytearray()
    for part in parts:
        b = part.encode("ascii")
        qname.append(len(b))
        qname.extend(b)
    qname.append(0)

    header = struct.pack(">HHHHHH", tx_id, 0x0100, 1, 0, 0, 0)
    footer = struct.pack(">HH", qtype, 1)  # QTYPE, QCLASS IN (1)
    return header + bytes(qname) + footer
