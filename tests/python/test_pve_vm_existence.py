"""VM absence is a permission-complete inventory fact, not a config HTTP code."""
from types import SimpleNamespace

import pytest
from proxmoxer import ResourceException

from iaas_automation.common.errors import ValidationError
from iaas_automation.pve_inventory.pve_api import ReadOnlyPveApi, PveApiRuntimeConfig, PveApiUnavailableError
from iaas_automation.runtime_execution.plans import _check_resource_conflicts, _check_declared_conflicts
from iaas_automation.runtime_execution.pve_results import observed_vmids, verify_configuration, VM_TYPE


def api_for(rows, grants=None, calls=None):
    calls = calls if calls is not None else []
    def permissions(**kwargs):
        calls.append(("permissions", kwargs))
        return {kwargs["path"]: {"VM.Audit": 0} if grants is None else grants}
    def config():
        raise ResourceException(500, "configuration file does not exist", "missing config")
    prox = SimpleNamespace(
        access=SimpleNamespace(permissions=SimpleNamespace(get=permissions)),
        cluster=SimpleNamespace(resources=SimpleNamespace(get=lambda **_: rows)),
        nodes=lambda _: SimpleNamespace(
            status=SimpleNamespace(get=lambda: {"status": "online"}),
            qemu=lambda _: SimpleNamespace(config=SimpleNamespace(get=config))))
    return ReadOnlyPveApi(PveApiRuntimeConfig("https://pve.invalid", "user@pve", "token", "secret", False), prox=prox)


def deletion(api):
    return verify_configuration([{"kind": "vm", "node": "n1", "vmid": 101, "absent": True,
                                  "snapshot_complete": True, "state_absent": True}], api)


def creation(api):
    _check_resource_conflicts([{"type": VM_TYPE, "change": {
        "actions": ["create"], "after": {"node_name": "n1", "vm_id": 101}}}], None, api)
    _check_declared_conflicts([{"vmid": 101}], None, api)


def test_missing_config_500_is_not_used_for_absence_and_remains_api_error():
    calls = []
    api = api_for([], calls=calls)
    with pytest.raises(PveApiUnavailableError):
        api.vm_config("n1", 101)
    creation(api)
    assert deletion(api)["status"] == "passed"
    assert all(call == ("permissions", {"path": "/vms/101"}) for call in calls)


@pytest.mark.parametrize("kind,node", [("qemu", "n1"), ("qemu", "other"), ("lxc", "other")])
def test_cluster_wide_vmid_occupancy_blocks_create_and_delete(kind, node):
    api = api_for([{"vmid": 101, "node": node, "type": kind}])
    with pytest.raises(ValidationError, match="occupied"):
        creation(api)
    assert deletion(api)["status"] == "failed"


@pytest.mark.parametrize("grants", [{}, {"VM.Audit": None}, {"VM.Audit": "1"}, {"VM.Audit": 2}])
def test_filtered_empty_inventory_cannot_establish_absence(grants):
    api = api_for([], grants)
    with pytest.raises(ValidationError, match="VM.Audit"):
        creation(api)
    assert deletion(api)["status"] == "unknown"


@pytest.mark.parametrize("rows", [None, {}, [{}], [{"vmid": "101", "node": "n1", "type": "qemu"}],
    [{"vmid": 101, "node": "n1", "type": "qemu"}] * 2])
def test_incomplete_or_duplicate_inventory_fails_closed(rows):
    api = api_for(rows)
    with pytest.raises(ValidationError):
        observed_vmids(api, {101})
    assert deletion(api)["status"] == "unknown"


def test_permission_and_inventory_failures_never_prove_absence():
    for method in ("effective_permissions", "cluster_vm_resources"):
        api = api_for([])
        def fail(*_):
            raise PveApiUnavailableError("unavailable", status_code=500)
        setattr(api, method, fail)
        with pytest.raises(PveApiUnavailableError):
            creation(api)
        assert deletion(api)["status"] == "unknown"
