"""Task-local PVE trust: system roots augmented by a caller PEM CA bundle."""

from __future__ import annotations

import ssl
from pathlib import Path

from .errors import ValidationError


CA_PREPARATION_FAILED = "PVE API CA preparation failed"


def _private_ca(ca_file: str | Path) -> str:
    """Validate caller material independently so public roots cannot mask it."""
    try:
        pem = Path(ca_file).read_text(encoding="ascii")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=pem)
        return pem
    except (OSError, ValueError, UnicodeError):
        raise ValidationError(CA_PREPARATION_FAILED) from None


def ssl_context(insecure: bool, ca_file: str | Path | None = None) -> ssl.SSLContext:
    """Use verified system trust plus optional CA, or explicit insecure mode."""
    if insecure:
        return ssl._create_unverified_context()
    pem = _private_ca(ca_file) if ca_file else None
    context = ssl.create_default_context()
    if pem is not None:
        context.load_verify_locations(cadata=pem)
    return context


def write_ca_bundle(ca_file: str | Path, destination: Path) -> Path:
    """Write a derived public plus private bundle for file-based TLS clients."""
    pem = _private_ca(ca_file)
    try:
        public = "".join(ssl.DER_cert_to_PEM_cert(cert)
                         for cert in ssl.create_default_context().get_ca_certs(binary_form=True))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(public + "\n" + pem + "\n", encoding="ascii")
    except (OSError, ValueError, UnicodeError):
        raise ValidationError(CA_PREPARATION_FAILED) from None
    return destination
