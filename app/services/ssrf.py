import ipaddress
import socket
from typing import cast
from urllib.parse import urlparse

_PRIVATE_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
)


class InvalidFetchUrl(ValueError):
    pass


def _resolve(host: str, port: int) -> list[str]:
    return [cast(str, info[4][0]) for info in socket.getaddrinfo(host, port)]


def _is_internal(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(ip in network for network in _PRIVATE_NETWORKS)


def validate_fetch_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise InvalidFetchUrl("only http/https URLs are allowed")
    host = parsed.hostname or ""
    if not host or host.lower() == "localhost":
        raise InvalidFetchUrl("local hosts are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for ip_str in _resolve(host, port):
        if _is_internal(ipaddress.ip_address(ip_str)):
            raise InvalidFetchUrl("internal/private addresses are not allowed")