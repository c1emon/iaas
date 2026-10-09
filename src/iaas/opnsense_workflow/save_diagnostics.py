"""Extract bounded validation evidence without exporting provider text or values."""
import ast
from collections.abc import Mapping
import re
from typing import Any
from iaas.common.public_diagnostics import safe_diagnostics


FIELDS = frozenset({
    'source_port', 'destination_port', 'local_port', 'source_net', 'destination_net',
    'interface', 'gateway', 'protocol', 'ipprotocol', 'sequence', 'action', 'direction',
    'enabled', 'quick', 'description', 'name', 'type', 'content', 'target', 'external',
    'address', 'members', 'statetype', 'replyto', 'source_not', 'destination_not',
})
# Only exact static model messages are safe to retain. Unknown messages may
# echo secrets or raw configuration and must never be copied into results.
REASONS = frozenset({
    'Please specify a valid portnumber, name, alias or range.',
    'Please specify a valid network segment or alias.',
    'Specify a valid gateway from the list matching the networks ip protocol.',
    'Sequence shall be between 1 and 999999.',
    'This field is required.', 'A value is required.',
    'Please select a valid item.', 'Please specify a valid number.',
})
REDACTED_REASON = 'unrecognized API validation reason (redacted)'
REASON_CODES = {
    'Please specify a valid portnumber, name, alias or range.': 'api_port_invalid',
    'Please specify a valid network segment or alias.': 'api_network_invalid',
    'Specify a valid gateway from the list matching the networks ip protocol.': 'api_gateway_invalid',
    'Sequence shall be between 1 and 999999.': 'api_sequence_invalid',
    'This field is required.': 'api_field_required', 'A value is required.': 'api_field_required',
}


def public_failure_diagnostics(failure: Any, resource: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(failure, Mapping):
        return []
    entries = []
    details = failure.get('validation_details')
    if isinstance(details, list):
        for detail in details[:64]:
            if isinstance(detail, Mapping):
                reason = detail.get('reason')
                entries.append({'code': REASON_CODES.get(reason, 'api_validation_failed') if isinstance(reason, str) else 'api_validation_failed',
                                'field': detail.get('field'), 'resource': resource})
    codes = failure.get('http_status_codes')
    if isinstance(codes, list):
        for code in codes[:16]:
            if isinstance(code, str) and re.fullmatch(r'[45][0-9]{2}', code):
                entries.append({'code': 'authentication_failed' if code == '401' else 'permission_denied' if code == '403' else 'http_failure',
                                'status_code': int(code), 'resource': resource})
    for flag, code in (('timeout_reported', 'timeout'), ('write_denied_reported', 'permission_denied'),
                       ('connection_error_reported', 'connection_failed')):
        if failure.get(flag) is True:
            entries.append({'code': code, 'resource': resource})
    return safe_diagnostics(entries)


def safe_failure(failure: Mapping[str, Any]) -> dict[str, Any]:
    details = failure.get('validation_details', [])
    sanitized = []
    if isinstance(details, list):
        for entry in details[:64]:
            if isinstance(entry, Mapping):
                sanitized.extend(safe_validations({entry.get('field'): entry.get('reason')}))
    codes = failure.get('http_status_codes')
    result = {
        'validation_details': sanitized,
        **{field: failure[field] for field in (
            'timeout_reported', 'connection_error_reported', 'validation_reported',
            'write_denied_reported', 'api_failure_reported', 'response_present') if type(failure.get(field)) is bool},
        'http_status_codes': [code for code in codes[:16] if isinstance(code, str)
                              and re.fullmatch(r'[1-5][0-9]{2}', code)] if isinstance(codes, list) else [],
    }
    status = failure.get('response_status_class')
    if isinstance(status, str) and status in {'missing', 'ok', 'ok_with_whitespace', 'other'}:
        result['response_status_class'] = status
    return result


def safe_validations(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Mapping):
        return []
    result = []
    for key, reason in list(value.items())[:64]:
        leaf = key.rsplit('.', 1)[-1] if isinstance(key, str) else ''
        field = leaf if leaf in FIELDS else 'unknown_field'
        reasons = reason if isinstance(reason, list) else [reason]
        for message in reasons[:8]:
            entry = {'field': field,
                     'reason': message if isinstance(message, str) and message in REASONS else REDACTED_REASON}
            if entry not in result:
                result.append(entry)
    return result


def validation_details(failure: Any) -> list[dict[str, str]]:
    """Parse only validations / Collection's Error segment, never Response."""
    if not isinstance(failure, Mapping):
        return []
    calls = [failure]
    children = failure.get('results')
    if isinstance(children, list):
        calls.extend(row for row in children[:64] if isinstance(row, Mapping) and row.get('failed'))
    details = []
    for call in calls:
        evidence = safe_validations(call.get('validations'))
        message = call.get('msg')
        if isinstance(message, str) and len(message) <= 65536:
            match = re.search(r'API call failed \| Error: (.*?) \| Response:', message, re.DOTALL)
            if match:
                try:
                    evidence.extend(safe_validations(ast.literal_eval(match[1])))
                except (ValueError, SyntaxError, RecursionError, MemoryError):
                    pass
        for entry in evidence:
            if entry not in details:
                details.append(entry)
    return details
