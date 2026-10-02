"""Acceptance check/plan bind reviewable inputs without consuming approval."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from iaas.pve_template import acceptance_plan as mod
from iaas.pve_template import runtime, acceptance_snippets
from iaas.runtime_execution.execution import Execution
from iaas.runtime_execution.outputs import TaskOutputs
from iaas.pve_template.admission import AdmissionError, admit_acceptance
from test_pve_placement_admission import API, Helpers


ROOT = Path(__file__).resolve().parents[2]


def request():
    return json.loads((ROOT / 'docs/examples/pve-acceptance/acceptance-request.json').read_text())


def test_offline_check_without_credentials_or_clients(tmp_path, monkeypatch):
    value = request()
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(value))
    selected = SimpleNamespace(options={'action': 'accept'}, files={'acceptance_request': path})
    monkeypatch.setattr(runtime, '_client', lambda *args: pytest.fail('check attempted API'))
    monkeypatch.setattr(acceptance_snippets, 'Snippets', lambda *args, **kwargs: pytest.fail('check attempted SSH'))
    outputs = TaskOutputs.create(tmp_path / 'check', ROOT, [path])
    mod.run_plan(selected, Execution(outputs, {}), 'check', value['runtime']['image_digest'])


def test_online_plan_is_get_only_and_has_no_consumption(tmp_path, monkeypatch):
    value = request()
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(value))
    selected = SimpleNamespace(options={'action': 'accept'}, files={'acceptance_request': path})
    api = API(value)
    monkeypatch.setattr(runtime, '_client', lambda *args: api)
    monkeypatch.setattr(acceptance_snippets, 'Snippets', lambda *args, **kwargs: Helpers())
    outputs = TaskOutputs.create(tmp_path / 'plan', ROOT, [path])
    mod.run_plan(selected, Execution(outputs, {}), 'plan', value['runtime']['image_digest'])
    preview = json.loads((tmp_path / 'plan/plan/acceptance-preview.json').read_text())
    assert mod.validate_preview(preview, request=value) == preview
    assert preview['facility_writes'] == 'none'
    assert preview['observed']['capacity']['total_required_bytes'] == 8 * 1024 ** 3 + 4 * 1024 ** 2
    assert all(method == 'GET' for method, _ in api.calls)
    assert not (tmp_path / 'plan/diagnostics/execution').exists()
    assert 'admission' not in preview and 'consumption' not in preview


@pytest.mark.parametrize('field', ['pool', 'range', 'runtime', 'deadline', 'digest'])
def test_preview_rejects_frozen_input_changes(field):
    value = request()
    preview = mod.build_preview(value, {'readiness': {'status': 'ready'}}, image_digest=value['runtime']['image_digest'])
    changed = deepcopy(preview)
    if field == 'pool': changed['fixed_input']['temporary_vm']['pool'] = 'other'
    if field == 'range': changed['fixed_input']['vmid_policy']['acceptance'][1] += 1
    if field == 'runtime': changed['runtime']['image_digest'] = 'sha256:' + 'f' * 64
    if field == 'deadline': changed['fixed_input']['deadlines']['work_deadline_at'] = '2098-01-01T00:00:00Z'
    if field == 'digest': changed['preview_digest'] = 'sha256:' + '0' * 64
    with pytest.raises(ValueError):
        mod.validate_preview(changed, request=value)


def test_auxiliary_firmware_disks_count_in_preclone_capacity():
    value = request()
    config = value['template_record']['configuration']
    config['efidisk0'] = 'local-lvm:vm-9000-disk-1,size=4M'
    config['tpmstate0'] = 'local-lvm:vm-9000-disk-2,size=4M'
    observed = admit_acceptance(API(value), value, helpers=Helpers())
    assert observed['capacity']['total_required_bytes'] == 8 * 1024 ** 3 + 12 * 1024 ** 2
    assert {disk['slot'] for disk in observed['capacity']['disks']} == {'scsi0', 'ide2', 'efidisk0', 'tpmstate0'}


def test_40gib_total_limit_is_not_increased_for_cloudinit():
    value = request()
    value['template_record']['configuration']['scsi0'] = 'local-lvm:vm-9000-disk-0,size=40G'
    value['temporary_vm']['disk_limit_bytes'] = 40 * 1024 ** 3
    api = API(value)
    with pytest.raises(AdmissionError, match='disk_limit_exceeded') as caught:
        admit_acceptance(api, value, helpers=Helpers())
    capacity = caught.value.diagnostic['capacity']
    assert capacity['total_required_bytes'] == 42_953_867_264
    assert capacity['disk_limit_bytes'] == 40 * 1024 ** 3
    assert all(method == 'GET' for method, _ in api.calls)
