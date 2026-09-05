"""Fail-closed runtime secret channel for K3s online workflows.

The channel accepts one explicit, permission-restricted JSON file whose keys are
the external references from the composed K3s model.  It deliberately exposes
metadata publicly and passes a resolved value only to a caller-supplied,
action-scoped consumer.  Consumer return values are discarded so a secret
cannot escape through this API.
"""

from __future__ import annotations

import json
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

from iaas_automation.common.errors import ValidationError, require

_SOURCE = "protected_environment_json"
_REDACTED = "<redacted>"


def validate_external_secret_ref(value: Any) -> str:
    """Validate and return an external ``op://`` reference.

    Error messages intentionally contain only the field context, never the
    candidate value.  This helper is shared by the loader and channel lookup.
    """

    require(
        isinstance(value, str) and bool(value),
        "secret reference must be a non-empty string",
    )
    require(
        not any(character.isspace() for character in value),
        "secret reference must not contain whitespace",
    )
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError(
            "secret reference must be a valid op:// external reference"
        ) from exc

    path_parts = parsed.path.removeprefix("/").split("/")
    valid = (
        parsed.scheme == "op"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and port is None
        and parsed.path.startswith("/")
        and len(path_parts) in {2, 3}
        and all(path_parts)
        and not parsed.query
        and not parsed.fragment
    )
    require(valid, "secret reference must be a valid op:// external reference")
    return value


@dataclass(frozen=True)
class SecretMetadata:
    """Non-sensitive identity returned after a reference is resolved."""

    reference: str
    source: str = _SOURCE
    status: str = "resolved"

    def as_dict(self) -> dict[str, str]:
        """Return a safe representation suitable for logs and task results."""

        return {
            "reference": self.reference,
            "source": self.source,
            "status": self.status,
        }


class ProtectedSecretChannel:
    """Resolve external references from one protected JSON environment.

    Values remain private to the channel and are available only as the
    argument to :meth:`consume`.  The method returns metadata, never the
    consumer's return value or the resolved value itself.
    """

    __slots__ = ("_values", "_source")

    def __init__(self, values: Mapping[str, str]) -> None:
        normalized: dict[str, str] = {}
        for reference, value in values.items():
            validate_external_secret_ref(reference)
            require(
                isinstance(value, str) and bool(value.strip()),
                "protected secret values must be non-empty strings",
            )
            normalized[reference] = value
        require(
            bool(normalized),
            "protected environment JSON must contain at least one secret reference",
        )
        self._values = MappingProxyType(normalized)
        self._source = _SOURCE

    def __repr__(self) -> str:
        return f"{type(self).__name__}(references={len(self._values)}, source={self._source!r})"

    def resolve(self, reference: Any) -> SecretMetadata:
        """Check that a reference is present and return redacted metadata."""

        normalized = validate_external_secret_ref(reference)
        require(
            normalized in self._values, "required runtime secret reference is missing"
        )
        return SecretMetadata(reference=normalized, source=self._source)

    def consume(self, reference: Any, consumer: Callable[[str], Any]) -> SecretMetadata:
        """Pass one secret to a consumer and discard every consumer result.

        A consumer exception is converted to a context-only validation error so
        a secret embedded in its exception text cannot reach ordinary output.
        """

        require(callable(consumer), "secret consumer must be callable")
        metadata = self.resolve(reference)
        value = self._values[metadata.reference]
        try:
            consumer(value)
        except Exception:
            raise ValidationError("protected secret consumer failed") from None
        finally:
            # Do not retain a local reference beyond this operation.  Python
            # cannot guarantee immediate memory wiping, but the channel never
            # persists a second copy or exposes it through a return value.
            del value
        return metadata

    # Explicit aliases make the boundary readable at call sites without
    # introducing separate resolution paths.
    metadata = resolve
    use = consume


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValidationError("protected environment JSON is invalid") from exc
    except OSError as exc:
        raise ValidationError("unable to read protected environment JSON") from exc
    require(isinstance(document, dict), "protected environment JSON must be an object")
    return document


def load_protected_environment_json(path: Path) -> ProtectedSecretChannel:
    """Load a permission-restricted JSON mapping of ``op://`` refs to values.

    The path must be an explicit regular file and may not be a symlink.  Group
    and other permissions are refused so this loader cannot silently consume a
    normal generated/exported environment file.
    """

    require(
        isinstance(path, Path), "protected environment JSON path must be a pathlib.Path"
    )
    try:
        if path.is_symlink() or not path.is_file():
            raise ValidationError("protected environment JSON must be a regular file")
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        raise ValidationError("unable to inspect protected environment JSON") from exc
    require(
        mode & 0o077 == 0 and mode & stat.S_IRUSR,
        "protected environment JSON requires restrictive permissions",
    )

    document = _load_json(path)
    return ProtectedSecretChannel(document)


def redact_runtime_text(text: Any, secrets: list[str] | tuple[str, ...] = ()) -> str:
    """Replace known runtime values before text enters ordinary output."""

    result = str(text)
    for secret in secrets:
        if isinstance(secret, str) and secret:
            result = result.replace(secret, _REDACTED)
    return result


# Name the class as a runtime channel too; both names describe the same strict
# contract and keep consumers from reaching for an unprotected resolver.
RuntimeSecretChannel = ProtectedSecretChannel
load_runtime_secret_channel = load_protected_environment_json


__all__ = [
    "ProtectedSecretChannel",
    "RuntimeSecretChannel",
    "SecretMetadata",
    "load_protected_environment_json",
    "load_runtime_secret_channel",
    "redact_runtime_text",
    "validate_external_secret_ref",
]
