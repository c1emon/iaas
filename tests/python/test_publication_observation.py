import hashlib
import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from iaas.observation import EvidenceSink, ObservationBudget
from iaas.pve_template import runtime
from test_pve_template_publisher import API
from test_pve_template_publication_failures import publish_setup


def test_publication_converges_after_import_content_and_template_flag(tmp_path, monkeypatch):
    class Lagged(API):
        def __init__(self):
            super().__init__()
            self.content_lag = True
            self.flag_lag = True

        def request(self, method, path, **kwargs):
            value = super().request(method, path, **kwargs)
            if method == 'GET' and path.endswith('/content') and 'scsi0' in self.config and self.content_lag:
                self.content_lag = False
                return []
            if method == 'GET' and path.endswith('/config') and self.config.get('template') == 1 and self.flag_lag:
                self.flag_lag = False
                return {**value, 'template': 0}
            return value
    api = Lagged()
    request, preview, execution = publish_setup(tmp_path, monkeypatch, api)
    result = runtime._publish(SimpleNamespace(), execution, request, preview, 'publish-1')
    assert result['publication'] == 'succeeded'
    assert len([c for c in api.calls if c[0] == 'UPLOAD']) == 1
    assert len([c for c in api.calls if c[0] == 'POST' and c[1].endswith('/config')]) == 1
    assert len([c for c in api.calls if c[0] == 'POST' and c[1].endswith('/template')]) == 1
    assert result['stop_diagnostics']['existence'] == 'present'


def test_foreign_volume_owner_stops_before_template_with_frozen_facts(tmp_path, monkeypatch):
    class Foreign(API):
        def request(self, method, path, **kwargs):
            value = super().request(method, path, **kwargs)
            if method == 'GET' and path.endswith('/content'):
                return [{**row, 'vmid': 888} for row in value]
            return value
    api = Foreign()
    request, preview, execution = publish_setup(tmp_path, monkeypatch, api)
    with pytest.raises(runtime.OperationFailed, match='volume_owner_conflict'):
        runtime._publish(SimpleNamespace(), execution, request, preview, 'publish-1')
    assert not any(c[0] == 'POST' and c[1].endswith('/template') for c in api.calls)
    intent = json.loads((execution.outputs.path('diagnostics') / 'publish-intent.json').read_text())
    result = runtime._failure_result(intent, 'publish-1', preview['preview_digest'], request['artifact_digest'])
    assert result['status'] == 'unknown'
    stop = result['stop_diagnostics']
    assert stop['stopping']['status'] == 'failed'
    evidence = next(g for g in stop['observations'] if g['check'] == 'volume-capacity')['terminal']['evidence']
    assert evidence['actual'][0]['vmid'] == 888
    assert evidence['actual'][0]['volid'] == 'images:vm-9001-disk-0'


def test_expired_bound_client_issues_neither_query_nor_write():
    clock = {'now': 0}
    budget = ObservationBudget(1, utc=lambda: clock['now'], monotonic=lambda: clock['now'])
    api = API()
    client = runtime._BoundClient(api, budget, EvidenceSink())
    clock['now'] = 2
    for method in ['GET', 'POST', 'DELETE']:
        with pytest.raises(Exception):
            client.request(method, '/api2/json/never')
    assert api.calls == []


def test_fixed_download_retries_503_once_and_does_not_record_locator(tmp_path, monkeypatch):
    data = b'fixed-image'
    calls = []
    def open_request(request, **kwargs):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise HTTPError(request.full_url, 503, 'busy', {}, None)
        return io.BytesIO(data)
    monkeypatch.setattr(runtime, 'build_opener', lambda *args: SimpleNamespace(open=open_request))
    sink = EvidenceSink()
    destination = tmp_path / 'disk.qcow2'
    runtime._download('https://objects.invalid/image?token=private', destination,
                      hashlib.sha256(data).hexdigest(), len(data), budget=ObservationBudget(2), sink=sink)
    assert destination.read_bytes() == data
    assert len(calls) == 2 and calls[0] == calls[1]
    assert 'private' not in json.dumps(sink.rows())


def test_publication_failure_exports_consumable_stop_summary(tmp_path, monkeypatch):
    class Foreign(API):
        def request(self, method, path, **kwargs):
            value = super().request(method, path, **kwargs)
            return [{**row, 'vmid': 888} for row in value] if method == 'GET' and path.endswith('/content') else value
    request, preview, execution = publish_setup(tmp_path, monkeypatch, Foreign())
    preview_path = tmp_path / 'preview.json'
    preview_path.write_text(json.dumps(preview))
    summaries = []
    execution.outputs.summary = summaries.append
    admission = {'schema_version': 1, 'execution_id': 'publish-1',
                 'plan_digest': preview['preview_digest'].removeprefix('sha256:'),
                 'target': request['target'], 'approved': True, 'deadlines': request['deadlines'],
                 'consumption': {'reserved': True, 'reservation_id': 'r-1'},
                 'pending': {'record_id': 'p-1'}, 'serialization': {'held': True, 'context_id': 's-1'},
                 'vmid_reservation': {'cluster_scope': request['cluster_scope'], 'vmids': [9001],
                                     'reservation_id': 'r-1', 'context_id': 's-1'}}
    selected = SimpleNamespace(options={'action': 'publish', 'preview_digest': preview['preview_digest'],
                                        'admission': admission}, files={'preview': preview_path})
    with pytest.raises(runtime.OperationFailed, match='volume_owner_conflict'):
        runtime.run(selected, 'apply', 'cohe', execution, preview['runtime']['image_digest'], 'publish-1')
    assert summaries[-1]['overall'] == 'unknown'
    assert summaries[-1]['stop_diagnostics']['stopping']['status'] == 'failed'
