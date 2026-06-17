"""Secret-related helpers kept separate from the main render path."""

from __future__ import annotations

from importlib import import_module

from .errors import ValidationError


def hash_cloud_init_password(password: str) -> str:
    """Hash a plaintext password for cloud-init use at runtime."""
    try:
        sha512_crypt = import_module("passlib.hash").sha512_crypt
    except Exception as exc:  # pragma: no cover
        raise ValidationError("passlib is required for cloud-init password hashing") from exc
    return sha512_crypt.hash(password)
