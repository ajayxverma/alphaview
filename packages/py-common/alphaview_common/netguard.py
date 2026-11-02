import asyncio
import ipaddress
from urllib.parse import urlparse


class UnsafeEndpointError(ValueError):
    pass


async def validate_endpoint(url: str, allow_private: bool = False) -> str:
    """Reject user-supplied endpoints that could reach internal services (SSRF)."""
    parsed = urlparse(url.strip())
    allowed_schemes = {"https", "http"} if allow_private else {"https"}
    if parsed.scheme not in allowed_schemes:
        raise UnsafeEndpointError(f"URL must use {' or '.join(sorted(allowed_schemes))}")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeEndpointError("URL must have a host and no embedded credentials")
    if allow_private:
        return url.strip().rstrip("/")

    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, parsed.port or 443)
    except OSError as exc:
        raise UnsafeEndpointError(f"Cannot resolve host {parsed.hostname}") from exc
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise UnsafeEndpointError("URL resolves to a private or reserved address")
    return url.strip().rstrip("/")
