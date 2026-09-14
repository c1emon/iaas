"""Run a representative CRUD lifecycle through the pinned provider modules."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import importlib
import io
import json
import os
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "automation" / "src"))

from ansible.module_utils import basic  # noqa: E402
from ansible_collections.oxlorg.opnsense.plugins.module_utils.base import logic  # noqa: E402
from iaas_automation.opnsense_validation.lifecycle import resource_arguments  # noqa: E402


RESOURCE_FILES = {
    "nat_destination": "dnat.yml",
    "nat_one_to_one": "one-to-one-nat.yml",
    "rule_interface_group": "interface-groups.yml",
}
RESOURCE_KEYS = {
    "nat_destination": "opnsense_dnat_rules",
    "nat_one_to_one": "opnsense_one_to_one_nat_rules",
    "rule_interface_group": "opnsense_interface_groups",
}
RESOURCE_NAMES = {
    "nat_destination": "dnat",
    "nat_one_to_one": "one-to-one-nat",
    "rule_interface_group": "interface-groups",
}


class MemorySession:
    """Small OPNsense API model that stores the provider's actual payloads."""

    objects: dict[str, dict] = {}
    posts: list[dict] = []
    activations = 0
    next_id = 1
    controller = ""

    def __init__(self, **kwargs):
        del kwargs

    @classmethod
    def reset(cls, controller: str) -> None:
        cls.objects = {}
        cls.posts = []
        cls.activations = 0
        cls.next_id = 1
        cls.controller = controller

    def close(self) -> None:
        return None

    def get(self, cnf: dict) -> dict:
        assert cnf["command"] == "get"
        records = deepcopy(self.objects)
        if self.controller == "nat_destination":
            return {"DNat": {"rule": records}}
        if self.controller == "nat_one_to_one":
            return {"filter": {"onetoone": {"rule": records}}}
        return {"group": {"ifgroupentry": records}}

    def post(self, cnf: dict, headers: dict | None = None) -> dict:
        del headers
        command = cnf["command"]
        self.posts.append(deepcopy(cnf))
        if command in {"apply", "reconfigure"}:
            self.activations += 1
            return {"status": "ok"}

        if command in {"add_rule", "add_item"}:
            payload = cnf["data"]["rule" if command == "add_rule" else "group"]
            uuid = f"synthetic-{self.next_id}"
            self.next_id += 1
            self.objects[uuid] = deepcopy(payload)
            return {"result": "saved", "uuid": uuid}

        if command in {"set_rule", "set_item"}:
            uuid = cnf["params"][0]
            payload = cnf["data"]["rule" if command == "set_rule" else "group"]
            self.objects[uuid] = deepcopy(payload)
            return {"result": "saved"}

        if command == "del_rule" or command == "del_item":
            self.objects.pop(cnf["params"][0], None)
            return {"result": "deleted"}

        if command == "toggle_rule":
            uuid = cnf["params"][0]
            item = self.objects[uuid]
            if self.controller == "nat_destination":
                item["disabled"] = "0" if str(item.get("disabled")) == "1" else "1"
            else:
                item["enabled"] = "0" if str(item.get("enabled")) == "1" else "1"
            return {"result": "toggled"}

        raise AssertionError(f"unexpected provider API command: {command}")


logic.Session = MemorySession
basic._ANSIBLE_PROFILE = "legacy"


def invoke(provider, params: dict, *, check_mode: bool = False) -> dict:
    module_args = {
        "firewall": "synthetic.invalid",
        "api_key": "synthetic",
        "api_secret": "synthetic",
        **params,
        "_ansible_check_mode": check_mode,
    }
    basic._ANSIBLE_ARGS = json.dumps({"ANSIBLE_MODULE_ARGS": module_args}).encode()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            provider.run_module()
        except SystemExit as error:
            code = error.code
    if code != 0:
        raise AssertionError(f"provider failed: {output.getvalue()}")
    return json.loads(output.getvalue())


def main() -> None:
    resource = os.environ["TEST_NAT_PROVIDER"]
    fixture = ROOT / "tests" / "fixtures" / "opnsense-nat" / RESOURCE_FILES[resource]
    document = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    record = document[RESOURCE_KEYS[resource]][0]
    provider = importlib.import_module(
        "ansible_collections.oxlorg.opnsense.plugins.modules." + resource
    )
    MemorySession.reset(resource)

    present = resource_arguments(record, RESOURCE_NAMES[resource])
    created = invoke(provider, present)
    assert created["changed"] is True
    assert len(MemorySession.objects) == 1
    posts_after_create = len(MemorySession.posts)
    assert invoke(provider, present)["changed"] is False
    assert len(MemorySession.posts) == posts_after_create

    checked = invoke(provider, present, check_mode=True)
    assert checked["changed"] is False
    assert len(MemorySession.posts) == posts_after_create
    assert MemorySession.activations == 0

    if resource == "nat_destination":
        cleared_record = deepcopy(record)
        cleared_record.pop("local_port")
        cleared = resource_arguments(cleared_record, "dnat")
        assert invoke(provider, cleared)["changed"] is True
        assert next(iter(MemorySession.objects.values()))["local-port"] == ""
        cleared_posts = len(MemorySession.posts)
        assert invoke(provider, cleared)["changed"] is False
        assert len(MemorySession.posts) == cleared_posts

        # The provider translates the public associated_rule value to the
        # native API's ``pass`` field.  Exercise both non-empty choices and
        # clearing that field, with an idempotent repeat after each update.
        raw = next(iter(MemorySession.objects.values()))
        assert raw["pass"] == "rule"
        associated_record = deepcopy(cleared_record)
        associated_record["associated_rule"] = "pass"
        associated = resource_arguments(associated_record, "dnat")
        assert invoke(provider, associated)["changed"] is True
        assert next(iter(MemorySession.objects.values()))["pass"] == "pass"
        associated_posts = len(MemorySession.posts)
        assert invoke(provider, associated)["changed"] is False
        assert len(MemorySession.posts) == associated_posts

        associated_record["associated_rule"] = ""
        cleared_associated = resource_arguments(associated_record, "dnat")
        assert invoke(provider, cleared_associated)["changed"] is True
        assert next(iter(MemorySession.objects.values()))["pass"] == ""
        cleared_associated_posts = len(MemorySession.posts)
        assert invoke(provider, cleared_associated)["changed"] is False
        assert len(MemorySession.posts) == cleared_associated_posts
    elif resource == "rule_interface_group":
        cleared_record = deepcopy(record)
        cleared_record.pop("description")
        cleared = resource_arguments(cleared_record, "interface-groups")
        assert invoke(provider, cleared)["changed"] is True
        assert next(iter(MemorySession.objects.values()))["descr"] == ""
        cleared_posts = len(MemorySession.posts)
        assert invoke(provider, cleared)["changed"] is False
        assert len(MemorySession.posts) == cleared_posts

    if resource == "nat_destination":
        # Existing-rule check mode predicts both update and deletion while
        # leaving the in-memory API untouched; normal deletion follows below.
        changed_record = deepcopy(record)
        changed_record["sequence"] += 1
        changed = resource_arguments(changed_record, "dnat")
        check_posts = len(MemorySession.posts)
        assert invoke(provider, changed, check_mode=True)["changed"] is True
        assert len(MemorySession.posts) == check_posts

        check_absent_record = {"state": "absent", "scope": record["scope"], "slug": record["slug"]}
        check_absent = resource_arguments(check_absent_record, "dnat")
        assert invoke(provider, check_absent, check_mode=True)["changed"] is True
        assert len(MemorySession.posts) == check_posts
        assert MemorySession.objects

    if resource in {"nat_destination", "nat_one_to_one"}:
        disabled_record = deepcopy(record)
        disabled_record["enabled"] = False
        disabled = resource_arguments(disabled_record, RESOURCE_NAMES[resource])
        assert invoke(provider, disabled)["changed"] is True
        raw = next(iter(MemorySession.objects.values()))
        raw_field = "disabled" if resource == "nat_destination" else "enabled"
        expected = "1" if resource == "nat_destination" else "0"
        assert str(raw[raw_field]) == expected

        reenabled = resource_arguments(record, RESOURCE_NAMES[resource])
        assert invoke(provider, reenabled)["changed"] is True
        assert str(raw[raw_field]) == ("0" if resource == "nat_destination" else "1")

    absent_record = {"state": "absent"}
    if resource == "rule_interface_group":
        absent_record["name"] = record["name"]
    else:
        absent_record.update(scope=record["scope"], slug=record["slug"])
    absent = resource_arguments(absent_record, RESOURCE_NAMES[resource])
    assert invoke(provider, absent)["changed"] is True
    assert not MemorySession.objects
    posts_after_delete = len(MemorySession.posts)
    assert invoke(provider, absent)["changed"] is False
    assert len(MemorySession.posts) == posts_after_delete


if __name__ == "__main__":
    main()
