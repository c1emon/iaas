from copy import deepcopy

from iaas.opnsense_workflow.reader import FixedCollectionTransport, _HttpFailure


DESIRED = {
    "name": "inside",
    "members": ["lan", "opt1"],
    "gui_group": True,
    "sequence": 0,
}
UUID = "11111111-1111-4111-8111-111111111111"
LOADED_GROUP_RULE = f'@4 pass in quick on inside inet proto tcp from any to any label "{UUID}"'
OVERVIEW = [
    {"identifier": "lan", "device": "igb0"},
    {"identifier": "opt1", "device": "vlan10"},
]
IFCONFIG = {
    "igb0": {"groups": ["inside"]},
    "vlan10": {"groups": ["inside", "other"]},
}


class GroupWire(FixedCollectionTransport):
    def __init__(self, *, version="26.7.3", overview=None, ifconfig=None,
                 filter_rows=None, dnat_rows=None, one_to_one_rows=None, pf_snapshot=None):
        self.calls = []
        self.version = version
        self.overview = deepcopy(OVERVIEW if overview is None else overview)
        self.ifconfig = deepcopy(IFCONFIG if ifconfig is None else ifconfig)
        self.filter_rows = deepcopy(filter_rows or {})
        self.dnat_rows = deepcopy(dnat_rows or {})
        self.one_to_one_rows = deepcopy(one_to_one_rows or {})
        self.pf_snapshot = deepcopy(pf_snapshot or {"rules": {"filter rules": {}, "nat rules": {}}})

    def _request(self, method, path, payload=None):
        self.calls.append((method, path))
        if path == "core/firmware/status":
            return {"product": {"product_version": self.version}}
        if path == "interfaces/overview/interfaces_info":
            return deepcopy(self.overview)
        if path == "diagnostics/interface/get_interface_config":
            return deepcopy(self.ifconfig)
        if path == "firewall/filter/get":
            return {"filter": {"rules": {"rule": self.filter_rows}}}
        if path == "firewall/d_nat/get":
            return {"DNat": {"rule": self.dnat_rows}}
        if path == "firewall/one_to_one/get":
            return {"filter": {"onetoone": {"rule": self.one_to_one_rows}}}
        if path == "diagnostics/firewall/pf_statistics/rules":
            return deepcopy(self.pf_snapshot)
        raise AssertionError(path)


def test_group_transport_reads_fixed_version_and_complete_current_state_sources():
    wire = GroupWire()

    result = wire.active_check("interface-groups", ["inside"], deepcopy(DESIRED))

    assert result["status"] == "verified"
    assert result["current_status"] == "verified"
    assert result["reason"] == "current_group_membership_matches"
    assert result["device_version"] == "26.7.3"
    assert wire.calls == [
        ("GET", "core/firmware/status"),
        ("GET", "interfaces/overview/interfaces_info"),
        ("GET", "diagnostics/interface/get_interface_config"),
        ("GET", "firewall/filter/get"),
        ("GET", "firewall/d_nat/get"),
        ("GET", "firewall/one_to_one/get"),
        ("GET", "diagnostics/firewall/pf_statistics/rules"),
    ]


def test_group_transport_does_not_allow_external_consumer_override():
    result = GroupWire().active_check(
        "interface-groups",
        ["inside"],
        deepcopy(DESIRED),
        context={"consumer_observation": {"status": "failed", "reason": "caller_must_not_override"}},
    )

    assert result["status"] == "verified"
    assert result["current_status"] == "verified"
    assert result["consumer"]["status"] == "not_applicable"
    assert result["completion"] == {
        "status": "unknown",
        "reason": "group_reconfigure_not_correlated",
    }


def test_group_transport_checks_loaded_group_consumer_success():
    wire = GroupWire(
        filter_rows={UUID: {"enabled": True, "interface": ["inside"]}},
        pf_snapshot={"rules": {"filter rules": {LOADED_GROUP_RULE: {}}, "nat rules": {}}},
    )

    result = wire.active_check("interface-groups", ["inside"], deepcopy(DESIRED))

    assert result["status"] == "verified"
    assert result["consumer"]["status"] == "verified"
    assert result["consumer"]["matches"][0]["uuid"] == UUID


def test_group_transport_checks_loaded_group_consumer_failure():
    wrong_rule = LOADED_GROUP_RULE.replace("on inside", "on igb0")
    wire = GroupWire(
        filter_rows={UUID: {"enabled": True, "interface": ["inside"]}},
        pf_snapshot={"rules": {"filter rules": {wrong_rule: {}}, "nat rules": {}}},
    )

    result = wire.active_check("interface-groups", ["inside"], deepcopy(DESIRED))

    assert result["status"] == "failed"
    assert result["consumer"]["status"] == "failed"
    assert result["reason"] == "loaded_interface_group_members_mismatch"


def test_group_transport_nat_consumer_is_unsupported():
    wire = GroupWire(dnat_rows={UUID: {"enabled": True, "interface": ["inside"]}})

    result = wire.active_check("interface-groups", ["inside"], deepcopy(DESIRED))

    assert result["status"] == "unsupported"
    assert result["consumer"] == {
        "status": "unsupported",
        "reason": "unsupported_nat_consumer_identity",
    }


def test_group_transport_bad_current_read_is_unknown():
    wire = GroupWire(ifconfig={"igb0": {"groups": "inside"}, "vlan10": {"groups": ["inside"]}})

    result = wire.active_check("interface-groups", ["inside"], deepcopy(DESIRED))

    assert result["status"] == "unknown"
    assert result["reason"] == "interface_groups_unavailable"


def test_group_transport_unqualified_version_stops_before_group_reads():
    wire = GroupWire(version="26.1")

    result = wire.active_check("interface-groups", ["inside"], deepcopy(DESIRED))

    assert result["status"] == "unsupported"
    assert result["reason"] == "device_version_unqualified"
    assert wire.calls == [("GET", "core/firmware/status")]


def test_group_transport_endpoint_failure_is_unknown_or_unsupported():
    class Denied(GroupWire):
        def _request(self, method, path, payload=None):
            self.calls.append((method, path))
            if path == "core/firmware/status":
                return {"product": {"product_version": "26.7.3"}}
            raise _HttpFailure("failed", "permission_denied")

    result = Denied().active_check("interface-groups", ["inside"], deepcopy(DESIRED))

    assert result == {"status": "unknown", "reason": "permission_denied"}
