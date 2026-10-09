"""Value-free public diagnostics reconstructed from a fixed catalog."""
from collections.abc import Mapping
import json
from pathlib import Path
import re
from typing import Any
from .errors import Diagnostic


MARKER = 'IAAS-DIAGNOSTIC '
MESSAGES = {
    'task_failed': 'Task failed.',
    'task_unreachable': 'Task could not reach its target.',
    'task_warning': 'Task reported warnings.',
    'protected_task_failed': 'Protected task failed; raw arguments and output remain private.',
    'protected_task_unreachable': 'Protected task could not reach its target.',
    'protected_warning': 'Protected task reported warnings; warning text remains private.',
    'authentication_failed': 'Authentication failed.',
    'permission_denied': 'Permission denied.',
    'http_failure': 'HTTP request failed.',
    'timeout': 'Operation timed out.',
    'connection_failed': 'Connection failed.',
    'api_validation_failed': 'API rejected a field value; unrecognized reason text is redacted.',
    'api_port_invalid': 'API requires a valid port number, port alias or continuous range.',
    'api_network_invalid': 'API requires a valid network segment or alias.',
    'api_gateway_invalid': 'API requires a gateway matching the network IP protocol.',
    'api_sequence_invalid': 'API requires a sequence between 1 and 999999.',
    'api_field_required': 'API requires a value for this field.',
    'process_failed': 'Child process failed; inspect the protected capture for details.',
    'process_start_failed': 'Child process could not start; inspect task setup and protected output.',
    'process_interrupted': 'Child process was interrupted; completion is unconfirmed.',
    'capture_incomplete': 'Protected output capture is incomplete; retain task storage.',
    'operation_failed': 'Operation failed; unrecognized exception text remains private.',
    'invalid_value': 'Input validation failed.',
    'opnsense_native_limit': 'Native OPNsense success does not independently prove internal completion or active state.',
    'activation_failed': 'Activation failed or is unconfirmed; dependent stages stopped.',
    'k3s_model_invalid': 'K3s validated model/node admission gate failed.',
    'registry_bearer_invalid': 'Registry authentication requires a same-authority HTTPS Bearer realm and credentials.',
    'credential_scope_missing': 'Declared endpoint access requires an action-scoped runtime credential.',
    'registry_tls_invalid': 'Registry TLS files must be regular and have restrictive permissions.',
    'switch_call_invalid': 'Switch resource calls must declare config and an allowed state.',
    'secret_channel_missing': 'An explicit resolvable protected runtime secret channel is required.',
    'k3s_tls_invalid': 'Declared K3s TLS files must be regular and have restrictive permissions.',
    'k3s_runtime_unhealthy': 'K3s runtime failed the post-restart health gate.',
    'artifact_selection_invalid': 'K3s artifact selection requires HTTPS, SHA-256 and its scoped credential.',
    'k3s_version_drift': 'Installed K3s version differs from reviewed observations; regenerate the plan.',
    'k3s_bootstrap_not_ready': 'Bootstrap API did not become ready; dependent joins stopped.',
    'k3s_token_mismatch': 'Bootstrap secure token does not match its protected external reference.',
    'k3s_ca_invalid': 'Authoritative K3s server CA must contain exactly one X.509 certificate.',
}
ASSERTION_CODES = {
    'k3s_server requires one validated embedded-etcd server model node': 'k3s_model_invalid',
    'k3s_agent requires one validated agent model node and endpoint': 'k3s_model_invalid',
    'k3s_runtime_config requires a validated composed model and node': 'k3s_model_invalid',
    'deployment requires validated whole scope and an explicit protected runtime secret path': 'k3s_model_invalid',
    'Registry authentication requires a same-authority HTTPS Bearer realm and credentials': 'registry_bearer_invalid',
    'declared artifact, registry, or proxy access requires its action-scoped runtime credential': 'credential_scope_missing',
    'a referenced registry TLS file must exist, be regular, and use restrictive permissions': 'registry_tls_invalid',
    'Each switch_config_resources entry must include state and config fields, and state must be included in switch_config_allowed_states.': 'switch_call_invalid',
    'authenticated baseline APT access requires a resolvable protected runtime secret': 'secret_channel_missing',
    'k3s_runtime_config requires an explicit protected runtime secret file': 'secret_channel_missing',
    'declared K3s TLS files must already exist as regular files with restrictive permissions': 'k3s_tls_invalid',
    'K3s runtime service failed the post-restart health gate': 'k3s_runtime_unhealthy',
    'K3s acquisition requires a caller-selected HTTPS URL, SHA-256, and an explicit protected runtime secret path when authentication is declared': 'artifact_selection_invalid',
    'actual K3s version differs from supplied observations; regenerate the upgrade plan': 'k3s_version_drift',
    'bootstrap server API did not become ready; dependent joins were not attempted': 'k3s_bootstrap_not_ready',
    'bootstrap secure token does not match the protected external token reference': 'k3s_token_mismatch',
    'authoritative K3s server CA must contain exactly one X.509 certificate': 'k3s_ca_invalid',
}
FIELDS = frozenset({'source_port', 'destination_port', 'local_port', 'source_net', 'destination_net',
    'interface', 'gateway', 'protocol', 'ipprotocol', 'sequence', 'action', 'direction', 'enabled',
    'quick', 'description', 'name', 'type', 'content', 'target', 'external', 'address', 'members',
    'statetype', 'replyto', 'source_not', 'destination_not', 'unknown_field', 'value', 'row',
    'selected', 'identity', 'references'})
ACTIONS = frozenset({'command', 'shell', 'uri', 'assert', 'fail', 'copy', 'template', 'set_fact',
    'service', 'systemd', 'systemd_service', 'get_url', 'fetch', 'slurp', 'stat', 'wait_for',
    'alias', 'alias_multi', 'rule', 'rule_multi', 'interface_vip', 'gateway', 'raw',
    'nat_destination', 'nat_one_to_one', 'rule_interface_group', 'protected_task'})
RESOURCES = frozenset({'aliases', 'vips', 'gateways', 'filter-rules', 'dnat', 'one-to-one-nat', 'interface-groups'})


def safe_diagnostic(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or not isinstance(value.get('code'), str) or value.get('code') not in MESSAGES:
        return None
    code = value['code']
    severity = 'warning' if code in {'task_warning', 'protected_warning', 'opnsense_native_limit'} else 'error'
    result: dict[str, Any] = {'code': code, 'severity': severity, 'message': MESSAGES[code]}
    for key, allowed in (('field', FIELDS), ('action', ACTIONS), ('resource', RESOURCES)):
        item = value.get(key)
        if isinstance(item, str) and item in allowed:
            result[key] = item
    for key, minimum, maximum in (('status_code', 100, 599), ('exit_code', 0, 255), ('warning_count', 1, 1000)):
        item = value.get(key)
        if type(item) is int and minimum <= item <= maximum:
            result[key] = item
    return result


def safe_diagnostics(values: Any) -> list[dict[str, Any]]:
    result = []
    if isinstance(values, list):
        for value in values[-256:]:
            entry = safe_diagnostic(value)
            if entry is not None and entry not in result:
                result.append(entry)
    return sorted(result, key=lambda entry: entry['severity'] != 'error')[:64]


def task_diagnostics(value: Any, action: str, *, protected: bool = True) -> list[dict[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    action = action.rsplit('.', 1)[-1]
    action = action if action in ACTIONS else 'protected_task'
    entries = []
    if value.get('failed') or value.get('failed_when_result') or value.get('unreachable'):
        entry = {'code': ('protected_task_unreachable' if protected else 'task_unreachable') if value.get('unreachable') else
                        ('protected_task_failed' if protected else 'task_failed'),
                 'action': action, 'exit_code': value.get('rc')}
        status = value.get('status')
        if type(status) is int and 400 <= status <= 599:
            entry.update(code='authentication_failed' if status == 401 else 'permission_denied' if status == 403 else 'http_failure',
                         status_code=status)
        entries.append(entry)
    warnings = value.get('warnings')
    if isinstance(warnings, list) and warnings:
        entries.append({'code': 'protected_warning' if protected else 'task_warning', 'action': action,
                        'warning_count': min(len(warnings), 1000)})
    return safe_diagnostics(entries)


def assertion_diagnostics(message: Any) -> list[dict[str, Any]]:
    if not isinstance(message, str) or message not in ASSERTION_CODES:
        return []
    return safe_diagnostics([{'code': ASSERTION_CODES[message], 'action': 'assert'}])


def capture_diagnostics(path: Path) -> list[dict[str, Any]]:
    """Read bounded head/tail windows; ignore arbitrary output and message text."""
    entries = []
    try:
        with path.open('rb') as stream:
            head = stream.read(262144)
            stream.seek(0, 2)
            size = stream.tell()
            tail = b''
            if size > len(head):
                stream.seek(max(len(head), size - 786432))
                tail = stream.read(786432)
        for line in (head + b'\n' + tail).splitlines():
            line = re.sub(rb'\x1b\[[0-9;]*m', b'', line)
            if line.startswith(MARKER.encode()) and len(line) <= 4096:
                try:
                    entries.append(json.loads(line[len(MARKER):]))
                except (ValueError, RecursionError):
                    continue
    except OSError:
        return []
    # Prefer the last diagnostics when a noisy task exceeds the public bound.
    return safe_diagnostics(entries)


def exception_diagnostics(error: BaseException) -> list[dict[str, Any]]:
    diagnostic = getattr(error, 'diagnostic', None)
    if isinstance(diagnostic, Diagnostic):
        value = diagnostic.to_dict()
        if isinstance(value, dict):
            code = diagnostic.code
            code = {
                'api_failure': 'http_failure', 'service_unavailable': 'connection_failed',
                'endpoint_unavailable': 'connection_failed', 'transport_failure': 'connection_failed',
                'observation_deadline_exhausted': 'timeout',
            }.get(code, code)
            entries = safe_diagnostics([{'code': code, 'status_code': value.get('status_code')}])
            if entries:
                return entries
    code = 'timeout' if isinstance(error, TimeoutError) else 'connection_failed' if isinstance(error, ConnectionError) else 'operation_failed'
    return safe_diagnostics([{'code': code}])
