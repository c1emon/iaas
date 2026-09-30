"""Controlled environment proxies and authentication-safe diagnostic capture."""

from __future__ import annotations

import base64
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import os
import re
from urllib.parse import quote, quote_plus, unquote, urlsplit
import urllib.request

from iaas.common.errors import ValidationError


PROXY_PAIRS = (("HTTP_PROXY", "http_proxy"), ("HTTPS_PROXY", "https_proxy"), ("NO_PROXY", "no_proxy"))
PROXY_NAMES = {name for pair in PROXY_PAIRS for name in pair}
NEUTRALIZED_NAMES = {"ALL_PROXY", "all_proxy", "FTP_PROXY", "ftp_proxy"}


class ProxyConfigurationError(ValidationError):
    """Only variable names and literal categories may appear in this error."""


def _validate_url(value: str, name: str) -> None:
    try:
        if any(ord(character) <= 32 or ord(character) == 127 for character in value):
            raise ValueError
        parsed = urlsplit(value)
        if (not value.startswith(("http://", "https://")) or not parsed.hostname
                or parsed.path not in ("", "/") or "?" in value or "#" in value
                or "\\" in value or parsed.netloc.endswith(":")):
            raise ValueError
        # Accessing port validates both integer syntax and the range.
        if parsed.port is not None and parsed.port < 1:
            raise ValueError
        if re.search(r"%(?![0-9A-Fa-f]{2})", value):
            raise ValueError
        if "@" in parsed.netloc:
            if parsed.netloc.count("@") != 1 or not parsed.username:
                raise ValueError
            decoded = unquote(parsed.netloc.rsplit("@", 1)[0])
            if any(ord(character) < 32 or ord(character) == 127 for character in decoded):
                raise ValueError
            if ":" in unquote(parsed.username):
                raise ValueError
        host = parsed.hostname
        if not host or "%" in host or any(character in host for character in " /\\@"):
            raise ValueError
    except (ValueError, UnicodeError):
        raise ProxyConfigurationError(f"{name} has invalid proxy URL") from None


def normalize_proxy_environment(supplied: Mapping[str, str], *, network: bool) -> dict[str, str]:
    if not network:
        return {}
    normalized: dict[str, str] = {}
    for upper, lower in PROXY_PAIRS:
        first, second = supplied.get(upper, "").strip(), supplied.get(lower, "").strip()
        if first and second and first != second:
            raise ProxyConfigurationError(f"{upper}/{lower} proxy values conflict")
        value = first or second
        if not value:
            continue
        if upper != "NO_PROXY":
            _validate_url(value, upper)
        elif any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ProxyConfigurationError("NO_PROXY has invalid control characters")
        normalized[upper] = normalized[lower] = value
    return normalized


def proxy_configured(environ: Mapping[str, str]) -> bool:
    return any(environ.get(name) for name in PROXY_NAMES)


@contextmanager
def process_proxy_environment(environ: Mapping[str, str]) -> Iterator[None]:
    """Apply the filtered configuration before environment-aware urllib clients."""
    names = PROXY_NAMES | NEUTRALIZED_NAMES
    previous = {name: os.environ.get(name) for name in names}
    previous_opener = getattr(urllib.request, "_opener", None)
    try:
        for name in names:
            if value := environ.get(name):
                os.environ[name] = value
            else:
                os.environ.pop(name, None)
        proxies = {protocol: environ[name] for protocol, name in (
            ("http", "http_proxy"), ("https", "https_proxy")) if environ.get(name)}
        urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler(proxies)))
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        urllib.request.install_opener(previous_opener)


class ProxyRedactor:
    """Replace configured proxy material, including credentials split across reads."""

    def __init__(self, environ: Mapping[str, str]):
        secrets: set[str] = set()
        for name in PROXY_NAMES:
            value = environ.get(name, "")
            if not value:
                continue
            secrets.add(value)
            if name.upper() == "NO_PROXY":
                continue
            parsed = urlsplit(value)
            if "@" not in parsed.netloc:
                continue
            userinfo = parsed.netloc.rsplit("@", 1)[0]
            username, password = unquote(parsed.username or ""), unquote(parsed.password or "")
            secrets.update((userinfo, unquote(userinfo), parsed.username or "", parsed.password or "",
                            username, password))
            authorization = base64.b64encode(f"{username}:{password}".encode()).decode()
            secrets.update((authorization, f"Basic {authorization}"))
        for value in tuple(secrets):
            if value:
                secrets.update((quote(value, safe=""), quote_plus(value, safe="")))
        tokens = sorted({value.encode() for value in secrets if value}, key=len, reverse=True)
        def encoded_pattern(token: bytes) -> bytes:
            def hex_pair(match: re.Match[bytes]) -> bytes:
                return b"%" + b"".join(bytes((value,)) if value < 65 else
                                       b"[" + bytes((value,)).lower() + bytes((value,)).upper() + b"]"
                                       for value in match.group(0)[1:])
            return re.sub(rb"%[0-9a-fA-F]{2}", hex_pair, re.escape(token))
        self.pattern = re.compile(b"|".join(encoded_pattern(token) for token in tokens)) if tokens else None
        self.keep = max(map(len, tokens), default=1) - 1
        self.pending = b""

    def feed(self, chunk: bytes, *, final: bool = False) -> bytes:
        if self.pattern is None:
            return chunk
        self.pending += chunk
        boundary = len(self.pending) if final else max(0, len(self.pending) - self.keep)
        for match in self.pattern.finditer(self.pending):
            if match.start() < boundary < match.end():
                boundary = match.end()
        ready, self.pending = self.pending[:boundary], self.pending[boundary:]
        return self.pattern.sub(b"[REDACTED]", ready)

    def text(self, value: str) -> str:
        return self.feed(value.encode(), final=True).decode(errors="replace")
