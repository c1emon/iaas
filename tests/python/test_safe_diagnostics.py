"""Fast offline contract tests for safe structured diagnostics."""

from dataclasses import FrozenInstanceError

import pytest

from iaas.common.conversion import ConversionError
from iaas.common.errors import Diagnostic, ValidationError
from iaas.http_transport import TransportFailure
from iaas.pve_inventory.pve_api import (
    PveApiAuthenticationError,
    PveApiError,
    PveApiNotConfiguredError,
    PveApiUnavailableError,
)


pytestmark = pytest.mark.fast


def test_diagnostic_exports_only_approved_fields_and_is_immutable() -> None:
    diagnostic = Diagnostic(
        component="validation",
        code="invalid_value",
        field_path=("row", 0, "value"),
        status_code=422,
    )

    exported = diagnostic.to_dict()
    assert set(exported) == {"component", "code", "field_path", "status_code"}
    assert exported["component"] == "validation"
    assert exported["code"] == "invalid_value"
    assert tuple(exported["field_path"]) == ("row", 0, "value")
    assert exported["status_code"] == 422
    with pytest.raises(FrozenInstanceError):
        diagnostic.code = "backend_payload"  # type: ignore[misc]


@pytest.mark.parametrize("component", ["backend", "", "validation "])
def test_diagnostic_rejects_uncontrolled_components(component: str) -> None:
    with pytest.raises(ValueError):
        Diagnostic(component=component, code="invalid_value")


@pytest.mark.parametrize(
    "field_path",
    [("token",), ("row", -1), ("row", True), ("row", 1.5), ("row", None)],
)
def test_diagnostic_rejects_dynamic_or_invalid_field_paths(field_path: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        Diagnostic(component="validation", code="invalid_value", field_path=field_path)


@pytest.mark.parametrize("status_code", [99, 600, -1, True, False])
def test_diagnostic_rejects_invalid_status_codes(status_code: object) -> None:
    with pytest.raises(ValueError):
        Diagnostic(component="http_transport", code="http_failure", status_code=status_code)


@pytest.mark.parametrize("status_code", [100, 599])
def test_diagnostic_accepts_inclusive_status_bounds(status_code: int) -> None:
    assert Diagnostic(
        component="http_transport", code="http_failure", status_code=status_code
    ).to_dict()["status_code"] == status_code


def test_validation_error_keeps_message_args_and_adds_diagnostic() -> None:
    diagnostic = Diagnostic(component="validation", code="invalid_value", field_path=("value",))
    error = ValidationError("invalid declaration", diagnostic=diagnostic)

    assert str(error) == "invalid declaration"
    assert error.args == ("invalid declaration",)
    assert error.diagnostic is diagnostic
    exported = error.diagnostic.to_dict()
    assert exported["component"] == "validation"
    assert exported["code"] == "invalid_value"
    assert tuple(exported["field_path"]) == ("value",)


def test_conversion_and_transport_failures_attach_safe_diagnostics() -> None:
    conversion = ConversionError("invalid_boolean")
    transport = TransportFailure("http_failure", 503)

    assert conversion.diagnostic.to_dict() == {
        "component": "conversion",
        "code": "invalid_boolean",
        "field_path": ["value"],
    }
    assert transport.reason == "http_failure"
    assert transport.status_code == 503
    assert transport.diagnostic.to_dict() == {
        "component": "http_transport",
        "code": "http_failure",
        "status_code": 503,
    }


@pytest.mark.parametrize(
    "error_type, code",
    [
        (PveApiError, "api_failure"),
        (PveApiAuthenticationError, "authentication_failed"),
        (PveApiNotConfiguredError, "endpoint_unavailable"),
        (PveApiUnavailableError, "service_unavailable"),
    ],
)
def test_pve_errors_keep_inheritance_message_status_and_safe_diagnostic(
    error_type: type[PveApiError], code: str
) -> None:
    secret = "token=synthetic-secret"
    error = error_type(secret, status_code=503)

    assert isinstance(error, PveApiError)
    assert str(error) == secret
    assert error.status_code == 503
    assert error.diagnostic.to_dict() == {
        "component": "pve_api",
        "code": code,
        "status_code": 503,
    }
    assert secret not in repr(error.diagnostic.to_dict())


def test_validation_cli_with_diagnostic_keeps_existing_output(capsys) -> None:
    from iaas.common.cli import run_validation_cli

    def invalid(_argv):
        raise ValidationError('bad input', diagnostic=Diagnostic('validation', 'invalid_value'))

    assert run_validation_cli(invalid, []) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == 'FAIL validation: bad input\n'


def test_uncontrolled_code_cannot_include_backend_text() -> None:
    with pytest.raises(ValueError) as caught:
        Diagnostic('validation', 'backend-token-private')
    assert 'backend-token-private' not in str(caught.value)
