"""SSRF protection for the web research subsystem.
Every URL that NEXA ever fetches (an initial request or a redirect target)
must pass through :func:`validate_url` first. This blocks:
- non-``http``/``https`` schemes (in particular ``file://``);
- ``localhost`` and other loopback hostnames;
- literal IP addresses in private/loopback/link-local/reserved ranges
  (covers RFC1918 private networks and the cloud metadata address
  ``169.254.169.254``, which falls under link-local);
- hostnames that *resolve* to any such address (DNS rebinding protection) -
  the resolver is injectable so this is fully testable offline.
"""
from __future__ import annotations
import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlparse, urlunparse
from app.models.errors import InvalidURLError, SSRFProtectionError
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})
BLOCKED_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",  # GCP metadata service
        "instance-data",  # AWS/OpenStack metadata alias
    }
)
Resolver = Callable[[str, "int | None"], list]
def _default_resolver(hostname: str, port: int | None = None) -> list:
    return socket.getaddrinfo(hostname, port)
def is_ip_blocked(ip_str: str) -> bool:
    """Return ``True`` if ``ip_str`` falls in a range that must never be fetched."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # not a parseable IP - treat conservatively as blocked
    # IPv4-mapped IPv6 (::ffff:127.0.0.1) reports is_loopback=False on the v6
    # object — unwrap and re-check the embedded IPv4 address.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return is_ip_blocked(str(mapped))
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )
def validate_url(url: str, resolver: Resolver = _default_resolver) -> str:
    """Validate ``url`` is safe to fetch. Returns ``url`` unchanged if so.
    Raises:
        app.models.errors.InvalidURLError: If the URL is malformed, uses a
            disallowed scheme, or its host cannot be resolved.
        app.models.errors.SSRFProtectionError: If the URL's host is (or
            resolves to) a blocked address.
    """
    if not url or "\x00" in url:
        raise InvalidURLError("URL must be a non-empty string without NUL bytes.")
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise InvalidURLError(f"Could not parse URL: {url}") from exc
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise SSRFProtectionError(
            f"Scheme '{scheme or '(none)'}' is not allowed. Only http/https are permitted."
        )
    hostname = parsed.hostname
    if not hostname:
        raise InvalidURLError(f"URL has no host: {url}")
    if hostname.lower() in BLOCKED_HOSTNAMES:
        raise SSRFProtectionError(f"Host '{hostname}' is blocked.")
    # Literal IP address (v4 or v6, optionally bracketed) - check directly.
    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        if is_ip_blocked(str(literal_ip)):
            raise SSRFProtectionError(f"IP address '{literal_ip}' is blocked.")
        return url
    # Otherwise resolve the hostname and check every candidate address, to
    # defend against DNS rebinding (a public-looking hostname that resolves
    # to a private/internal IP).
    try:
        results = resolver(hostname, None)
    except OSError as exc:
        raise InvalidURLError(f"Could not resolve host: {hostname}") from exc
    if not results:
        raise InvalidURLError(f"Could not resolve host: {hostname}")
    for entry in results:
        sockaddr = entry[4]
        ip_str = sockaddr[0]
        if is_ip_blocked(ip_str):
            raise SSRFProtectionError(
                f"Host '{hostname}' resolves to a blocked address ({ip_str})."
            )
    return url



def pin_url_to_validated_address(url: str, resolver: Resolver = _default_resolver) -> tuple[str, str]:
    """Return an IP-literal URL plus the original hostname for Host/SNI.

    Validation is repeated for the exact address used by the socket. The HTTP
    client therefore cannot perform a second DNS lookup after validation.
    """
    validate_url(url, resolver)
    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname is None:
        raise InvalidURLError(f"URL has no host: {url}")
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            results = resolver(hostname, parsed.port)
        except OSError as exc:
            raise InvalidURLError(f"Could not resolve host: {hostname}") from exc
        if not results:
            raise InvalidURLError(f"Could not resolve host: {hostname}")
        addresses = [entry[4][0] for entry in results]
        for address in addresses:
            if is_ip_blocked(address):
                raise SSRFProtectionError(
                    f"Host '{hostname}' resolves to a blocked address ({address})."
                )
        selected = ipaddress.ip_address(addresses[0])
    else:
        if is_ip_blocked(str(literal)):
            raise SSRFProtectionError(f"IP address '{literal}' is blocked.")
        selected = literal

    host_literal = f"[{selected}]" if selected.version == 6 else str(selected)
    netloc = host_literal
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    pinned = urlunparse(parsed._replace(netloc=netloc))
    return pinned, hostname
