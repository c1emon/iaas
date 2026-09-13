from copy import deepcopy
from pathlib import Path
import os
import subprocess
import sys

import pytest
import yaml

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_validation import validate_document, validate_documents
from iaas_automation.runtime_config import load_environment
from iaas_automation.runtime_config.compile import compile_documents

ROOT = Path(__file__).resolve().parents[2]


def declarations():
    aliases = [dict(name="LOCAL_NETS", type="network", content=["192.0.2.0/24"],
                    description="Reviewed ingress networks", enabled=True, state="present")]
    rules = [dict(scope="lan", slug="deny-outside", state="present", enabled=True,
                  sequence=100, interface=["lan"], direction="in", action="block", quick=True,
                  ip_protocol="inet", protocol="any", source_net="any",
                  destination_net="LOCAL_NETS", destination_invert=True)]
    return {"aliases": {"opnsense_aliases": aliases}, "filter-rules": {
        "opnsense_filter_rules": rules, "opnsense_filter_rule_context": {
            "interface_networks": {"lan": ["192.0.2.0/24"]}, "aliases": deepcopy(aliases)}}}


@pytest.mark.parametrize("family,networks,valid", [
    ("inet", ["192.0.2.0/24"], True),
    ("inet", ["192.0.2.0/24", "2001:db8::/64"], True),
    ("inet46", ["192.0.2.0/24"], False),
    ("inet6", ["192.0.2.0/24"], False),
    ("inet6", ["2001:db8::/64"], False),
    ("inet", ["198.51.100.0/24"], False),
])
def test_family_coverage(family, networks, valid):
    doc = declarations()["filter-rules"]
    doc["opnsense_filter_rules"][0]["ip_protocol"] = family
    doc["opnsense_filter_rule_context"]["interface_networks"]["lan"] = networks
    if valid:
        validate_document("filter-rules", doc)
    else:
        with pytest.raises(ValidationError, match="deny rule"):
            validate_document("filter-rules", doc)


def test_dual_family_and_mixed_dynamic_members():
    doc = declarations()["filter-rules"]
    context = doc["opnsense_filter_rule_context"]
    context["aliases"][0]["content"].append("2001:db8::/64")
    context["interface_networks"]["lan"].append("2001:db8::/64")
    context["aliases"].append(dict(name="COMBINED", type="networkgroup",
        content=["LOCAL_NETS", "EXTERNAL_DYNAMIC"], description="Group", enabled=True, state="present"))
    doc["opnsense_filter_rules"][0].update(ip_protocol="inet46", destination_net="COMBINED")
    validate_document("filter-rules", doc)
    context["aliases"][1]["content"] = ["EXTERNAL_DYNAMIC"]
    with pytest.raises(ValidationError, match="deny rule"):
        validate_document("filter-rules", doc)


def test_context_shape_conflicts_and_missing_evidence():
    docs = declarations()
    validate_documents(docs)
    docs["aliases"]["opnsense_aliases"][0]["enabled"] = False
    with pytest.raises(ValidationError, match="conflicts"):
        validate_documents(docs)
    doc = declarations()["filter-rules"]
    doc["opnsense_filter_rule_context"]["safe"] = True
    with pytest.raises(ValidationError, match="unknown keys"):
        validate_document("filter-rules", doc)
    del doc["opnsense_filter_rule_context"]
    with pytest.raises(ValidationError, match="deny rule"):
        validate_document("filter-rules", doc)


def test_generated_standard_files_use_normal_runtime(tmp_path):
    docs = declarations()
    docs["aliases"]["opnsense_aliases"].append(dict(name="REVIEW_GROUP", type="networkgroup",
        content=["LOCAL_NETS"], description="Generated group", enabled=True, state="present"))
    for name, doc in docs.items():
        (tmp_path / f"{name}.yml").write_text(yaml.safe_dump(doc))
    env = tmp_path / "environment.yml"
    env.write_text(yaml.safe_dump(dict(schema_version=1, environment="lab", components={
        "opnsense": {"inputs": {name: f"{name}.yml" for name in docs}}})))
    output = compile_documents(load_environment(env, "opnsense"))
    assert {name: yaml.safe_load(value) for name, value in output.items()} == {
        f"{name}.yml": doc for name, doc in docs.items()}
    docs["aliases"]["opnsense_aliases"][0]["enabled"] = False
    (tmp_path / "aliases.yml").write_text(yaml.safe_dump(docs["aliases"]))
    with pytest.raises(ValidationError):
        compile_documents(load_environment(env, "opnsense"))


def test_high_level_policy_is_not_a_runtime_input(tmp_path):
    (tmp_path / "policy.yml").write_text("schema_version: 1\n")
    env = tmp_path / "environment.yml"
    env.write_text(yaml.safe_dump(dict(schema_version=1, environment="lab", components={
        "opnsense": {"inputs": {"selective-proxy": "policy.yml"}}})))
    with pytest.raises(ValidationError):
        compile_documents(load_environment(env, "opnsense"))


@pytest.mark.parametrize("patch,valid", [({}, True), ({"sequence": "100"}, False),
    ({"sequence": True}, False), ({"enabled": "true"}, False), ({"enabled": 1}, False),
    ({"source_net": ["192.0.2.1", "192.0.2.2"], "source_invert": True}, False),
    ({"destination_net": ["LOCAL_NETS", "OTHER"]}, False)])
def test_real_ansible_loaded_admission(tmp_path, patch, valid):
    doc = declarations()["filter-rules"]
    doc["opnsense_filter_rules"][0].update(patch)
    source = tmp_path / "rules.yml"
    source.write_text(yaml.safe_dump(doc))
    # Execute the actual source loading and admission tasks, stopping before credentials.
    original = yaml.safe_load((ROOT / "automation/ansible/playbooks/opnsense/manage-filter-rules.yml").read_text())[0]
    tasks = original["tasks"] if "tasks" in original else original["pre_tasks"]
    load = next(task for task in tasks if task["name"] == "Load desired OPNsense new filter rules")
    check = next(task for task in tasks if task["name"].startswith("Revalidate loaded rules"))
    assert tasks.index(check) < next(i for i, task in enumerate(tasks) if "credential preflight" in task["name"])
    play = tmp_path / "check.yml"
    play.write_text(yaml.safe_dump([dict(hosts="localhost", gather_facts=False, connection="local",
        vars={"opnsense_filter_rule_source": str(source)}, tasks=[load, check])]))
    result = subprocess.run([str(Path(sys.executable).parent / "ansible-playbook"), "-i", "localhost,", str(play)],
        env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "automation/ansible/ansible.cfg")},
        capture_output=True, text=True, timeout=30)
    assert (result.returncode == 0) is valid, result.stdout + result.stderr
