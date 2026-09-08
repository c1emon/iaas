"""Representative release events and registry substitutes; no publication."""

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest
import yaml


spec = importlib.util.spec_from_file_location("runtime_release", Path(__file__).resolve().parents[2] / "automation/runtime/release.py")
assert spec and spec.loader
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.mark.parametrize("tag", ["v1.2.3", "v0.1.0-rc.1"])
def test_published_versions(tag):
    assert release.validate_event("release", {"action": "published", "release": {"draft": False, "tag_name": tag}}) == tag


@pytest.mark.parametrize("event,action,draft,tag", [
    ("push", "published", False, "v1.2.3"),
    ("release", "edited", False, "v1.2.3"),
    ("release", "published", True, "v1.2.3"),
    ("release", "published", False, "v01.2.3"),
    ("release", "published", False, "v1.2.3+build"),
    ("release", "published", False, "v1.2.3-rc.01"),
])
def test_rejected_events(event, action, draft, tag):
    with pytest.raises(ValueError):
        release.validate_event(event, {"action": action, "release": {"draft": draft, "tag_name": tag}})


@pytest.mark.parametrize("state", ["absent", "existing", "conflict", "unavailable"])
def test_no_overwrite_publication(monkeypatch, state):
    metadata = {"image": "ghcr.io/example/iaas-runtime", "source": "https://github.com/example/iaas",
                "revision": "a" * 40, "tag": "v1.2.3"}
    labels = {f"org.opencontainers.image.{key}": metadata["tag" if key == "version" else key]
              for key in ("source", "revision", "version")}
    calls = []
    digest = metadata["image"] + "@sha256:" + "b" * 64

    def fake_command(*arguments, **kwargs):
        calls.append(arguments)
        if arguments[:3] == ("docker", "image", "inspect"):
            selected = dict(labels)
            if state == "conflict" and arguments[-1] != "tested":
                selected["org.opencontainers.image.revision"] = "c" * 40
            return json.dumps([{"Config": {"Labels": selected}, "RepoDigests": [digest]}])
        return ""

    def manifest(*arguments, **kwargs):
        code = 0 if state in {"existing", "conflict"} else 1
        error = "manifest unknown" if state == "absent" else "unauthorized"
        return subprocess.CompletedProcess(arguments, code, "{}", error)

    monkeypatch.setattr(release, "command", fake_command)
    monkeypatch.setattr(release.subprocess, "run", manifest)
    if state in {"conflict", "unavailable"}:
        with pytest.raises((ValueError, RuntimeError)):
            release.publish(metadata, "tested")
    else:
        assert release.publish(metadata, "tested") == digest
    assert any(call[:2] == ("docker", "push") for call in calls) == (state == "absent")


def test_exact_tagged_checkout(monkeypatch):
    monkeypatch.setattr(release, "command", lambda *args: "a" * 40 if args[-1] == "HEAD" else "b" * 40)
    with pytest.raises(ValueError, match="exact Release tag"):
        release.prepare("release", {"action": "published", "release": {"draft": False, "tag_name": "v1.2.3"}}, "example/iaas")


def test_workflow_keeps_publication_after_tested_artifact_and_public_pull():
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.load((root / ".github/workflows/runtime-release.yml").read_text(), Loader=yaml.BaseLoader)
    assert workflow["on"] == {"release": {"types": ["published"]}}
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    jobs = workflow["jobs"]
    assert jobs["publish"]["needs"] == "build"
    assert jobs["anonymous-consumption"]["needs"] == "publish"
    assert workflow["permissions"] == {"contents": "read"}
    assert [name for name, job in jobs.items() if job.get("permissions", {}).get("packages") == "write"] == ["publish"]
    commands = {name: "\n".join(step.get("run", "") for step in job["steps"]) for name, job in jobs.items()}
    assert "make runtime-tofu-check" in commands["build"]
    assert "docker save" in commands["build"]
    assert "docker load" in commands["publish"] and "image-id.txt" in commands["publish"]
    assert "docker build" not in commands["publish"]
    assert "mktemp -d" in commands["anonymous-consumption"]
    assert "docker pull" in commands["anonymous-consumption"]
    assert "public consumption failed" in commands["anonymous-consumption"]
