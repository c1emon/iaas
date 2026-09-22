"""Fixed single-provider roots, ephemeral credentials and explicit SSH trust."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from iaas_automation.common.errors import ValidationError, require
from .credentials import protected_file

AUTH = ('pve_api_username', 'pve_api_token_id', 'pve_api_token_secret')
SSH_AUTH = ('pve_ssh_username', 'pve_ssh_private_key')
TOKEN = '${var.pve_api_username}!${var.pve_api_token_id}=${var.pve_api_token_secret}'


def normalize_endpoint(value: Any) -> str:
    require(isinstance(value, str), 'PVE endpoint must be fixed')
    url = urlsplit(value)
    require(url.scheme == 'https' and url.hostname and not url.username and not url.password
            and url.path in {'', '/'} and not url.query and not url.fragment, 'invalid fixed PVE endpoint')
    host = f'[{url.hostname.lower()}]' if ':' in url.hostname else url.hostname.lower()
    return f'https://{host}:{url.port or 8006}'


def _labels(value: Any) -> list[tuple[str, dict]]:
    values = value if isinstance(value, list) else [value or {}]
    return [(name, block) for row in values for name, block in row.items()
            if not name.startswith('__') for block in (block if isinstance(block, list) else [block])]


def _blocks(value: Any) -> list[dict]:
    return value if isinstance(value, list) else [value] if isinstance(value, dict) else []


def _document(path: Path) -> dict:
    try:
        if path.name.endswith('.tf.json'):
            return json.loads(path.read_text())
        import hcl2
        from hcl2.utils import SerializationOptions
        return hcl2.loads(path.read_text(), serialization_options=SerializationOptions(
            strip_string_quotes=True, explicit_blocks=False, with_comments=False))
    except Exception:
        raise ValidationError('PVE root configuration cannot be parsed') from None


def _fixed(value: Any, variables: dict, target: Mapping) -> Any:
    for name, key in (('pve_endpoint', 'api_endpoint'), ('pve_insecure', 'insecure')):
        if value == '${var.' + name + '}':
            require(name in variables and not variables[name].get('ephemeral')
                    and not variables[name].get('sensitive'), 'target must use fixed non-sensitive input')
            return target[key]
    require(not isinstance(value, str) or '${' not in value, 'dynamic provider target is unsupported')
    return value


def validate_root(root: Path, target: Mapping[str, Any]) -> dict:
    rows, variables, sources = [], {}, []
    files = sorted(set(root.rglob('*.tf')) | set(root.rglob('*.tf.json')))
    for path in files:
        if '.terraform' in path.parts:
            continue
        document = _document(path)
        providers = _labels(document.get('provider'))
        require(not providers or path.parent == root, 'child module provider configuration is unsupported')
        if path.parent != root:
            continue
        rows.extend(providers)
        for name, var in _labels(document.get('variable')):
            require(name not in variables, 'duplicate root variable')
            variables[name] = var
        for block in _blocks(document.get('terraform')):
            for required in _blocks(block.get('required_providers')):
                sources.extend(required.items())
    require(len(rows) == 1 and rows[0][0] == 'proxmox', 'root must declare exactly one supported proxmox provider')
    require(len(sources) == 1 and sources[0][0] == 'proxmox'
            and sources[0][1].get('source') in {'bpg/proxmox', 'registry.opentofu.org/bpg/proxmox'},
            'root must use the supported bpg/proxmox provider')
    row = rows[0][1]
    require(set(row) <= {'endpoint', 'insecure', 'api_token', 'ssh'}, 'unsupported provider configuration or alias')
    require(row.get('api_token') == TOKEN, 'provider authentication must use supported ephemeral variables')
    ssh = _blocks(row.get('ssh'))
    require(len(ssh) <= 1, 'multiple provider SSH blocks are unsupported')
    for name in (*AUTH, *(SSH_AUTH if ssh else ())):
        definition = variables.get(name, {})
        require(definition.get('ephemeral') is True and definition.get('sensitive') is True
                and 'default' not in definition, 'provider authentication variables must be sensitive and ephemeral without defaults')
    endpoint = normalize_endpoint(_fixed(row.get('endpoint'), variables, target))
    insecure = _fixed(row.get('insecure', False), variables, target)
    require(endpoint == normalize_endpoint(target['api_endpoint']) and type(insecure) is bool
            and insecure == target['insecure'], 'root provider endpoint or TLS conflicts with target')
    nodes = []
    if ssh:
        config = ssh[0]
        require(set(config) <= {'agent', 'username', 'private_key', 'node'}
                and config.get('agent') is False
                and config.get('username') == '${var.pve_ssh_username}'
                and config.get('private_key') == '${var.pve_ssh_private_key}',
                'provider SSH requires explicit ephemeral key/user and agent=false')
        for node in _blocks(config.get('node')):
            require(set(node) <= {'name', 'address', 'port'}, 'unsupported provider SSH node field')
            name, address, port = node.get('name'), node.get('address'), node.get('port', 22)
            require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', name)
                    and isinstance(address, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', address)
                    and type(port) is int and 1 <= port <= 65535, 'provider SSH node must have fixed name/address/port')
            nodes.append({'name': name, 'host': address, 'port': port})
        require(nodes and len({n['name'] for n in nodes}) == len(nodes), 'provider SSH nodes must be explicit and unique')
    return {'provider': 'proxmox', 'api_endpoint': endpoint, 'insecure': insecure,
            'ssh_nodes': nodes, 'ssh_enabled': bool(ssh)}


def prepare_provider_environment(provider: Mapping, files: Mapping[str, Path], environ: dict[str, str]) -> None:
    environ['TF_VAR_pve_endpoint'] = provider['api_endpoint']
    environ['TF_VAR_pve_insecure'] = str(provider['insecure']).lower()
    require(all(environ.get('TF_VAR_' + name) for name in AUTH), 'PVE execution credentials missing')
    if provider['ssh_enabled']:
        require('ssh_key' in files and environ.get('TF_VAR_pve_ssh_username'), 'provider SSH requires explicit key and username')
        protected_file(files['ssh_key'])
        environ['TF_VAR_pve_ssh_private_key'] = files['ssh_key'].read_text()
    else:
        for name in SSH_AUTH:
            environ.pop('TF_VAR_' + name, None)


def _plan_constant(expression: Any, native: Mapping) -> Any:
    require(isinstance(expression, dict), 'native provider expression missing')
    if 'constant_value' in expression:
        return expression['constant_value']
    references = expression.get('references', [])
    require(len(references) == 1 and references[0] in {'var.pve_endpoint', 'var.pve_insecure'},
            'native provider target is dynamic')
    return native.get('variables', {}).get(references[0][4:], {}).get('value')


def validate_plan_provider(native: Mapping, provider: Mapping, target: Mapping) -> dict:
    rows = native.get('configuration', {}).get('provider_config', {})
    require(set(rows) == {'proxmox'}, 'native plan provider topology is unsupported')
    row = rows['proxmox']
    require(row.get('full_name') in {'registry.opentofu.org/bpg/proxmox', 'registry.terraform.io/bpg/proxmox'}
            and not row.get('alias'), 'native plan provider source or alias mismatch')
    expressions = row.get('expressions', {})
    endpoint = normalize_endpoint(_plan_constant(expressions.get('endpoint'), native))
    insecure = _plan_constant(expressions.get('insecure', {'constant_value': False}), native)
    require(endpoint == provider['api_endpoint'] == normalize_endpoint(target['api_endpoint'])
            and type(insecure) is bool and insecure == provider['insecure'] == target['insecure'],
            'native plan provider endpoint or TLS mismatch')
    return dict(provider)


def _nodes(value: Any) -> set[str]:
    result = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'node_name':
                require(isinstance(child, str) and child, 'unknown provider SSH node')
                result.add(child)
            else:
                result |= _nodes(child)
    elif isinstance(value, list):
        for child in value:
            result |= _nodes(child)
    return result


def _ssh_connect(host: str, port: int, user: str, files: Mapping[str, Path]) -> None:
    require('known_hosts' in files and 'ssh_key' in files, 'SSH trust and explicit private key are required')
    protected_file(files['known_hosts'], secret=False)
    protected_file(files['ssh_key'])
    import paramiko
    client = paramiko.SSHClient()
    try:
        client.load_host_keys(str(files['known_hosts']))
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        # Authenticate and verify host identity without executing a command.
        client.connect(host, port=port, username=user, key_filename=str(files['ssh_key']),
                       allow_agent=False, look_for_keys=False, timeout=15, auth_timeout=15, banner_timeout=15)
    except Exception:
        raise ValidationError('SSH identity or host trust could not be verified') from None
    finally:
        client.close()


def verify_helper_trust(target: Mapping, files: Mapping[str, Path]) -> None:
    _ssh_connect(target['ssh_host'], target.get('ssh_port', 22), target['ssh_user'], files)


def verify_ssh_trust(provider: Mapping, files: Mapping[str, Path], environ: Mapping,
                     *, state: Mapping | None = None, plan: Mapping | None = None,
                     declared_nodes: set[str] | None = None) -> None:
    if not provider['ssh_enabled']:
        return
    nodes = set(declared_nodes or ()) | _nodes(state or {})
    if plan:
        for resource in plan.get('resource_changes', []):
            change = resource.get('change', {})
            require(not change.get('after_unknown', {}).get('node_name'), 'unknown provider SSH node')
            nodes |= _nodes(change.get('before') or {}) | _nodes(change.get('after') or {})
    mapping = {node['name']: node for node in provider['ssh_nodes']}
    require(nodes <= set(mapping), 'provider SSH node has no explicit destination')
    user = environ.get('TF_VAR_pve_ssh_username')
    require(isinstance(user, str) and bool(user), 'provider SSH username missing')
    for node in provider['ssh_nodes']:
        _ssh_connect(node['host'], node['port'], user, files)
