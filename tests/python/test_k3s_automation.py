"""Focused synthetic tests for composed K3s automation intent."""

from __future__ import annotations

import copy
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.common.io import load_yaml
from iaas_automation.k3s_automation.config import build_composed_model, render_review
from iaas_automation.k3s_automation.cli import main as k3s_main


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "k3s"
INTENT_PATH = FIXTURES / "intent.yml"
INVENTORY_PATH = FIXTURES / "generated-pve.yml"
EXPECTED_REVIEW_PATH = FIXTURES / "expected-review.yml"


def valid_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    return copy.deepcopy(load_yaml(INTENT_PATH)), copy.deepcopy(load_yaml(INVENTORY_PATH))


def test_valid_intent_composes_vm_owned_facts() -> None:
    intent, inventory = valid_documents()

    model = build_composed_model(intent, inventory)

    first = model["nodes"][0]
    assert first["vm_ref"] == "synthetic-server-01"
    assert first["ansible_host"] == "192.0.2.11"
    assert first["node_nic"] == "cluster0"
    assert first["node_ip"] == "198.51.100.11"
    assert first["architecture"] == "amd64"
    assert model["cluster"]["api_endpoint"]["address"] == "198.51.100.11"
    assert model["cluster"]["api_endpoint"]["tls_sans"] == []
    assert "198.51.100.0/24" in model["cluster"]["service_proxy"]["no_proxy"]
    assert model["cluster"]["artifacts"]["amd64"]["proxy_url"] == (
        "http://artifact-proxy.synthetic.invalid:3128"
    )
    assert model["cluster"]["registry"]["mirrors"][0]["rewrites"] == {
        "^rancher/(.*)": "mirror/rancher/$1"
    }
    assert model["cluster"]["registry"]["mirrors"][0]["ca_ref"] == (
        "op://synthetic/registry/ca-pem"
    )
    assert model["cluster"]["registry"]["mirrors"][0]["client_key_ref"] == (
        "op://synthetic/registry/client-key-pem"
    )


def test_review_render_is_deterministic_and_contains_references_not_values() -> None:
    intent, inventory = valid_documents()
    model = build_composed_model(intent, inventory)

    first = render_review(model)
    second = render_review(model)

    assert first == second
    assert first == EXPECTED_REVIEW_PATH.read_text(encoding="utf-8")
    assert "op://synthetic/k3s/server-token" in first
    assert "synthetic-secret-value" not in first


def test_synthetic_fixtures_do_not_copy_vm_owned_facts_or_real_hosts() -> None:
    intent, _inventory = valid_documents()

    assert all(set(node) == {"vm_ref", "role", "bootstrap"} for node in intent["nodes"])
    assert all(node["vm_ref"].startswith("synthetic-") for node in intent["nodes"])
    assert "astra" not in INTENT_PATH.read_text(encoding="utf-8").lower()


def test_service_proxy_explicit_retirement_is_valid() -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["service_proxy"] = {"state": "absent", "extra_no_proxy": []}

    model = build_composed_model(intent, inventory)

    assert model["cluster"]["service_proxy"]["state"] == "absent"
    assert model["cluster"]["service_proxy"]["url"] is None
    assert model["cluster"]["service_proxy"]["credential_ref"] is None


def test_per_node_vm_fact_override_is_rejected() -> None:
    intent, inventory = valid_documents()
    intent["nodes"][0]["node_ip"] = "203.0.113.9"

    with pytest.raises(ValidationError, match="unknown keys node_ip"):
        build_composed_model(intent, inventory)


def test_missing_or_ambiguous_node_network_role_is_rejected() -> None:
    intent, inventory = valid_documents()
    host = inventory["all"]["children"]["pve_vms"]["hosts"]["synthetic-server-01"]
    host["pve_nics"][1]["role"] = "storage"

    with pytest.raises(ValidationError, match="exactly one NIC with role cluster"):
        build_composed_model(intent, inventory)

    host["pve_nics"][0]["role"] = "cluster"
    host["pve_nics"][1]["role"] = "cluster"
    with pytest.raises(ValidationError, match="exactly one NIC with role cluster"):
        build_composed_model(intent, inventory)


def test_connection_nic_must_be_unique_and_match_ansible_host() -> None:
    intent, inventory = valid_documents()
    host = inventory["all"]["children"]["pve_vms"]["hosts"]["synthetic-server-01"]
    host["pve_nics"][0]["ansible_connection"] = False
    with pytest.raises(ValidationError, match="exactly one ansible_connection NIC"):
        build_composed_model(intent, inventory)

    intent, inventory = valid_documents()
    host = inventory["all"]["children"]["pve_vms"]["hosts"]["synthetic-server-01"]
    host["pve_nics"][0]["ip_address"] = "192.0.2.99"
    with pytest.raises(ValidationError, match="must match ansible_host"):
        build_composed_model(intent, inventory)

@pytest.mark.parametrize("role", ["storage", "ingress"])
def test_storage_and_ingress_cannot_supply_node_identity(role: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["node_network_role"] = role

    with pytest.raises(ValidationError, match="node_network_role"):
        build_composed_model(intent, inventory)


def test_artifact_map_must_cover_derived_architecture() -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["artifacts"] = {}

    with pytest.raises(ValidationError, match="artifacts.*amd64"):
        build_composed_model(intent, inventory)


def test_embedded_etcd_rejects_two_servers() -> None:
    intent, inventory = valid_documents()
    intent["nodes"] = [intent["nodes"][0], intent["nodes"][1], intent["nodes"][3]]

    with pytest.raises(ValidationError, match="one or an odd number of at least three servers"):
        build_composed_model(intent, inventory)


def test_fixed_endpoint_is_derived_into_tls_sans_and_cannot_repeat_node_ip() -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["api_endpoint"] = {"mode": "fixed", "address": "api.synthetic.invalid"}

    model = build_composed_model(intent, inventory)
    assert model["cluster"]["api_endpoint"] == {
        "mode": "fixed",
        "address": "api.synthetic.invalid",
        "tls_sans": ["api.synthetic.invalid"],
    }

    intent["cluster"]["api_endpoint"]["address"] = "198.51.100.11"
    with pytest.raises(ValidationError, match="must not repeat a selected node IP"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize("address", ["0.0.0.0", "127.0.0.1", "224.0.0.1", "169.254.1.1"])
def test_fixed_endpoint_rejects_non_unicast_addresses(address: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["api_endpoint"] = {"mode": "fixed", "address": address}

    with pytest.raises(ValidationError, match="stable unicast"):
        build_composed_model(intent, inventory)


def test_cluster_ranges_cannot_overlap_vm_networks() -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["networking"]["pod_cidr"] = "198.51.100.0/24"

    with pytest.raises(ValidationError, match="must not overlap VM subnet"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize("node_ip", ["198.51.100.0", "198.51.100.255"])
def test_node_identity_rejects_ipv4_network_and_broadcast_addresses(node_ip: str) -> None:
    intent, inventory = valid_documents()
    host = inventory["all"]["children"]["pve_vms"]["hosts"]["synthetic-server-01"]
    host["pve_nics"][1]["ip_address"] = node_ip

    with pytest.raises(ValidationError, match="usable host address"):
        build_composed_model(intent, inventory)


def test_plaintext_secret_registry_tls_and_global_bypass_are_rejected() -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["server_token_ref"] = "synthetic-secret-value"
    with pytest.raises(ValidationError, match="server_token_ref.*op://"):
        build_composed_model(intent, inventory)

    intent, inventory = valid_documents()
    intent["cluster"]["registry"]["mirrors"][0]["endpoint"] = "http://registry.synthetic.invalid"
    with pytest.raises(ValidationError, match="endpoint.*HTTPS"):
        build_composed_model(intent, inventory)

    intent, inventory = valid_documents()
    intent["cluster"]["service_proxy"]["extra_no_proxy"] = ["0.0.0.0/0"]
    with pytest.raises(ValidationError, match="overbroad network bypass"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize("bypass", ["0.0.0.0/1", "128.0.0.0/1", "com"])
def test_no_proxy_rejects_overbroad_networks_and_naked_suffixes(bypass: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["service_proxy"]["extra_no_proxy"] = [bypass]

    with pytest.raises(ValidationError, match="extra_no_proxy"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize(
    "secret_ref",
    [
        "op://vault",
        "op:///item/field",
        "op://vault/item",
        "op://plaintext-secret@vault/item/field",
        "op://vault:123/item/field",
        "op://vault/item/section/field/extra",
        "op://vault/item//field",
    ],
)
def test_external_secret_reference_requires_vault_item_and_field(secret_ref: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["server_token_ref"] = secret_ref

    with pytest.raises(ValidationError, match="server_token_ref.*op://"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize(
    "url",
    [
        "https://artifacts.synthetic.invalid:invalid/k3s",
        "https://artifacts.synthetic.invalid:0/k3s",
        "https://artifacts.synthetic.invalid/k3s?token=plaintext",
        "https://artifacts.synthetic.invalid/k3s#fragment",
    ],
)
def test_artifact_url_rejects_invalid_or_secret_bearing_forms(url: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["artifacts"]["amd64"]["url"] = url

    with pytest.raises(ValidationError, match="artifacts.amd64.url"):
        build_composed_model(intent, inventory)


def test_artifact_url_must_use_the_exact_declared_k3s_version_path() -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["artifacts"]["amd64"]["url"] = (
        "https://artifacts.synthetic.invalid/k3s/v1.34.9+k3s1/amd64/k3s"
    )

    with pytest.raises(ValidationError, match="exact cluster.version"):
        build_composed_model(intent, inventory)


def test_registry_name_and_rewrite_regex_are_validated() -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["registry"]["mirrors"][0]["registry"] = "https://docker.io"
    with pytest.raises(ValidationError, match="registry"):
        build_composed_model(intent, inventory)

    intent, inventory = valid_documents()
    intent["cluster"]["registry"]["mirrors"][0]["rewrites"] = {"[invalid": "target"}
    with pytest.raises(ValidationError, match="rewrites"):
        build_composed_model(intent, inventory)

    intent, inventory = valid_documents()
    intent["cluster"]["registry"]["mirrors"][0]["rewrites"] = {
        "^(?=rancher/)": "mirror/rancher/$1"
    }
    with pytest.raises(ValidationError, match="RE2-compatible"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize(
    "pattern",
    [r"foo\Z", r"foo\N{LATIN CAPITAL LETTER A}", r"foo\u0041", r"foo\U00000041"],
)
def test_registry_rewrite_rejects_python_only_regex_syntax(pattern: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["registry"]["mirrors"][0]["rewrites"] = {pattern: "mirror/path"}

    with pytest.raises(ValidationError, match="RE2-compatible"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize(
    ("pattern", "replacement"),
    [
        ("a", "mirror"),
        ("rancher.io/(.*)", "mirror/$1"),
        ("^../(.*)", "../$1"),
    ],
)
def test_registry_rewrite_is_anchored_literal_and_path_bounded(pattern: str, replacement: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["registry"]["mirrors"][0]["rewrites"] = {pattern: replacement}

    with pytest.raises(ValidationError, match="rewrites"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize("registry", ["docker", "bad_host", "-bad.example", "a..b", "127.0.0.999"])
def test_registry_name_must_be_a_recognizable_valid_host_or_host_port(registry: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["registry"]["mirrors"][0]["registry"] = registry

    with pytest.raises(ValidationError, match="registry"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize(
    "missing_key",
    ["ca_ref", "ca_sha256", "client_cert_ref", "client_cert_sha256", "client_key_ref"],
)
def test_registry_tls_material_requires_complete_external_identity(missing_key: str) -> None:
    intent, inventory = valid_documents()
    del intent["cluster"]["registry"]["mirrors"][0][missing_key]

    with pytest.raises(ValidationError, match="TLS material"):
        build_composed_model(intent, inventory)


def test_component_duplicates_and_mixed_cluster_address_families_are_rejected() -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["components"]["disable"].append("traefik")
    with pytest.raises(ValidationError, match="disable.*duplicate"):
        build_composed_model(intent, inventory)

    intent, inventory = valid_documents()
    intent["cluster"]["networking"]["service_cidr"] = "fd00:43::/112"
    with pytest.raises(ValidationError, match="same address family"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize("service_cidr", ["10.0.0.0/8", "fd00:43::/64"])
def test_service_cidr_rejects_ranges_larger_than_k3s_supports(service_cidr: str) -> None:
    intent, inventory = valid_documents()
    if ":" in service_cidr:
        intent["cluster"]["networking"]["pod_cidr"] = "fd00:42::/64"
    intent["cluster"]["networking"]["service_cidr"] = service_cidr

    with pytest.raises(ValidationError, match="service_cidr.*maximum supported size"):
        build_composed_model(intent, inventory)


def test_single_stack_cluster_cidrs_must_match_derived_node_address_family() -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["networking"]["pod_cidr"] = "fd00:42::/64"
    intent["cluster"]["networking"]["service_cidr"] = "fd00:43::/112"

    with pytest.raises(ValidationError, match="node IPs must use the cluster address family"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize("bypass", ["8.0.0.0/8", "2001:4860::/32"])
def test_no_proxy_rejects_broad_public_networks(bypass: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["service_proxy"]["extra_no_proxy"] = [bypass]

    with pytest.raises(ValidationError, match="overbroad public network bypass"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize(
    "version",
    ["v1.26.12+k3s1", "v1.27.9+k3s1", "v1.28.5+k3s1", "v1.29.0+k3s1"],
)
def test_registry_fallback_deny_rejects_unsupported_k3s_versions(version: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["version"] = version

    with pytest.raises(ValidationError, match="fallback deny.*version"):
        build_composed_model(intent, inventory)


@pytest.mark.parametrize(
    "directory",
    ["/var/lib/rancher/k3s/../outside", "/var/lib/rancher/k3s/server/tls"],
)
def test_snapshot_directory_is_derived_and_cannot_be_overridden(directory: str) -> None:
    intent, inventory = valid_documents()
    intent["cluster"]["snapshot"]["directory"] = directory

    with pytest.raises(ValidationError, match="snapshot.*unknown keys directory"):
        build_composed_model(intent, inventory)


def test_cli_validates_and_renders_review(tmp_path: Path) -> None:
    review_path = tmp_path / "review.yml"

    assert k3s_main(["--intent", str(INTENT_PATH), "--inventory", str(INVENTORY_PATH)]) == 0
    assert k3s_main(["--intent", str(INTENT_PATH), "--inventory", str(INVENTORY_PATH), "--render", str(review_path)]) == 0
    assert review_path.read_text(encoding="utf-8") == render_review(build_composed_model(*valid_documents()))


def test_cli_validation_failure_is_concise() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "automation" / "src")
    result = subprocess.run(
        [sys.executable, "-m", "iaas_automation.k3s_automation", "--intent", "/missing/intent.yml", "--inventory", str(INVENTORY_PATH)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.startswith("FAIL validation:")
    assert "Traceback" not in result.stderr


def test_makefile_exposes_only_explicit_offline_k3s_entrypoints() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "k3s-check:" in makefile
    assert "k3s-render:" in makefile
    assert "K3S_INTENT" in makefile
    assert "K3S_INVENTORY" in makefile
    check_line = next(line for line in makefile.splitlines() if line.startswith("check:"))
    assert "k3s-" not in check_line


def test_cli_scope_is_limited_to_explicit_composed_nodes() -> None:
    assert k3s_main([
        "--intent", str(FIXTURES / "intent.yml"),
        "--inventory", str(FIXTURES / "generated-pve.yml"),
        "--scope", "synthetic-server-01,synthetic-server-02",
    ]) == 0

    with pytest.raises(ValidationError, match="wildcards"):
        k3s_main([
            "--intent", str(FIXTURES / "intent.yml"),
            "--inventory", str(FIXTURES / "generated-pve.yml"),
            "--scope", "*",
        ])
