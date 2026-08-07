"""URL safety helpers for JD ingest (block SSRF to private/link-local targets)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    """Raised when a URL must not be fetched."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (ip.version == 4 and ip in ipaddress.ip_network("169.254.0.0/16"))
        or (ip.version == 6 and ip in ipaddress.ip_network("fc00::/7"))
    )


def assert_public_http_url(url: str, *, resolve: bool = True) -> str:
    """
    Validate that ``url`` is http(s) and does not target private/link-local hosts.

    When ``resolve`` is True, DNS is resolved and every address is checked.
    Returns the normalized URL string.
    """
    raw = (url or "").strip()
    if not raw:
        raise UnsafeUrlError("URL is empty")
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise UnsafeUrlError("Only http and https URLs are allowed")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL is missing a hostname")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("URLs with embedded credentials are not allowed")

    # Literal IPs in the hostname
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and _is_blocked_ip(ip):
        raise UnsafeUrlError("Refusing to fetch private or link-local addresses")

    if host.lower() in {"localhost", "metadata.google.internal"}:
        raise UnsafeUrlError("Refusing to fetch localhost / metadata hosts")

    if resolve:
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if scheme == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise UnsafeUrlError(f"Could not resolve host: {host}") from exc
        if not infos:
            raise UnsafeUrlError(f"Could not resolve host: {host}")
        for info in infos:
            addr = info[4][0]
            try:
                resolved = ipaddress.ip_address(addr)
            except ValueError:
                continue
            if _is_blocked_ip(resolved):
                raise UnsafeUrlError("Refusing to fetch a host that resolves to a private address")

    return raw
