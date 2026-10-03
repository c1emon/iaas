"""Representative current-contract software checks; no facility acceptance claim."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from iaas.common.errors import ValidationError
from iaas.image import runtime as image
from iaas.image.contracts import validate_build_request
from iaas.pve_template import runtime as pve
from iaas.pve_template.contracts import build_publish_preview, validate_publish_request
from iaas.runtime_config.compile import compile_documents
from iaas.runtime_config.loader import load_environment
from iaas.runtime_execution.execution import OperationFailed
from iaas.runtime_execution.__main__ import main

from test_image_execution import _execution, _request, _selected
from test_image_publish_contracts import request as publish_request
from test_pve_template_publisher import API, Outputs
from test_pve_template_acceptance import API as AcceptanceAPI, Snippets, request as acceptance_request, admission, DIGEST, begin
from iaas.pve_template.acceptance import Acceptance
from iaas.pve_acceptance_contracts import validate_acceptance_request

GIB = 1024 ** 3
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('capacity', [None, True, '8', 0, 7, 1025])
def test_build_capacity_is_explicit_and_bounded(capacity):
    request = _request()
    request['disk_size_gib'] = capacity
    with pytest.raises(ValidationError, match='disk_size_gib'):
        validate_build_request(request)


@pytest.mark.parametrize('upgrade', ['true', 1, None, {}])
def test_upgrade_requires_boolean(upgrade):
    request = _request()
    request['customization']['package_upgrade'] = upgrade
    with pytest.raises(ValidationError, match='package_upgrade'):
        validate_build_request(request)


def test_build_current_version_and_normalized_options():
    request = _request()
    request['customization']['package_upgrade'] = True
    normalized = validate_build_request(request)
    assert normalized['disk_size_gib'] == 8
    assert normalized['customization']['package_upgrade'] is True
    assert validate_build_request(_request())['customization']['package_upgrade'] is False
    request['schema_version'] = 1
    with pytest.raises(ValidationError, match='schema_version'):
        validate_build_request(request)


@pytest.mark.parametrize('base_size,final_size,upgrade_failure,success', [
    (3 * GIB, 8 * GIB, False, True),
    (9 * GIB, 8 * GIB, False, False),
    (3 * GIB, 40 * GIB, False, False),
    (3 * GIB, 8 * GIB, True, False),
])
def test_build_capacity_upgrade_and_failure_before_artifact(tmp_path, monkeypatch, base_size, final_size, upgrade_failure, success):
    execution = _execution(tmp_path)
    request = _request(firmware='bios', checks={'required': ['format', 'disk-size', 'self-contained'], 'optional': []})
    request['customization']['package_upgrade'] = True
    monkeypatch.setattr(image, '_executor_check', lambda resources: {
        'accelerator': 'kvm', 'supported_platform': True, 'supported_kvm': True, 'enough_disk': True})
    monkeypatch.setattr(image, '_memory_observation', lambda resources: {
        'status': 'unknown', 'requested_memory_mib': resources['memory_mib'], 'observations': []})
    monkeypatch.setattr(image, '_download_base', lambda request, path, resources, **kwargs: path.write_bytes(b'base'))
    monkeypatch.setattr(image, '_require_self_contained', lambda path, *args: {
        'format': 'qcow2', 'virtual-size': base_size if path.name == 'base.img' else final_size})
    monkeypatch.setattr(image, '_make_seed', lambda execution, directory, **kwargs: (directory / 'seed', directory / 'key'))
    monkeypatch.setattr(image.shutil, 'which', lambda tool: '/usr/bin/' + tool)
    calls = []

    def packer(execution, task, record, phase, command, cwd):
        calls.append(dict(execution.environ))
        if upgrade_failure:
            raise OperationFailed('packer-build package upgrade failed')
        output = task / 'packer-output'
        output.mkdir()
        (output / 'disk.qcow2').write_bytes(b'output')

    monkeypatch.setattr(image, '_run_tracked_tool', packer)
    monkeypatch.setattr(image, '_flatten_image', lambda execution, source, destination, cwd: destination.write_bytes(b'clean-disk'))
    monkeypatch.setattr(image, '_offline_cleanup', lambda *args: None)
    if success:
        image._build(_selected(request, execution_id='build-8g'), execution, 'build-8g')
    else:
        with pytest.raises(ValidationError):
            image._build(_selected(request, execution_id='build-8g'), execution, 'build-8g')
    task = execution.outputs.path('work') / 'image-tasks/build-8g'
    assert (task / 'artifact.json').exists() is success
    assert json.loads((task / 'task.json').read_text())['status'] == ('succeeded' if success else 'failed')
    if base_size > 8 * GIB:
        assert not calls
        assert not (task / 'build.key').exists()
    else:
        assert calls[0]['PKR_VAR_disk_size_gib'] == '8'
        assert calls[0]['PKR_VAR_package_upgrade'] == 'true'
    if success:
        artifact = json.loads((task / 'artifact.json').read_text())
        assert json.loads((task / 'task.json').read_text())['resources']['memory_observation']['status'] == 'unknown'
        assert artifact['disk']['virtual_size_bytes'] == 8 * GIB
        assert all(check['status'] == 'passed' for check in artifact['checks'])


def test_publish_no_nic_is_created_verified_and_recorded(tmp_path, monkeypatch):
    request = publish_request()
    request['hardware'].update(bridge=None, memory_mib=1024)
    request['vmid'] = 9001  # Synthetic API fixture identity.
    preview = build_publish_preview(request, runtime={'image_digest': 'runtime@sha256:' + 'a' * 64})
    api = API()
    outputs = Outputs(tmp_path / 'outputs')
    execution = SimpleNamespace(outputs=outputs, environ={'PVE_ARTIFACT_URL': request['source']['object_ref']})
    monkeypatch.setattr(pve, '_client', lambda *args: api)
    monkeypatch.setattr(pve, '_download', lambda locator, path, digest, size, **kwargs: path.write_bytes(b'disk'))
    monkeypatch.setattr(pve, '_verify_qcow2', lambda *args, **kwargs: None)
    result = pve._publish(SimpleNamespace(), execution, validate_publish_request(request), preview, 'no-nic')
    create = next(fields for method, path, fields in api.calls if method == 'POST' and path.endswith('/qemu'))
    assert 'net0' not in create
    assert result['publication'] == 'succeeded'
    assert not any(key.startswith('net') for key in result['template_record']['configuration'])
    assert result['template_record']['configuration']['memory'] == 1024
    config = dict(result['template_record']['configuration'], net7='virtio,bridge=vmbr0')
    with pytest.raises(ValidationError, match='no NIC'):
        pve._verify_requested_config(config, request)


@pytest.mark.parametrize('bridge', ['', False, {}, 0])
def test_publish_no_nic_requires_explicit_null(bridge):
    request = publish_request()
    request['hardware']['bridge'] = bridge
    with pytest.raises(ValidationError, match='bridge'):
        validate_publish_request(request)


def test_publish_rejects_no_nic_ip_and_firmware_conflicts():
    request = publish_request()
    request['hardware']['bridge'] = None
    request['cloud_init_defaults']['ip_config'] = 'ip=dhcp'
    with pytest.raises(ValidationError, match='ip_config'):
        validate_publish_request(request)
    request = publish_request()
    request['hardware']['firmware'] = 'uefi'
    with pytest.raises(ValidationError, match='firmware'):
        validate_publish_request(request)


def clone_documents():
    cluster = yaml.safe_load((ROOT / 'tests/fixtures/runtime/pve-cluster.yml').read_text())
    vms = yaml.safe_load((ROOT / 'tests/fixtures/runtime/vms.yml').read_text())
    cluster['templates']['synthetic'].update(vmid=9000, disk_size_gib=8, primary_nics=0)
    cluster['storage_roles']['disks']['datastore'] = 'memory'
    cluster['networks']['lab'].update(bridge='br_dev', cidr='10.10.0.0/24', gateway='10.10.0.254', dns='10.5.0.15')
    vm = vms['vms'][0]
    vm.update(pool='dev', resources={'cores': 8, 'memory_mib': 8192, 'root_disk_gib': 128})
    vm['nics'][0].update(static_ip='10.10.0.100/24', gateway='10.10.0.254', dns=['10.5.0.15'])
    return cluster, vms


def selected_clone(tmp_path, cluster, vms):
    for name, value in [('cluster', cluster), ('vms', vms)]:
        (tmp_path / f'{name}.yml').write_text(yaml.safe_dump(value))
    path = tmp_path / 'environment.yml'
    path.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {
        'pve': {'inputs': {'cluster': 'cluster.yml', 'vms': 'vms.yml'}}}}))
    return load_environment(path, 'pve')


def test_offline_clone_supports_zero_nic_template_and_requested_vm(tmp_path):
    cluster, vms = clone_documents()
    generated = json.loads(compile_documents(selected_clone(tmp_path, cluster, vms))['pve.tfvars.json'])
    vm = generated['vms'][0]
    assert vm['resources'] == {'cores': 8, 'memory_mib': 8192, 'root_disk_gib': 128}
    assert vm['pool'] == 'dev'
    assert vm['storage']['disk_datastore_id'] == 'memory'
    assert vm['nics'][0]['network']['bridge'] == 'br_dev'
    assert vm['nics'][0]['static_ip'] == '10.10.0.100/24'


@pytest.mark.parametrize('field,value,expected', [
    ('root_disk_gib', 7, 'root_disk_gib'), ('cores', True, 'cores'), ('cores', 129, 'cores'),
    ('disk_size', 128, 'disk_size'),
])
def test_offline_clone_errors_show_file_field_and_reason(tmp_path, field, value, expected):
    cluster, vms = clone_documents()
    vms['vms'][0]['resources'][field] = value
    with pytest.raises(ValidationError) as error:
        compile_documents(selected_clone(tmp_path, cluster, vms))
    assert 'vms.yml' in str(error.value)
    assert expected in str(error.value)


def test_public_check_reports_file_field_without_credentials_or_network(tmp_path, monkeypatch, capsys):
    request = _request()
    request['customization']['package_upgrade'] = 'PRIVATE-CREDENTIAL-VALUE'
    (tmp_path / 'build.json').write_text(json.dumps(request))
    entry = tmp_path / 'environment.yml'
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {
        'image': {'inputs': {'build': 'build.json'}, 'files': {'env': 'missing-secret.env'}}}}))
    monkeypatch.setattr(image, '_require_executor', lambda *args: pytest.fail('guest build during check'))
    monkeypatch.setattr(image, '_download_base', lambda *args: pytest.fail('network during check'))
    assert main(['--environment', str(entry), '--component', 'image', '--operation', 'check',
                 '--output', str(tmp_path / 'output')]) == 2
    public = capsys.readouterr().out
    assert 'build.json' in public and 'customization.package_upgrade' in public and 'boolean' in public
    assert 'PRIVATE-CREDENTIAL-VALUE' not in public


@pytest.mark.parametrize('bad', ['ip=dhcp,gw=10.10.0.254', 'ip=10.10.0.100/24,password=private', 'garbage', 'ip=dhcp,ip=dhcp'])
def test_publish_and_acceptance_check_reject_invalid_ip_parameters(bad):
    request = publish_request()
    request['cloud_init_defaults']['ip_config'] = bad
    with pytest.raises(ValidationError, match='ip_config'):
        validate_publish_request(request)
    value = acceptance_request()
    value['temporary_vm']['ip_config'] = bad
    with pytest.raises(ValueError):
        validate_acceptance_request(value)


@pytest.mark.parametrize('fault', ['', 'bad-growth', 'bad-dns', 'skip-resize'])
def test_bounded_general_clone_growth_network_and_cleanup(tmp_path, fault):
    value = acceptance_request()
    value['template_record']['configuration'].pop('net0', None)
    value['temporary_vm'].update(disk_size_gib=128, disk_limit_bytes=129 * GIB, nameservers=['10.5.0.15'],
                                 cpus=8, memory_mib=8192, bridge='br_dev', ip_config='ip=10.10.0.100/24,gw=10.10.0.254')
    value = validate_acceptance_request(value)

    class GeneralAPI(AcceptanceAPI):
        def request(self, method, path, fields=None, **kwargs):
            if path.endswith('/resize'):
                self.calls.append((method, path, fields, kwargs))
                if fault != 'skip-resize':
                    self.clone['scsi0'] = 'local-lvm:vm-9100-disk-0,size=128G'
                return self.task('resize')
            if path.endswith('/agent/exec'):
                self.calls.append((method, path, fields, kwargs))
                command = json.loads(kwargs['body'])['command']
                assert command[:2] == ['python3', '-c']
                assert 'shell=True' not in command[2]
                return {'pid': 123}
            if path.endswith('/agent/exec-status'):
                self.calls.append((method, path, fields, kwargs))
                facts = {'root_disk_bytes': 128 * GIB, 'root_partition_bytes': 127 * GIB,
                         'root_filesystem_bytes': 126 * GIB, 'addresses': ['10.10.0.100/24'],
                         'default_gateways': ['10.10.0.254'], 'nameservers': ['10.5.0.15'],
                         'machine_id_initialized': True, 'instance_id': 'fresh-clone-instance'}
                if fault == 'bad-growth':
                    facts['root_filesystem_bytes'] = 8 * GIB
                if fault == 'bad-dns':
                    facts['nameservers'] = ['10.0.2.3']
                cloud = {'status': 'done', 'extended_status': 'done', 'errors': [], 'recoverable_errors': {},
                         'boot_status_code': 'enabled-by-generator', 'general_template': facts}
                return {'exited': True, 'exitcode': 0, 'out-data': json.dumps(cloud)}
            return super().request(method, path, fields, **kwargs)

    api = GeneralAPI(value)
    baseline = copy.deepcopy(api.source)
    original = tmp_path / 'original'
    journal = begin(original, 'accept', value, admission(value), 'accept-001', DIGEST)
    from iaas.pve_template.deadlines import DeadlineBudget
    budget = DeadlineBudget(value['deadlines'])
    if fault:
        budget.limit('work', .3)
    result = Acceptance(api, value, journal, original, Snippets(), budget).execute()
    assert result['overall'] == ('passed' if not fault else 'failed' if fault == 'bad-dns' else 'unknown')
    assert api.source == baseline
    assert api.clone is None and api.volumes == []
    assert all(row['status'] in {'passed', 'not_required'} for row in result['cleanup'].values())
    assert result['capacity']['total_required_bytes'] == 128 * GIB + 4 * 1024 ** 2
    clone = next(fields for method, path, fields, kwargs in api.calls if path.endswith('/clone'))
    assert clone['full'] == 1 and clone['pool'] == value['temporary_vm']['pool']
    if fault != 'skip-resize':
        resize = next(i for i, call in enumerate(api.calls) if call[1].endswith('/resize'))
        configure = next(i for i, call in enumerate(api.calls) if call[0] == 'PUT' and call[1].endswith('/config'))
        start = next(i for i, call in enumerate(api.calls) if call[1].endswith('/status/start'))
        assert resize < configure < start
        assert api.calls[configure][2]['nameserver'] == '10.5.0.15'


def test_growth_preflight_rejects_total_limit_without_mutations():
    from iaas.pve_template.admission import admit_acceptance, AdmissionError
    value = acceptance_request()
    value['temporary_vm'].update(disk_size_gib=128, disk_limit_bytes=128 * GIB + 1)
    value = validate_acceptance_request(value)
    api = AcceptanceAPI(value)
    with pytest.raises(AdmissionError, match='disk_limit_exceeded'):
        admit_acceptance(api, value, helpers=Snippets())
    assert not any(method != 'GET' for method, *_ in api.calls)
