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


@pytest.mark.parametrize("tag", ["v1.2.3", "v0.1.0-rc.1", "v1.2.3-" + "a" * 115])
def test_published_versions(tag):
    assert release.validate_event("release", {"action": "published", "release": {"draft": False, "tag_name": tag}}) == tag


@pytest.mark.parametrize("event,action,draft,tag", [
    ("push", "published", False, "v1.2.3"),
    ("release", "edited", False, "v1.2.3"),
    ("release", "published", True, "v1.2.3"),
    ("release", "published", False, "v01.2.3"),
    ("release", "published", False, "v1.2.3+build"),
    ("release", "published", False, "v1.2.3-rc.01"),
    ("release", "published", False, "v1.2.3-" + "a" * 116),
])
def test_rejected_events(event, action, draft, tag):
    with pytest.raises(ValueError):
        release.validate_event(event, {"action": action, "release": {"draft": draft, "tag_name": tag}})


@pytest.mark.parametrize("state", ["absent", "existing", "conflict", "single", "partial", "child-conflict", "wrong-arch", "unavailable"])
def test_no_overwrite_publication(monkeypatch, state):
    metadata = {"image": "ghcr.io/example/iaas-runtime", "source": "https://github.com/example/iaas",
                "revision": "a" * 40, "tag": "v1.2.3"}
    labels = {f"org.opencontainers.image.{key}": metadata["tag" if key == "version" else key]
              for key in ("source", "revision", "version")}
    image = metadata["image"]
    version = image + ":v1.2.3"
    ids = {"amd64": "sha256:" + "a" * 64, "arm64": "sha256:" + "b" * 64}
    digests = {"amd64": "sha256:" + "c" * 64, "arm64": "sha256:" + "d" * 64}
    index_digest = "sha256:" + "e" * 64
    index = {"manifests": [{"platform": {"os": "linux", "architecture": arch}, "digest": digests[arch]}
                           for arch in release.ARCHITECTURES]}
    registry = {f"{image}@{digests[arch]}": {"config": {"digest": ids[arch]}}
                for arch in release.ARCHITECTURES}
    if state in {"existing", "conflict"}:
        registry[version] = index
        registry[f"{image}@{index_digest}"] = index
    if state == "conflict":
        registry[f"{image}@{digests['arm64']}"] = {"config": {"digest": "wrong"}}
    if state == "single":
        registry[version] = {"config": {"digest": ids["amd64"]}}
    if state in {"partial", "child-conflict"}:
        registry[version + "-amd64"] = {"config": {"digest": ids["amd64"] if state == "partial" else "wrong"}}
    if state == "child-conflict":
        registry[f"{image}@{digests['amd64']}"] = {"config": {"digest": "wrong"}}
    calls = []

    def fake_command(*arguments, **kwargs):
        calls.append(arguments)
        if arguments[:3] == ("docker", "image", "inspect"):
            arch = arguments[-1].rsplit("-", 1)[1]
            return json.dumps([{"Config": {"Labels": labels}, "Os": "linux", "Id": ids[arch],
                                "Architecture": "wrong" if state == "wrong-arch" else arch}])
        if arguments[:2] == ("docker", "pull"):
            arch = arguments[-2].split("/")[1]
            digest = index_digest if arguments[-1] == version else digests[arch]
            return "Digest: " + digest
        if arguments[:3] == ("docker", "manifest", "push"):
            registry[f"{image}@{index_digest}"] = index
            return index_digest
        return ""

    def lookup(reference, insecure=False):
        if state == "unavailable":
            raise RuntimeError("registry lookup failed")
        return registry.get(reference)

    monkeypatch.setattr(release, "command", fake_command)
    monkeypatch.setattr(release, "registry_manifest", lookup)
    failed = state in {"conflict", "single", "child-conflict", "wrong-arch", "unavailable"}
    if failed:
        with pytest.raises((ValueError, RuntimeError)):
            release.publish(metadata, "tested")
    else:
        assert release.publish(metadata, "tested") == f"{image}@{index_digest}"
    pushes = [call for call in calls if call[:2] == ("docker", "push")]
    assert len(pushes) == (2 if state == "absent" else 1 if state == "partial" else 0)
    creates = [call for call in calls if call[:3] == ("docker", "manifest", "create")]
    if creates:
        assert creates[0][-2:] == tuple(f"{image}@{digests[arch]}" for arch in release.ARCHITECTURES)


@pytest.mark.parametrize("error,absent", [("manifest unknown", True), ("unauthorized", False), ("timeout", False)])
def test_registry_lookup_fails_closed(monkeypatch, error, absent):
    monkeypatch.setattr(release.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", error))
    if absent:
        assert release.registry_manifest("example/test:v1") is None
    else:
        with pytest.raises(RuntimeError, match="lookup failed"):
            release.registry_manifest("example/test:v1")


def test_containerd_manifest_identity_is_not_config_identity():
    manifest = {"config": {"digest": "config-id"}}
    record = {"Id": "manifest-id", "Descriptor": {"digest": "manifest-id"}}
    release.verify_image(manifest, "manifest-id", record)
    with pytest.raises(ValueError, match="differs"):
        release.verify_image(manifest, "another-manifest", record)


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
    for name in ("build", "anonymous-consumption"):
        assert jobs[name]["strategy"]["max-parallel"] == "1"
        assert {item["arch"] for item in jobs[name]["strategy"]["matrix"]["include"]} == {"amd64", "arm64"}
    assert "cmp tested-images/" in commands["publish"]
    assert "--platform" in commands["anonymous-consumption"]
    assert "capabilities" in commands["anonymous-consumption"]
