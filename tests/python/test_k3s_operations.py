"""Offline safety checks for K3s mutation-operation selectors."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.common.io import load_yaml
from iaas_automation.k3s_automation.config import build_composed_model
from iaas_automation.k3s_automation.operations import (
    UpgradePlan,
    validate_deployment_scope,
    validate_exact_scope,
    validate_upgrade,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "k3s"


def composed_model() -> dict[str, Any]:
    intent = copy.deepcopy(load_yaml(FIXTURES / "intent.yml"))
    inventory = copy.deepcopy(load_yaml(FIXTURES / "generated-pve.yml"))
    return build_composed_model(intent, inventory)


ALL_NODES = "synthetic-server-01,synthetic-server-02,synthetic-server-03,synthetic-agent-01"
OBSERVED_OLD = {
    "synthetic-server-01": "v1.34.0+k3s1",
    "synthetic-server-02": "v1.34.0+k3s1",
    "synthetic-server-03": "v1.34.0+k3s1",
    "synthetic-agent-01": "v1.34.0+k3s1",
}
TARGET = "v1.35.1+k3s1"


def test_exact_scope_accepts_declared_comma_separated_nodes() -> None:
    model = composed_model()

    assert validate_exact_scope(model, ALL_NODES) == tuple(ALL_NODES.split(","))


@pytest.mark.parametrize(
    "scope",
    [
        "",
        "*",
        "all",
        "synthetic-server-01,*",
        "synthetic-server-01,synthetic-server-01",
        "synthetic-server-01,unknown-node",
        "synthetic-server-01, synthetic-server-02",
    ],
)
def test_exact_scope_rejects_implicit_wildcards_duplicates_unknowns_and_spacing(scope: str) -> None:
    with pytest.raises(ValidationError, match="scope"):
        validate_exact_scope(composed_model(), scope)


def test_deployment_requires_the_whole_composed_cluster_scope() -> None:
    model = composed_model()

    assert validate_deployment_scope(model, ALL_NODES) == tuple(ALL_NODES.split(","))
    with pytest.raises(ValidationError, match="whole cluster|all declared"):
        validate_deployment_scope(model, "synthetic-server-01,synthetic-server-02")


def test_upgrade_requires_explicit_whole_cluster_scope() -> None:
    with pytest.raises(ValidationError, match="whole cluster|all declared"):
        validate_upgrade(
            composed_model(),
            "synthetic-server-01,synthetic-server-02,synthetic-server-03",
            OBSERVED_OLD,
            TARGET,
        )


def test_upgrade_accepts_one_minor_step_and_orders_servers_before_agents() -> None:
    plan = validate_upgrade(composed_model(), ALL_NODES, OBSERVED_OLD, TARGET)

    assert isinstance(plan, UpgradePlan)
    assert plan.target_version == TARGET
    assert plan.skipped == ()
    assert plan.to_upgrade == (
        "synthetic-server-01",
        "synthetic-server-02",
        "synthetic-server-03",
        "synthetic-agent-01",
    )


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("v1.33.9+k3s1", "downgrade"),
        ("v1.36.0+k3s1", "skipped-minor"),
        ("v2.35.1+k3s1", "unsupported"),
    ],
)
def test_upgrade_rejects_unsafe_version_transitions(target: str, expected: str) -> None:
    with pytest.raises(ValidationError, match=expected):
        validate_upgrade(composed_model(), ALL_NODES, OBSERVED_OLD, target)


def test_upgrade_rejects_unsupported_mixed_prior_versions() -> None:
    observed = dict(OBSERVED_OLD)
    observed["synthetic-agent-01"] = "v1.34.1+k3s1"

    with pytest.raises(ValidationError, match="mixed"):
        validate_upgrade(composed_model(), ALL_NODES, observed, TARGET)


def test_upgrade_resume_skips_exact_target_and_continues_remaining_nodes() -> None:
    observed = dict(OBSERVED_OLD)
    observed["synthetic-server-01"] = TARGET
    observed["synthetic-agent-01"] = TARGET

    plan = validate_upgrade(composed_model(), ALL_NODES, observed, TARGET)

    assert plan.skipped == ("synthetic-server-01", "synthetic-agent-01")
    assert plan.to_upgrade == (
        "synthetic-server-02",
        "synthetic-server-03",
    )


def test_upgrade_rejects_node_above_target_before_mutation() -> None:
    observed = dict(OBSERVED_OLD)
    observed["synthetic-server-01"] = "v1.35.2+k3s1"

    with pytest.raises(ValidationError, match="above target|downgrade"):
        validate_upgrade(composed_model(), ALL_NODES, observed, TARGET)
