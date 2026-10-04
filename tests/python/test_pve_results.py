from copy import deepcopy

import pytest

from iaas.common.errors import ValidationError
from iaas.runtime_execution.pve_results import machine_review, expectations, verify_configuration
from iaas.pve_inventory.pve_api import PveApiNotConfiguredError


def change(actions=None, vmid=101):
    return {"address": 'module.vm["private-key"].proxmox_virtual_environment_vm.unprotected[0]',
            "type": "proxmox_virtual_environment_vm", "change": {
                "actions": actions or ["create"], "before": {"node_name": "n1", "vm_id": 100},
                "after": {"node_name": "n1", "vm_id": vmid, "started": False,
                          "cpu": [{"cores": 2}], "memory": [{"dedicated": 1024}],
                          "disk": [{"interface": "scsi0", "datastore_id": "local", "size": 8}],
                          "network_device": [{"bridge": "vmbr0", "mac_address": "AA:BB:CC:DD:EE:FF"}],
                          "clone": [{"vm_id": 900, "node_name": "n1"}]}, "after_unknown": {}}}


def snapshot(item, deposed=False):
    values = deepcopy(item["change"]["after"])
    values["smbios"] = [{"uuid": "new-native-uuid"}]
    return {"resources": [{"module": 'module.vm["private-key"]', "type": item["type"],
                           "name": "unprotected", "instances": [{"index_key": 0, "attributes": values,
                                                                     **({"deposed": "abc"} if deposed else {})}]}]}


class API:
    def effective_permissions(self, path):
        return {path: {"VM.Audit": 0}}

    def cluster_vm_resources(self):
        return [{"vmid": 101, "node": "n1", "type": "qemu"}]

    def node_status(self, node):
        return {"status": "online"}

    def vm_config(self, node, vmid):
        if vmid == 100:
            raise PveApiNotConfiguredError("absent", status_code=404)
        return {"cores": 2, "memory": "1024", "scsi0": "local:vm-101-disk-0,size=8G",
                "net0": "virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0", "smbios1": "uuid=new-native-uuid"}

    def vm_status(self, node, vmid):
        return {"status": "stopped"}


@pytest.mark.parametrize("actions", [["create"], ["update"], ["delete"], ["delete", "create"], ["create", "delete"], ["no-op"]])
def test_review_redacts_keys_and_only_clone_actions_depend_on_template(actions):
    summary, changes, dependencies = machine_review({"resource_changes": [change(actions)]})
    assert "private-key" not in str(summary)
    assert bool(dependencies) == ("create" in actions)
    assert bool(changes) == (actions != ["no-op"])


def test_unknown_clone_is_rejected():
    item = change()
    item["change"]["after_unknown"] = {"clone": True}
    with pytest.raises(ValidationError, match="unknown clone"):
        machine_review({"resource_changes": [item]})


def test_stopped_vm_and_no_root_outputs_verify():
    item = change()
    result = verify_configuration(expectations([item], snapshot(item)), API())
    assert result["status"] == "passed"


def test_missing_pve_bios_uses_seabios_default_but_not_ovmf():
    item = change()
    item["change"]["after"]["bios"] = "seabios"
    report = verify_configuration(expectations([item], snapshot(item)), API())
    assert report["status"] == "passed"
    item["change"]["after"]["bios"] = "ovmf"
    report = verify_configuration(expectations([item], snapshot(item)), API())
    assert report["status"] == "failed"
    assert report["objects"][0]["checks"]["bios"] == "failed"


@pytest.mark.parametrize("actions,wrong_identity", [
    (["create"], {"vm_id": 999}),
    (["update"], {"node_name": "wrong"}),
    (["delete", "create"], {"node_name": "wrong", "vm_id": 999}),
])
def test_snapshot_identity_must_match_plan_before_api_observation(actions, wrong_identity):
    item = change(actions)
    state = snapshot(item)
    state["resources"][0]["instances"][0]["attributes"].update(wrong_identity)
    # No API is needed to reject the wrong new-object association. A
    # coincidentally matching live VM must not rescue this snapshot.
    report = verify_configuration(expectations([item], state), None)
    assert report["status"] == "failed"
    assert report["objects"][0]["checks"] == {"snapshot_identity": "failed"}


def test_missing_snapshot_identity_stays_unknown():
    item = change()
    state = snapshot(item)
    del state["resources"][0]["instances"][0]["attributes"]["vm_id"]
    report = verify_configuration(expectations([item], state), API())
    assert report["status"] == "unknown"
    assert report["objects"][0]["checks"] == {"snapshot_identity": "unknown"}


def test_unknown_planned_identity_resolves_only_from_original_snapshot():
    item = change()
    state = snapshot(item)
    item["change"]["after"].update(node_name=None, vm_id=None)
    item["change"]["after_unknown"].update(node_name=True, vm_id=True)
    assert verify_configuration(expectations([item], state), API())["status"] == "passed"
    assert verify_configuration(expectations([item], None), API())["status"] == "unknown"


def test_unknown_values_only_resolve_from_original_snapshot():
    item = change()
    state = snapshot(item)
    item["change"]["after"]["network_device"][0]["mac_address"] = None
    item["change"]["after_unknown"] = {"network_device": [{"mac_address": True}]}
    assert verify_configuration(expectations([item], state), API())["status"] == "passed"
    assert verify_configuration(expectations([item], None), API())["status"] == "unknown"
    item["change"]["after"]["cpu"][0]["cores"] = 4
    assert verify_configuration(expectations([item], state), API())["status"] == "failed"


@pytest.mark.parametrize("actions", [["delete", "create"], ["create", "delete"]])
def test_replacement_checks_old_absence_and_new_identity(actions):
    item = change(actions)
    expected = expectations([item], snapshot(item))
    assert len(expected) == 2
    assert verify_configuration(expected, API())["status"] == "passed"
    item["change"]["before"]["vm_id"] = 101
    expected = expectations([item], snapshot(item))
    assert len(expected) == 1
    assert verify_configuration(expected, API())["status"] == "passed"
    expected[0]["native_identity"] = []
    assert verify_configuration(expected, API())["status"] == "unknown"


def test_deposed_state_and_permission_failure_do_not_pass():
    item = change(["delete", "create"])
    assert verify_configuration(expectations([item], snapshot(item, True)), API())["status"] == "failed"

    class Denied(API):
        def effective_permissions(self, path):
            raise PermissionError("private diagnostic")

    deleted = change(["delete"])
    report = verify_configuration(expectations([deleted], {"resources": []}), Denied())
    assert report["status"] == "unknown"
    assert "private diagnostic" not in str(report)


def test_empty_scope_is_explicit():
    report = verify_configuration([], API())
    assert {k: report[k] for k in ('status', 'scope', 'objects')} == {"status": "passed", "scope": "empty", "objects": []}
    assert report['observation_window']['source'] == 'internal-default'


def test_missing_node_is_not_successful_deletion():
    class MissingNode(API):
        def node_status(self, node):
            raise PveApiNotConfiguredError("node missing", status_code=404)

    deleted = change(["delete"])
    assert verify_configuration(expectations([deleted], {"resources": []}), MissingNode())["status"] == "unknown"


@pytest.mark.parametrize("attachment", [{"scsi1": "local:vm-101-disk-1,size=8G"},
                                        {"net1": "virtio=AA:BB:CC:DD:EE:00,bridge=vmbr0"},
                                        {"unused0": "local:vm-101-disk-2"}])
def test_unexpected_attachments_fail(attachment):
    class Extra(API):
        def vm_config(self, node, vmid):
            return super().vm_config(node, vmid) | attachment

    item = change()
    assert verify_configuration(expectations([item], snapshot(item)), Extra())["status"] == "failed"


@pytest.mark.parametrize("bios,present,storage,efi_type,passed", [
    ("seabios", False, "local", "4m", True),
    ("seabios", True, "local", "4m", False),
    ("ovmf", True, "local", "4m", True),
    ("ovmf", False, "local", "4m", False),
    ("ovmf", True, "wrong", "4m", False),
    ("ovmf", True, "local", "2m", False),
])
def test_efi_configuration_matches_saved_plan(bios, present, storage, efi_type, passed):
    item = change()
    values = item["change"]["after"]
    values["bios"] = bios
    values["efi_disk"] = [{"datastore_id": "local", "type": "4m"}] if bios == "ovmf" else []
    state = snapshot(item)
    # Known plan scope cannot be replaced by a different post-apply snapshot.
    state["resources"][0]["instances"][0]["attributes"]["efi_disk"] = []

    class EFI(API):
        def vm_config(self, node, vmid):
            config = super().vm_config(node, vmid) | {"bios": bios}
            if present:
                config["efidisk0"] = f"{storage}:vm-101-disk-1,efitype={efi_type},size=4M"
            return config

    report = verify_configuration(expectations([item], state), EFI(), timeout=1, interval=0)
    assert (report["status"] == "passed") is passed
    checks = report["objects"][0]["checks"]
    assert checks["disk_attachments"] == ("passed" if present == (bios == "ovmf") else "failed")
    if bios == "ovmf" and present:
        assert checks["efi_disk.storage"] == ("passed" if storage == "local" else "failed")
        assert checks["efi_disk.type"] == ("passed" if efi_type == "4m" else "failed")


def test_power_converges_without_reapplying():
    class Converging(API):
        calls = 0
        def vm_status(self, node, vmid):
            self.calls += 1
            return {'status': 'running' if self.calls == 1 else 'stopped'}
    api = Converging()
    item = change()
    report = verify_configuration(expectations([item], snapshot(item)), api, interval=0)
    assert report['status'] == 'passed'
    assert api.calls == 2
    assert report['observations'][0]['terminal']['attempt'] == 2


def test_one_window_shared_across_objects_and_retries():
    from iaas.observation import ObservationExpired
    class Bound:
        remaining_calls = 0
        def remaining(self, phase):
            self.remaining_calls += 1
            if self.remaining_calls > 6:
                raise ObservationExpired()
            return 1
    item = change()
    api = API()
    expected = expectations([item], snapshot(item))
    expected.append({**deepcopy(expected[0]), 'vmid': 102})
    report = verify_configuration(expected, api, budget=Bound(), interval=0)
    assert report['objects'][0]['status'] == 'passed'
    assert report['objects'][1]['status'] == 'unknown'
    assert report['observations'][1]['terminal']['reason'] == 'observation_deadline_expired'


def test_independent_window_does_not_reuse_ended_original_verification():
    item = change()
    expected = expectations([item], snapshot(item))
    class Ended:
        def remaining(self, phase):
            raise RuntimeError('ended')
    assert verify_configuration(expected, API(), budget=Ended())['status'] == 'unknown'
    report = verify_configuration(expected, API())
    assert report['status'] == 'passed'
    assert report['observation_window']['source'] == 'internal-default'


def test_temporary_query_retry_retains_bound_identity_and_comparisons():
    from iaas.pve_inventory.pve_api import PveApiUnavailableError
    class Temporary(API):
        reads = 0
        def vm_config(self, node, vmid):
            self.reads += 1
            if self.reads == 1:
                raise PveApiUnavailableError('unavailable')
            return super().vm_config(node, vmid)
    item = change()
    api = Temporary()
    report = verify_configuration(expectations([item], snapshot(item)), api, interval=0)
    assert report['status'] == 'passed' and api.reads == 2
    evidence = report['observations'][0]['terminal']['evidence']
    assert evidence['actual']['uuid'] == 'new-native-uuid'
    assert evidence['expected']['volumes'][0]['size'] == 8
    assert evidence['actual']['volumes'][0]['volid'] == 'local:vm-101-disk-0'


def test_tighter_execution_cutoff_is_reported_as_actual_window():
    from iaas.observation import ObservationBudget
    from iaas.runtime_execution.pve_results import VerificationBudget
    enclosing = ObservationBudget(1, source='bound-execution')
    window = VerificationBudget(120, enclosing=enclosing)
    assert window.cutoff == enclosing.cutoff
    assert window.window['cutoff'] == enclosing.facts()['cutoff']
    assert window.window['source'] == 'internal-default+execution-cutoff'


def test_ha_targets_preserve_separate_terminal_evidence():
    class HA:
        def ha_status(self):
            return [{'sid': 'vm:101', 'state': 'started'}, {'sid': 'vm:102', 'state': 'started'}]
    expected = [{'kind': 'ha', 'values': {'resource_id': name, 'state': 'started'},
                 'absent': False, 'snapshot_complete': True} for name in ('vm:101', 'vm:102')]
    report = verify_configuration(expected, HA())
    assert report['status'] == 'passed'
    assert {row['association']['resource_id'] for row in report['observations']} == {'vm:101', 'vm:102'}


def test_native_diagnostics_keep_historical_failure_separate_from_convergence():
    from iaas.runtime_execution.pve_results import stop_diagnostics
    item = change()
    report = verify_configuration(expectations([item], snapshot(item)), API())
    result = {'native_execution': {'status': 'failed'}, 'state_persistence': {'status': 'unknown'},
              'collection': {'status': 'passed'}, 'effects': {'facility': 'known'}}
    diagnosis = stop_diagnostics(result, report)
    assert diagnosis['stopping']['check'] == 'native_execution'
    assert diagnosis['stopping']['status'] == 'failed'
    assert diagnosis['activity'] == 'stopped' and diagnosis['existence'] == 'present'
    assert diagnosis['observations'][0]['terminal']['status'] == 'ready'
    assert diagnosis['recovery']['supported'] is False
