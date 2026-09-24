from iaas.opnsense_workflow.group_checks import check_interface_group_current


DESIRED = {"name": "inside", "members": ["lan", "opt1"]}
OVERVIEW = [
    {"identifier": "lan", "device": "igb0"},
    {"identifier": "opt1", "device": "vlan10"},
    {"identifier": "", "device": "igb1"},  # unassigned overview row
]
IFCONFIG = {
    "igb0": {"groups": ["inside", "other"]},
    "vlan10": {"groups": ["inside"]},
    "igb1": {"groups": []},
}


def test_group_current_maps_logical_members_and_checks_exact_device_set():
    result = check_interface_group_current(DESIRED, OVERVIEW, IFCONFIG)

    assert result["status"] == "verified"
    assert result["scope"] == "current_state"
    assert result["expected"]["physical_members"] == ["igb0", "vlan10"]
    assert result["observed"]["group_members"] == ["igb0", "vlan10"]
    assert result["consumer"] == {
        "status": "unsupported",
        "reason": "filter_consumption_unobserved",
    }
    assert result["completion"] == {
        "status": "unknown",
        "reason": "group_reconfigure_not_correlated",
    }


def test_group_current_can_confirm_current_scope_when_consumer_is_inapplicable():
    result = check_interface_group_current(
        DESIRED,
        OVERVIEW,
        IFCONFIG,
        {"status": "not_applicable", "reason": "no_loaded_group_consumer"},
    )

    assert result["status"] == "verified"
    assert result["current_status"] == "verified"
    assert result["consumer"]["status"] == "not_applicable"
    assert result["completion"]["status"] == "unknown"


def test_group_current_keeps_consumer_failure_separate_but_failing():
    result = check_interface_group_current(
        DESIRED,
        OVERVIEW,
        IFCONFIG,
        {"status": "failed", "reason": "loaded_group_rule_mismatch"},
    )

    assert result["status"] == "failed"
    assert result["current_status"] == "verified"
    assert result["consumer"]["status"] == "failed"


def test_group_current_accepts_complete_overview_rows_response():
    overview = {"current": 1, "rowCount": 3, "total": 3, "rows": OVERVIEW}

    assert check_interface_group_current(DESIRED, overview, IFCONFIG)["status"] == "verified"


def test_group_current_reports_complete_membership_mismatch_as_failed():
    ifconfig = {
        "igb0": {"groups": ["inside"]},
        "vlan10": {"groups": []},
        "igb1": {"groups": ["inside"]},
    }

    result = check_interface_group_current(DESIRED, OVERVIEW, ifconfig)

    assert result["status"] == "failed"
    assert result["reason"] == "current_group_membership_mismatch"
    assert result["observed"]["group_members"] == ["igb0", "igb1"]


def test_group_current_returns_unknown_for_unmapped_logical_member():
    result = check_interface_group_current(DESIRED, [{"identifier": "lan", "device": "igb0"}], IFCONFIG)

    assert result["status"] == "unknown"
    assert result["reason"] == "logical_interface_unmapped"


def test_group_current_returns_unknown_for_ambiguous_mapping():
    overview = [
        {"identifier": "lan", "device": "igb0"},
        {"identifier": "lan", "device": "igb1"},
    ]

    result = check_interface_group_current(DESIRED, overview, IFCONFIG)

    assert result["status"] == "unknown"
    assert result["reason"] == "ambiguous_logical_interface_mapping"


def test_group_current_returns_unknown_for_incomplete_overview():
    overview = {"current": 1, "rowCount": 1, "total": 2, "rows": OVERVIEW[:1]}

    result = check_interface_group_current(DESIRED, overview, IFCONFIG)

    assert result["status"] == "unknown"
    assert result["reason"] == "incomplete_interface_overview"


def test_group_current_returns_unknown_for_bad_diagnostic_group_shape():
    ifconfig = {"igb0": {"groups": "inside"}, "vlan10": {"groups": []}}

    result = check_interface_group_current(DESIRED, OVERVIEW, ifconfig)

    assert result["status"] == "unknown"
    assert result["reason"] == "interface_groups_unavailable"


def test_group_current_returns_unknown_for_malformed_diagnostic_row():
    ifconfig = {"igb0": {"groups": ["inside"]}, "vlan10": None}

    result = check_interface_group_current(DESIRED, OVERVIEW, ifconfig)

    assert result["status"] == "unknown"
    assert result["reason"] == "malformed_interface_diagnostics_row"


def test_group_current_does_not_treat_missing_diagnostics_device_as_absent():
    ifconfig = {"igb0": {"groups": ["inside"]}}

    result = check_interface_group_current(DESIRED, OVERVIEW, ifconfig)

    assert result["status"] == "unknown"
    assert result["reason"] == "diagnostic_interface_missing"
