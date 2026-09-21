"""Offline contract checks for the bounded OPNsense workflow reader."""

from __future__ import annotations

from copy import deepcopy

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_workflow.planning import coverage, plan
from iaas_automation.opnsense_workflow.reader import (
    COLLECTION_TARGETS,
    FixedCollectionTransport,
    MAX_PAGES,
    Reader,
    ReaderError,
    normalize_desired,
)


TARGET = {"host": "firewall", "endpoint": "https://firewall.example", "ssl_verify": True}
CREDENTIALS = {"OPNSENSE_API_KEY": "key", "OPNSENSE_API_SECRET": "secret"}


ROWS = {
    "aliases": [{
        "name": "NETS", "type": "host", "content": ["192.0.2.10"],
        "description": "managed", "enabled": True,
    }],
    "vips": [{
        "description": "vip", "interface": "lan", "address": "192.0.2.10/32",
        "bind": False, "expand": True,
    }],
    "gateways": [{
        "name": "WAN", "interface": "wan", "ip_protocol": "inet", "gateway": "192.0.2.1",
        "default_gw": False, "far_gw": False, "monitor_disable": False,
        "monitor_noroute": False, "monitor": "192.0.2.1", "force_down": False,
        "latency_low": 200, "latency_high": 500, "loss_low": 10, "loss_high": 20,
        "interval": 1, "time_period": 60, "loss_interval": 4, "data_length": 1,
        "priority": 255, "weight": 1, "description": "managed",
    }],
    "filter-rules": [{
        "description": "iaas:opnsense:filter:demo:allow", "enabled": True, "sequence": 10,
        "interface": ["lan"], "direction": "in", "action": "pass", "quick": True,
        "ip_protocol": "inet", "protocol": "TCP", "source_net": "any",
        "destination_net": "NETS", "log": False,
    }],
    "dnat": [{
        "description": "iaas:opnsense:dnat:demo:web", "enabled": True, "sequence": 10,
        "interface": ["wan"], "ip_protocol": "inet", "protocol": "tcp",
        "source_net": "any", "destination_net": "wanip", "target": "192.0.2.10",
        "nat_reflection": "", "associated_rule": "rule",
    }],
    "one-to-one-nat": [{
        "description": "iaas:opnsense:one-to-one-nat:demo:web", "enabled": True, "sequence": 10,
        "interface": "wan", "type": "binat", "external": "198.51.100.10",
        "source_net": "192.0.2.10", "destination_net": "any", "nat_reflection": "disable",
    }],
    "interface-groups": [{
        "name": "External", "members": ["wan"], "gui_group": True, "sequence": 0,
        "description": "managed",
    }],
}


class FakeCollection:
    def __init__(self, rows=None, *, interfaces=None):
        self.rows = deepcopy(rows or ROWS)
        self.interfaces_seen = interfaces if interfaces is not None else ["lan", "wan"]
        self.calls: list[tuple[str, dict]] = []
        self.mutated = False

    def list(self, target, **kwargs):
        self.calls.append((target, kwargs))
        resource = next(resource for resource, value in COLLECTION_TARGETS.items() if value == target)
        return deepcopy(self.rows[resource])

    def interfaces(self):
        return list(self.interfaces_seen)

    def save(self, *args, **kwargs):
        self.mutated = True


def reader(transport):
    return Reader(TARGET, CREDENTIALS, transport)


def test_all_seven_collection_targets_are_read_only_and_normalized():
    transport = FakeCollection()
    observations = reader(transport).read(list(COLLECTION_TARGETS))

    assert set(observations) == set(COLLECTION_TARGETS)
    assert all(observation["status"] == "complete" for observation in observations.values())
    assert observations["filter-rules"]["objects"][0]["identity"] == [
        "iaas:opnsense:filter:demo:allow"
    ]
    assert observations["filter-rules"]["objects"][0]["configuration"]["source_invert"] is False
    assert observations["filter-rules"]["objects"][0]["configuration"]["destination_net"] == ["NETS"]
    assert observations["filter-rules"]["objects"][0]["references"] == ["aliases:NETS", "interface-groups:lan"]
    assert observations["aliases"]["objects"][0]["recovery"] == "expressible"
    assert observations["aliases"]["interfaces"] == ["lan", "wan"]
    assert not transport.mutated


def test_read_does_not_probe_optional_confirmation_capabilities():
    class ProbeFail(FakeCollection):
        def confirmation_capabilities(self):
            raise AssertionError('optional firmware probe must not run during read')

    transport = ProbeFail()
    observation = reader(transport).read(['aliases'])['aliases']
    assert observation['status'] == 'complete'
    assert observation['objects'][0]['identity'] == ['NETS']


def _plan_alias_deletion(rows):
    observations = reader(FakeCollection(rows)).read(coverage([{"resource": "aliases"}]))
    return plan(
        {"aliases": {"opnsense_aliases": [ROWS["aliases"][0] | {"state": "absent"}]}},
        {"schema_version": 1, "selection": {"aliases": "all"},
         "managed": {"aliases": [["NETS"]]}},
        observations, TARGET,
        {"image_digest": "registry.invalid/runtime@sha256:" + "a" * 64,
         "platform": "linux/arm64", "interface_version": 1},
        {"inputs": []},
    )


@pytest.mark.parametrize("resource, consumer", [
    ("aliases", ROWS["aliases"][0] | {
        "name": "GROUP", "type": "networkgroup", "content": ["NETS"], "proto": ["IPv4"]}),
    ("aliases", ROWS["aliases"][0] | {
        "name": "GROUP", "type": "networkgroup", "content": {"NETS": {}}, "proto": ["IPv4"]}),
    ("filter-rules", ROWS["filter-rules"][0] | {
        "description": "native rule", "uuid": "native-test", "destination_net": "NETS,OTHER"}),
    ("filter-rules", ROWS["filter-rules"][0] | {
        "description": "native rule", "uuid": "native-test", "destination_net": "NETS\nOTHER"}),
    ("dnat", ROWS["dnat"][0] | {"source_net": "NETS,OTHER"}),
])
def test_reader_dependencies_prevent_deleting_referenced_alias(resource, consumer):
    rows = {name: [] for name in ROWS}
    rows["aliases"] = deepcopy(ROWS["aliases"])
    rows[resource].append(consumer)
    observed = reader(FakeCollection(rows)).read([resource])[resource]["objects"][-1]
    assert observed["configuration"] is None
    assert "aliases:NETS" in observed["references"]
    with pytest.raises(ValidationError, match="missing dependency"):
        _plan_alias_deletion(rows)


def test_unrelated_unexpressible_networkgroup_does_not_block_alias_deletion():
    rows = {name: [] for name in ROWS}
    rows["aliases"] = [ROWS["aliases"][0], ROWS["aliases"][0] | {
        "name": "GROUP", "type": "networkgroup", "content": ["OTHER"], "proto": ["IPv4"]}]
    candidate = _plan_alias_deletion(rows)
    assert [item["action"] for item in candidate["differences"]] == ["delete"]


@pytest.mark.parametrize("field, value, canonical", [
    ("icmp6type", ["echoreq"], "icmpv6_type"),
    ("icmpv6_type", ["echoreq"], "icmpv6_type"),
    ("divert-to", {"192.0.2.20": {"selected": 1}}, "divert_to"),
    ("divert_to", "192.0.2.20", "divert_to"),
])
def test_unsupported_native_field_aliases_never_become_recoverable(field, value, canonical):
    rows = {"filter-rules": [ROWS["filter-rules"][0] | {field: value}]}
    item = reader(FakeCollection(rows)).read(["filter-rules"])["filter-rules"]["objects"][0]
    assert item["configuration"] is None
    assert item["reason"] == "unexpressed_native_fields:" + canonical
    assert item["recovery"] == "manual_required"


@pytest.mark.parametrize("value", [0, False, "0"])
def test_unknown_native_zero_is_not_assumed_to_be_a_default(value):
    rows = {"aliases": [ROWS["aliases"][0] | {"future_option": value}]}
    item = reader(FakeCollection(rows)).read(["aliases"])["aliases"]["objects"][0]
    assert item["configuration"] is None
    assert item["reason"] == "unexpressed_native_fields:unknown_native_field"


@pytest.mark.parametrize("mode", [
    {"ipalias": {"selected": 1}, "carp": {"selected": 1}},
    [{"value": "ipalias", "selected": 1}, {"value": "carp", "selected": 1}],
    {"ipalias": {"selected": 1}, "carp": {"selected": "invalid"}},
    {"ipalias": {"selected": 1}, "carp": "invalid"},
])
def test_invalid_selector_makes_observation_incomplete_without_exposing_values(mode):
    rows = {"vips": [ROWS["vips"][0] | {"mode": mode}]}
    observation = reader(FakeCollection(rows)).read(["vips"])["vips"]
    assert observation["status"] == "incomplete"
    assert observation["objects"] == []
    assert observation["reason"] == ["malformed_native_selector"]


def test_selector_labels_do_not_replace_keys_and_multiple_members_are_preserved():
    rows = {"vips": [ROWS["vips"][0] | {
        "mode": {"ipalias": {"selected": 1, "value": "IP Alias"}},
        "interface": [{"key": "lan", "selected": 1, "value": "LAN display label"}],
    }], "interface-groups": [ROWS["interface-groups"][0] | {
        "members": {"wan": {"selected": 1, "value": "WAN display label"},
                    "lan": {"selected": 1, "value": "LAN display label"}},
    }]}
    observations = reader(FakeCollection(rows)).read(list(rows))
    vip = observations["vips"]["objects"][0]
    assert vip["identity"] == ["192.0.2.10/32", "lan"]
    assert vip["configuration"] is not None
    assert observations["interface-groups"]["objects"][0]["configuration"]["members"] == ["lan", "wan"]


@pytest.mark.parametrize("overflow", [False, True])
def test_pagination_never_discards_objects_to_match_total(overflow):
    class Paged(FakeCollection):
        def list(self, target, **kwargs):
            page = kwargs["page"]
            names = ["A", "B"] if page == 1 else ["C", "D"] if overflow else ["C"]
            return {"current": page, "rowCount": 2, "total": 3,
                    "rows": [ROWS["aliases"][0] | {"name": name} for name in names]}

    observation = reader(Paged()).read(["aliases"])["aliases"]
    if overflow:
        assert observation["status"] == "incomplete"
        assert observation["objects"] == []
        assert observation["reason"] == "inconsistent_collection_total"
    else:
        assert observation["status"] == "complete"
        assert [item["identity"] for item in observation["objects"]] == [["A"], ["B"], ["C"]]


def test_page_shapes_are_bounded_and_complete():
    class Paged(FakeCollection):
        def list(self, target, **kwargs):
            self.calls.append((target, kwargs))
            if target != "alias":
                return []
            page = kwargs["page"]
            rows = [{"name": "A", "type": "host", "content": ["192.0.2.1"], "description": "managed", "enabled": True}]
            rows += [{"name": "B", "type": "host", "content": ["192.0.2.2"], "description": "managed", "enabled": True}]
            return {"current": page, "rowCount": 1, "total": 2, "rows": [rows[page - 1]]} if page <= 2 else {"current": page, "rowCount": 1, "total": 2, "rows": []}

    transport = Paged()
    observation = reader(transport).read(["aliases"])["aliases"]
    assert observation["status"] == "complete"
    assert observation["coverage"]["pages"] == 2
    assert [item["identity"] for item in observation["objects"]] == [["A"], ["B"]]


def test_pagination_bound_is_incomplete_and_never_means_absent():
    class Unbounded(FakeCollection):
        def list(self, target, **kwargs):
            self.calls.append((target, kwargs))
            return {"current": kwargs["page"], "rowCount": 1, "total": MAX_PAGES + 1,
                    "rows": [{"name": "A", "type": "host", "content": ["192.0.2.1"], "description": "managed", "enabled": True}]}

    observation = reader(Unbounded()).read(["aliases"])["aliases"]
    assert observation["status"] == "incomplete"
    assert observation["objects"] == []
    assert observation["reason"] == "configuration_bound_exceeded"


def test_unrepresentable_live_object_keeps_identity_references_and_manual_recovery():
    rows = deepcopy(ROWS)
    rows["filter-rules"][0].pop("action")
    observation = reader(FakeCollection(rows)).read(["filter-rules"])["filter-rules"]
    assert observation["status"] == "complete"
    item = observation["objects"][0]
    assert item["identity"] == ["iaas:opnsense:filter:demo:allow"]
    assert item["configuration"] is None
    assert "aliases:NETS" in item["references"]
    assert item["recovery"] == "manual_required"


def test_duplicate_identity_is_incomplete():
    rows = deepcopy(ROWS)
    rows["aliases"].append(deepcopy(rows["aliases"][0]))
    observation = reader(FakeCollection(rows)).read(["aliases"])["aliases"]
    assert observation["status"] == "incomplete"
    assert observation["reason"] == ["duplicate_identity"]


def test_unmanaged_rule_uses_native_uuid_identity_without_blocking_enumeration():
    rows = deepcopy(ROWS)
    rows["filter-rules"] = [{"uuid": "native-rule-1", "description": "Default rule", "enabled": True,
                              "sequence": 1, "interface": ["lan"], "direction": "in", "action": "block",
                              "quick": False, "ip_protocol": "inet", "protocol": "any",
                              "source_net": "any", "destination_net": "any"}]
    observation = reader(FakeCollection(rows)).read(["filter-rules"])["filter-rules"]
    assert observation["status"] == "complete"
    assert observation["objects"][0]["identity"] == ["native:native-rule-1"]
    assert observation["objects"][0]["configuration"] is None
    assert observation["objects"][0]["recovery"] == "manual_required"


def test_fixed_collection_empty_model_is_an_empty_collection():
    assert FixedCollectionTransport._entries(
        {"alias": {"aliases": {"alias": {}}}}, "alias.aliases.alias"
    ) == []


def test_default_reader_is_unsupported_and_does_not_offer_write_api():
    observation = Reader(TARGET, {}).read(["aliases"])["aliases"]
    assert observation["status"] == "unsupported"
    assert "save" not in dir(Reader(TARGET, CREDENTIALS))


def test_normalization_keeps_semantics_stable_and_rejects_unknown_fields():
    record = deepcopy(ROWS["filter-rules"][0])
    record.pop("description")
    record.update(scope="demo", slug="allow", state="present")
    record["interface"] = ["wan", "lan"]
    normalized = normalize_desired("filter-rules", record)
    assert normalized["interface"] == ["lan", "wan"]
    assert normalized["source_invert"] is False
    assert normalize_desired("filter-rules", record | {"unexpected": True})["unexpected"] is True


@pytest.mark.parametrize("target", [{}, {"host": "fw", "endpoint": "ftp://fw", "ssl_verify": True},
                                     {"host": "fw", "endpoint": "https://fw?token=bad", "ssl_verify": True}])
def test_target_is_explicit_and_non_secret_url_shape(target):
    with pytest.raises(ReaderError):
        Reader(target, CREDENTIALS, FakeCollection())


def test_resource_selection_is_explicit():
    with pytest.raises(ReaderError):
        reader(FakeCollection()).read("aliases")
    with pytest.raises(ReaderError):
        reader(FakeCollection()).read(["snat"])
    with pytest.raises(ReaderError):
        reader(FakeCollection()).read(["aliases", "aliases"])


def test_raw_provider_select_and_inverted_fields_follow_pinned_simplify_shape():
    rows = {resource: [] for resource in ROWS}
    rows["aliases"] = [{"name": "NETS", "type": {"host": {"selected": 1}},
                         "content": {"192.0.2.10": {"selected": 1}}, "descr": "managed",
                         "disabled": "0"}]
    rows["vips"] = [{"descr": "vip", "interface": {"lan": {"selected": 1}},
                      "mode": {"ipalias": {"selected": 1}}, "advbase": "1", "advskew": "0",
                      "subnet": "192.0.2.10", "subnet_bits": "32", "nobind": "1", "noexpand": "0"}]
    rows["gateways"] = deepcopy(ROWS["gateways"])
    rows["filter-rules"] = [{"description": "iaas:opnsense:filter:demo:allow", "disabled": "0",
                              "sequence": "10", "interface": {"lan": {"selected": 1}},
                              "direction": {"in": {"selected": 1}}, "action": {"pass": {"selected": 1}},
                              "quick": "1", "ipprotocol": {"inet": {"selected": 1}},
                              "protocol": {"TCP": {"selected": 1}},
                              "source": {"network": "any", "not": "0"},
                              "destination": {"network": "NETS", "not": "0"}, "log": "0"}]
    rows["dnat"] = deepcopy(ROWS["dnat"])
    rows["one-to-one-nat"] = deepcopy(ROWS["one-to-one-nat"])
    rows["interface-groups"] = [{"ifname": "External", "members": {"wan": {"selected": 1}},
                                  "nogroup": "0", "sequence": "0", "descr": "managed"}]

    observations = reader(FakeCollection(rows)).read(["aliases", "vips", "filter-rules", "interface-groups"])
    assert observations["aliases"]["status"] == "complete"
    assert observations["aliases"]["objects"][0]["configuration"]["content"] == ["192.0.2.10"]
    assert observations["vips"]["objects"][0]["identity"] == ["192.0.2.10/32", "lan"]
    assert observations["vips"]["objects"][0]["configuration"] is not None
    assert observations["filter-rules"]["status"] == "complete"
    assert observations["interface-groups"]["objects"][0]["configuration"]["members"] == ["wan"]


def test_gateway_detail_is_one_model_with_nested_choices_and_logical_interfaces():
    class Wire(FixedCollectionTransport):
        def __init__(self):
            self.calls = []

        def _request(self, method, path, payload=None):
            self.calls.append((method, path))
            if path == 'firewall/group/get_item':
                return {'group': {'members': {'wan': {'selected': 0}, 'lan': {'selected': 0}}}}
            if path == 'routing/settings/search_gateway':
                return {'current': 1, 'rowCount': 1000, 'total': 1, 'rows': [{'uuid': 'gateway-id'}]}
            assert path == 'routing/settings/get_gateway/gateway-id'
            return {'gateway_item': ROWS['gateways'][0] | {'interface': {'wan': {'selected': 1}}}}

    wire = Wire()
    observation = reader(wire).read(['gateways'])['gateways']
    assert observation['status'] == 'complete'
    assert observation['objects'][0]['configuration']['interface'] == 'wan'
    assert observation['interfaces'] == ['lan', 'wan']
    assert all('get_interface_names' not in path for _, path in wire.calls)


def test_alias_active_check_uses_diagnostics_table_without_writes():
    class Active(FakeCollection):
        def active_check(self, resource, identity, desired):
            assert resource == "aliases"
            assert identity == ["NETS"]
            return {"status": "verified", "coverage": {"scope": "alias_table", "rows": 1}}

    transport = Active()
    result = reader(transport).active_check("aliases", ["NETS"], ROWS["aliases"][0])
    assert result["status"] == "verified"
    assert not transport.mutated


def test_reader_active_check_forwards_optional_dependency_context():
    class Active(FakeCollection):
        def active_check(self, resource, identity, desired, *, context=None):
            assert resource == "aliases"
            assert identity == ["GROUP"]
            assert context == {"live_aliases": []}
            return {"status": "incomplete", "reason": "networkgroup_dependency_unavailable"}

    result = reader(Active()).active_check(
        "aliases", ["GROUP"], ROWS["aliases"][0], context={"live_aliases": []}
    )
    assert result["status"] == "incomplete"


def test_fixed_alias_active_check_requires_complete_static_membership_match():
    class Diagnostics(FixedCollectionTransport):
        def __init__(self, response):
            self.response = response

        def _request(self, method, path, payload=None):
            return self.response

    desired = ROWS["aliases"][0] | {"state": "present"}
    assert Diagnostics({"rows": [{"ip": "192.0.2.10"}]}).active_check(
        "aliases", ["NETS"], desired
    )["status"] == "incomplete"
    assert Diagnostics({"rows": [{"ip": "192.0.2.10"}], "total": 1}).active_check(
        "aliases", ["NETS"], desired
    )["status"] == "verified"
    assert Diagnostics({"rows": [{"ip": "192.0.2.11"}], "total": 1}).active_check(
        "aliases", ["NETS"], desired
    )["status"] == "failed"
    assert Diagnostics({"rows": [], "total": 1}).active_check(
        "aliases", ["NETS"], desired
    )["status"] == "incomplete"
    assert Diagnostics({"rows": [{}], "total": 1}).active_check(
        "aliases", ["NETS"], desired
    )["status"] == "incomplete"
    assert Diagnostics({"rows": [{"ip": "not-an-address"}], "total": 1}).active_check(
        "aliases", ["NETS"], desired
    )["status"] == "incomplete"
    dynamic = desired | {"type": "urltable"}
    assert Diagnostics({"rows": [{"ip": "192.0.2.10"}], "total": 1}).active_check(
        "aliases", ["NETS"], dynamic
    )["status"] == "unsupported"


@pytest.mark.parametrize("alias_type, content, rows", [
    ("host", ["192.0.2.0/24"], ["192.0.2.0/25", "192.0.2.128/25"]),
    ("network", ["192.0.2.0/24"], ["192.0.2.0/24", "192.0.2.0/25"]),
    ("network", ["2001:db8::/64"], ["2001:db8::/65", "2001:db8:0:0:8000::/65"]),
])
def test_fixed_static_alias_active_check_compares_address_union(alias_type, content, rows):
    class Diagnostics(FixedCollectionTransport):
        def __init__(self, response):
            self.response = response

        def _request(self, method, path, payload=None):
            return self.response

    desired = {
        "name": "NETS", "type": alias_type, "content": content,
        "state": "present", "enabled": True,
    }
    result = Diagnostics({"rows": [{"ip": value} for value in rows], "total": len(rows)}).active_check(
        "aliases", ["NETS"], desired
    )

    assert result["status"] == "verified"
    assert result["coverage"]["expected"] == 1
    assert result["coverage"]["matched"] == 1


def test_fixed_networkgroup_active_check_resolves_selected_and_live_static_dependencies():
    class Diagnostics(FixedCollectionTransport):
        def __init__(self, response):
            self.response = response
            self.calls = []

        def _request(self, method, path, payload=None):
            self.calls.append((method, path))
            return self.response

    desired = {
        "name": "GROUP", "type": "networkgroup", "content": ["HOST", "NESTED"],
        "state": "present", "enabled": True,
    }
    context = {
        "selected": [{
            "resource": "aliases", "identity": ["GROUP"], "desired": desired,
        }, {
            "resource": "aliases", "identity": ["HOST"], "desired": {
                "name": "HOST", "type": "host", "content": ["192.0.2.10"],
                "state": "present", "enabled": True,
            },
        }],
        "live_aliases": [{
            "name": "NESTED", "type": "network", "content": ["2001:db8::/64"],
            "state": "present", "enabled": True,
        }],
    }
    result = Diagnostics({
        "rows": [{"ip": "192.0.2.10"}, {"ip": "2001:db8::/64"}], "total": 2,
    }).active_check("aliases", ["GROUP"], desired, context=context)

    assert result["status"] == "verified"
    assert result["coverage"]["expected"] == 2
    assert result["coverage"]["dependency"]["scope"] == "selected_transitions_and_live_dependencies"


def test_fixed_networkgroup_active_check_uses_live_unselected_dependency_only():
    class Diagnostics(FixedCollectionTransport):
        def __init__(self, response):
            self.response = response

        def _request(self, method, path, payload=None):
            return self.response

    desired = {
        "name": "GROUP", "type": "networkgroup", "content": ["HOST"],
        "state": "present", "enabled": True,
    }
    result = Diagnostics({"rows": [{"ip": "192.0.2.10"}], "total": 1}).active_check(
        "aliases", ["GROUP"], desired,
        context={
            "selected": [{"resource": "aliases", "identity": ["GROUP"], "desired": desired}],
            "live_aliases": [{
                "name": "HOST", "type": "host", "content": ["192.0.2.10"],
                "state": "present", "enabled": True,
            }],
        },
    )

    assert result["status"] == "verified"


@pytest.mark.parametrize("member, expected_status, expected_reason", [
    ({"name": "DYNAMIC", "type": "urltable", "content": ["https://example.invalid/list"],
      "state": "present", "enabled": True}, "unsupported", "dynamic_networkgroup_member"),
    (None, "incomplete", "networkgroup_dependency_unavailable"),
])
def test_fixed_networkgroup_active_check_does_not_turn_dynamic_or_missing_dependency_into_empty(
    member, expected_status, expected_reason
):
    class Diagnostics(FixedCollectionTransport):
        def __init__(self, response):
            self.response = response

        def _request(self, method, path, payload=None):
            return self.response

    dependency_name = "DYNAMIC" if member else "MISSING"
    desired = {
        "name": "GROUP", "type": "networkgroup", "content": [dependency_name],
        "state": "present", "enabled": True,
    }
    live = [] if member is None else [member]
    result = Diagnostics({"rows": [], "total": 0}).active_check(
        "aliases", ["GROUP"], desired,
        context={"selected": [{"resource": "aliases", "identity": ["GROUP"], "desired": desired}],
                 "live_aliases": live},
    )

    assert result["status"] == expected_status
    assert result["reason"] == expected_reason


def test_fixed_networkgroup_active_check_rejects_incomplete_observation_with_enough_rows():
    class Diagnostics(FixedCollectionTransport):
        def __init__(self, response):
            self.response = response

        def _request(self, method, path, payload=None):
            return self.response

    desired = {
        "name": "GROUP", "type": "networkgroup", "content": ["HOST"],
        "state": "present", "enabled": True,
    }
    result = Diagnostics({"rows": [{"ip": "192.0.2.10"}], "total": 1}).active_check(
        "aliases", ["GROUP"], desired,
        context={
            "selected": [{"resource": "aliases", "identity": ["GROUP"], "desired": desired}],
            "observations": {"aliases": {
                "status": "incomplete",
                "observation_scope": "configuration",
                "objects": [{"resource": "aliases", "identity": ["HOST"],
                              "configuration": {"name": "HOST", "type": "host",
                                                 "content": ["192.0.2.10"],
                                                 "state": "present", "enabled": True},
                              "classification": {"origin": "user_config",
                                                   "management": "independent",
                                                   "basis": ["supported_model"]}}],
            }},
        },
    )

    assert result["status"] == "incomplete"
    assert result["reason"] == "networkgroup_dependency_incomplete"


def test_fixed_networkgroup_active_check_rejects_duplicate_live_dependency_names():
    class Diagnostics(FixedCollectionTransport):
        def __init__(self, response):
            self.response = response

        def _request(self, method, path, payload=None):
            return self.response

    desired = {
        "name": "GROUP", "type": "networkgroup", "content": ["HOST"],
        "state": "present", "enabled": True,
    }
    host = {"name": "HOST", "type": "host", "content": ["192.0.2.10"],
            "state": "present", "enabled": True}
    result = Diagnostics({"rows": [{"ip": "192.0.2.10"}], "total": 1}).active_check(
        "aliases", ["GROUP"], desired,
        context={"selected": [{"resource": "aliases", "identity": ["GROUP"], "desired": desired}],
                 "live_aliases": [host, dict(host)]},
    )

    assert result["status"] == "incomplete"
    assert result["reason"] == "networkgroup_dependency_incomplete"


def test_disabled_alias_old_pf_table_does_not_confirm_active_state():
    class Diagnostics(FixedCollectionTransport):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.calls = 0

        def _request(self, method, path, payload=None):
            self.calls += 1
            if path == "firewall/alias_util/aliases":
                return ["NETS"]
            return {"rows": [{"ip": "192.0.2.10"}], "total": 1}

    desired = {
        "name": "NETS", "type": "host", "content": ["192.0.2.10"],
        "state": "present", "enabled": False,
    }
    diagnostics = Diagnostics(
        {"host": "fw", "endpoint": "https://fw.example", "ssl_verify": True}, {}
    )
    result = diagnostics.active_check("aliases", ["NETS"], desired)
    assert result["status"] == "unsupported"
    assert result["reason"] == "native_retirement_and_consumers_unconfirmed"
    assert result["coverage"]["table"] == "residual_nonempty"
    assert diagnostics.calls == 2


@pytest.mark.parametrize('resource,field', [
    ('dnat', 'nosync'), ('vips', 'nosync'), ('gateways', 'nosync'),
    ('gateways', 'monitor_killstates'), ('gateways', 'monitor_killstates_priority'),
    ('filter-rules', 'nosync'), ('filter-rules', 'nopfsync'),
    ('filter-rules', 'received-on-not'), ('filter-rules', 'tcpflags_any'), ('aliases', 'counters'),
])
def test_native_disabled_flags_are_neutral_but_enabled_flags_block(resource, field):
    for value in ('0', 0, 0.0, False, 'No', 'off', ''):
        transport = FakeCollection()
        transport.rows[resource][0][field] = value
        obj = reader(transport).read([resource])[resource]['objects'][0]
        assert obj['configuration'] is not None, obj['reason']
    for value in ('1', True, 'unexpected', 2.0, [], {}):
        transport.rows[resource][0][field] = value
        obj = reader(transport).read([resource])[resource]['objects'][0]
        assert obj['configuration'] is None
        assert field in obj['reason']


@pytest.mark.parametrize('resource,field,multiple', [
    ('aliases', 'authtype', False), ('aliases', 'proto', True),
    ('filter-rules', 'icmp_type', True), ('filter-rules', 'icmpv6_type', True),
    ('filter-rules', 'tcp_flags', True), ('filter-rules', 'tcp_flags_clear', True),
    ('filter-rules', 'received-on', True), ('filter-rules', 'divert_to', False),
    ('filter-rules', 'shaper1', False), ('filter-rules', 'shaper2', False),
])
def test_native_selectors_decode_empty_and_reject_active_values(resource, field, multiple):
    transport = FakeCollection()
    transport.rows[resource][0][field] = {
        '': {'value': 'None', 'selected': 0 if multiple else 1},
        'feature': {'value': 'Display label', 'selected': 0},
    }
    obj = reader(transport).read([resource])[resource]['objects'][0]
    assert obj['configuration'] is not None, obj['reason']
    transport.rows[resource][0][field]['']['selected'] = 0
    transport.rows[resource][0][field]['feature']['selected'] = 1
    obj = reader(transport).read([resource])[resource]['objects'][0]
    assert obj['configuration'] is None
    assert field in obj['reason']


def test_volatile_fields_are_scoped_and_not_configuration():
    transport = FakeCollection()
    transport.rows['aliases'][0]['current_items'] = '42'
    transport.rows['filter-rules'][0].update(sort_order='1000001', prio_group='200')
    for resource in ('aliases', 'filter-rules'):
        assert reader(transport).read([resource])[resource]['objects'][0]['configuration'] is not None
    transport.rows['dnat'][0]['current_items'] = '42'
    assert reader(transport).read(['dnat'])['dnat']['objects'][0]['configuration'] is None


def test_addressless_gateway_is_enumerated_but_not_manageable():
    transport = FakeCollection()
    transport.rows['gateways'][0].update(gateway='', uuid='native-gateway')
    obs = reader(transport).read(['gateways'])['gateways']
    assert obs['status'] == 'complete'
    obj = obs['objects'][0]
    assert obj['identity'] == ['native:native-gateway']
    assert obj['label'] == 'gateways:WAN'
    assert obj['configuration'] is None
    assert obj['recovery'] == 'manual_required'
    del transport.rows['gateways'][0]['uuid']
    assert reader(transport).read(['gateways'])['gateways']['status'] == 'incomplete'


def test_empty_optional_nogroup_is_false_but_empty_members_remain_unknown():
    transport = FakeCollection()
    row = transport.rows['interface-groups'][0]
    row.pop('gui_group', None)
    row['nogroup'] = ''
    obj = reader(transport).read(['interface-groups'])['interface-groups']['objects'][0]
    assert obj['configuration']['gui_group'] is True
    row['members'] = []
    obj = reader(transport).read(['interface-groups'])['interface-groups']['objects'][0]
    assert obj['configuration'] is None


def test_unrelated_addressless_gateway_does_not_block_alias_plan_but_dependency_does():
    rows = {name: [] for name in ROWS}
    rows['aliases'] = deepcopy(ROWS['aliases'])
    rows['gateways'] = [ROWS['gateways'][0] | {'gateway': '', 'uuid': 'dynamic-native'}]
    assert _plan_alias_deletion(rows)['admission']['status'] != 'blocked'
    rows['filter-rules'] = [ROWS['filter-rules'][0] | {'gateway': 'WAN'}]
    observations = reader(FakeCollection(rows)).read(list(COLLECTION_TARGETS))
    with pytest.raises(ValidationError, match='dependency|express'):
        plan({'filter-rules': {'opnsense_filter_rules': [observations['filter-rules']['objects'][0]['configuration']]}},
             {'schema_version': 1, 'selection': {'filter-rules': 'all'},
              'managed': {'filter-rules': [observations['filter-rules']['objects'][0]['identity']]}}, observations,
             TARGET, {}, {})


def test_live_alias_statistics_do_not_hide_configured_expiration():
    transport = FakeCollection()
    stats = dict.fromkeys(('eval_match', 'eval_nomatch', 'in_block_b', 'in_block_p',
                          'in_pass_b', 'in_pass_p', 'out_block_b', 'out_block_p',
                          'out_pass_b', 'out_pass_p'), '123')
    transport.rows['aliases'][0].update(stats)
    obj = reader(transport).read(['aliases'])['aliases']['objects'][0]
    assert obj['configuration'] is not None
    assert not set(stats) & obj['configuration'].keys()
    transport.rows['aliases'][0]['expire'] = '300'
    obj = reader(transport).read(['aliases'])['aliases']['objects'][0]
    assert obj['reason'] == 'unexpressed_native_fields:unknown_native_field'


def test_filter_display_text_does_not_replace_network_identifiers():
    transport = FakeCollection()
    row = transport.rows['filter-rules'][0]
    row.update({'%source_net': 'Friendly source address', '%destination_net': 'Friendly alias label'})
    obj = reader(transport).read(['filter-rules'])['filter-rules']['objects'][0]
    assert obj['configuration']['destination_net'] == ['NETS']
    assert 'aliases:NETS' in obj['references']
    row['%unsupported_feature'] = 'display-like but unknown'
    obj = reader(transport).read(['filter-rules'])['filter-rules']['objects'][0]
    assert obj['reason'] == 'unexpressed_native_fields:unknown_native_field'


def test_empty_alias_frequency_is_only_omitted_for_non_urltable():
    transport = FakeCollection()
    row = transport.rows['aliases'][0]
    row['updatefreq'] = ''
    obj = reader(transport).read(['aliases'])['aliases']['objects'][0]
    assert obj['configuration'] is not None
    assert 'updatefreq_days' not in obj['configuration']
    row['updatefreq'] = '1'
    assert reader(transport).read(['aliases'])['aliases']['objects'][0]['configuration'] is None
    row.update(type='urltable', content=['https://example.invalid/addresses'], updatefreq='')
    assert reader(transport).read(['aliases'])['aliases']['objects'][0]['configuration'] is None
    row['updatefreq'] = '1'
    assert reader(transport).read(['aliases'])['aliases']['objects'][0]['configuration']['updatefreq_days'] == '1'


def test_native_csv_filter_networks_and_ports_are_validated_as_lists():
    transport = FakeCollection()
    row = transport.rows['filter-rules'][0]
    row.update(destination_net='NETS,192.0.2.0/24', source_net='OTHER,198.51.100.1',
               source_port='1024,1025', destination_port='443,8443')
    obj = reader(transport).read(['filter-rules'])['filter-rules']['objects'][0]
    assert obj['configuration']['destination_net'] == ['192.0.2.0/24', 'NETS']
    assert obj['configuration']['source_net'] == ['198.51.100.1', 'OTHER']
    assert obj['configuration']['destination_port'] == ['443', '8443']
    assert {'aliases:NETS', 'aliases:OTHER'} <= set(obj['references'])
    row['destination_invert'] = True
    assert reader(transport).read(['filter-rules'])['filter-rules']['objects'][0]['configuration'] is None
