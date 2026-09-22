from copy import deepcopy

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.runtime_execution.pve_results import machine_review, expectations, verify_configuration
from iaas_automation.pve_inventory.pve_api import PveApiNotConfiguredError


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
        def vm_config(self, node, vmid):
            raise PermissionError("private diagnostic")

    deleted = change(["delete"])
    report = verify_configuration(expectations([deleted], {"resources": []}), Denied())
    assert report["status"] == "unknown"
    assert "private diagnostic" not in str(report)


def test_empty_scope_is_explicit():
    assert verify_configuration([], API()) == {"status": "passed", "scope": "empty", "objects": []}


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
