"""Root parsing and trust tests; SSH transport is a local test double."""
import json
from copy import deepcopy

import pytest

from iaas.common.errors import ValidationError
from iaas.runtime_execution.pve_provider import (
    AUTH, SSH_AUTH, TOKEN, validate_root, prepare_provider_environment,
    validate_plan_provider, verify_ssh_trust,
)

TARGET = {'api_endpoint': 'https://api.invalid:8006', 'insecure': False}


def root_document(ssh=True):
    row = {'endpoint': '${var.pve_endpoint}', 'insecure': '${var.pve_insecure}', 'api_token': TOKEN}
    if ssh:
        row['ssh'] = {'agent': False, 'username': '${var.pve_ssh_username}', 'private_key': '${var.pve_ssh_private_key}',
                      'node': [{'name': 'n1', 'address': 'ssh.invalid', 'port': 2222}]}
    return {'terraform': {'required_providers': {'proxmox': {'source': 'bpg/proxmox', 'version': '0.111.0'}}},
            'provider': {'proxmox': row}, 'variable': {
                **{name: {'type': 'string', 'sensitive': True, 'ephemeral': True} for name in (*AUTH, *SSH_AUTH)},
                'pve_endpoint': {'type': 'string'}, 'pve_insecure': {'type': 'bool'}}}


def save(tmp_path, value):
    (tmp_path / 'main.tf.json').write_text(json.dumps(value))
    return validate_root(tmp_path, TARGET)


def native_plan():
    return {'configuration': {'provider_config': {'proxmox': {
        'full_name': 'registry.opentofu.org/bpg/proxmox', 'expressions': {
            'endpoint': {'references': ['var.pve_endpoint']}, 'insecure': {'references': ['var.pve_insecure']}}}}},
            'variables': {'pve_endpoint': {'value': TARGET['api_endpoint']}, 'pve_insecure': {'value': False}}}


def test_actual_json_root_and_native_target_agree(tmp_path):
    binding = save(tmp_path, root_document())
    assert binding['ssh_nodes'] == [{'name': 'n1', 'host': 'ssh.invalid', 'port': 2222}]
    native = native_plan()
    validate_plan_provider(native, binding, TARGET)
    native['variables']['pve_endpoint']['value'] = 'https://different.invalid:8006'
    with pytest.raises(ValidationError, match='mismatch'):
        validate_plan_provider(native, binding, TARGET)


def test_hcl_is_parsed_instead_of_regex_scanned(tmp_path):
    # HCL parsing accepts ordinary provider/module files and enforces the same
    # sensitive + ephemeral contract as the JSON spelling.
    (tmp_path / 'main.tf').write_text('''terraform { required_providers { proxmox = { source = "bpg/proxmox" } } }
provider "proxmox" { endpoint = "https://api.invalid:8006"
 insecure = false
 api_token = "${var.pve_api_username}!${var.pve_api_token_id}=${var.pve_api_token_secret}" }
''' + '\n'.join(f'variable "{name}" {{ type = string\n sensitive = true\n ephemeral = true }}' for name in AUTH))
    assert validate_root(tmp_path, TARGET)['ssh_enabled'] is False


@pytest.mark.parametrize('mutation', ['ordinary', 'alias', 'second', 'dynamic', 'agent', 'dynamic_node'])
def test_unsupported_roots_fail_before_native_commands(tmp_path, mutation):
    doc = root_document()
    if mutation == 'ordinary':
        doc['variable'][AUTH[-1]].pop('ephemeral')
    elif mutation == 'alias':
        doc['provider']['proxmox']['alias'] = 'other'
    elif mutation == 'second':
        doc['provider']['other'] = deepcopy(doc['provider']['proxmox'])
    elif mutation == 'dynamic':
        doc['provider']['proxmox']['endpoint'] = '${local.endpoint}'
    elif mutation == 'agent':
        doc['provider']['proxmox']['ssh']['agent'] = True
    else:
        doc['provider']['proxmox']['ssh']['node'][0]['address'] = '${local.host}'
    with pytest.raises(ValidationError):
        save(tmp_path, doc)


def test_credential_rotation_uses_current_key_without_changing_binding(tmp_path):
    provider = save(tmp_path, root_document())
    key = tmp_path / 'key'
    key.write_text('first-private-key')
    key.chmod(0o600)
    env = {'TF_VAR_' + name: 'synthetic' for name in AUTH}
    env['TF_VAR_pve_ssh_username'] = 'ops'
    prepare_provider_environment(provider, {'ssh_key': key}, env)
    assert env['TF_VAR_pve_ssh_private_key'] == 'first-private-key'
    key.write_text('new-private-key')
    prepare_provider_environment(provider, {'ssh_key': key}, env)
    assert env['TF_VAR_pve_ssh_private_key'] == 'new-private-key'
    assert provider == validate_root(tmp_path, TARGET)


def test_trust_uses_node_mapping_nondefault_port_and_no_host_agent(tmp_path, monkeypatch):
    import paramiko
    provider = save(tmp_path, root_document())
    key, hosts = tmp_path / 'key', tmp_path / 'hosts'
    for path in (key, hosts):
        path.write_text('synthetic-test-material')
        path.chmod(0o600)
    calls = []

    class SSH:
        def load_host_keys(self, path):
            assert path == str(hosts)
        def set_missing_host_key_policy(self, policy):
            assert isinstance(policy, paramiko.RejectPolicy)
        def connect(self, host, **options):
            calls.append((host, options))
        def close(self):
            pass

    monkeypatch.setattr(paramiko, 'SSHClient', SSH)
    verify_ssh_trust(provider, {'ssh_key': key, 'known_hosts': hosts}, {'TF_VAR_pve_ssh_username': 'ops'}, declared_nodes={'n1'})
    host, options = calls[0]
    assert host == 'ssh.invalid' and options['port'] == 2222
    assert options['allow_agent'] is False and options['look_for_keys'] is False
    with pytest.raises(ValidationError, match='explicit destination'):
        verify_ssh_trust(provider, {}, {}, state={'resources': [{'instances': [{'attributes': {'node_name': 'unknown'}}]}]})
    with pytest.raises(ValidationError, match='trust'):
        verify_ssh_trust(provider, {'ssh_key': key}, {'TF_VAR_pve_ssh_username': 'ops'})


def test_wrong_key_does_not_expose_authentication_diagnostics(tmp_path, monkeypatch):
    import paramiko
    provider = save(tmp_path, root_document())
    key = tmp_path / 'key'
    key.write_text('bad-key')
    key.chmod(0o600)

    class SSH:
        def load_host_keys(self, path): pass
        def set_missing_host_key_policy(self, policy): pass
        def connect(self, *a, **kw): raise RuntimeError('secret diagnostic')
        def close(self): pass

    monkeypatch.setattr(paramiko, 'SSHClient', SSH)
    with pytest.raises(ValidationError, match='could not be verified') as error:
        verify_ssh_trust(provider, {'ssh_key': key, 'known_hosts': key}, {'TF_VAR_pve_ssh_username': 'ops'})
    assert 'secret diagnostic' not in str(error.value)
