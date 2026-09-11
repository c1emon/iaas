"""Release event validation and no-overwrite publication of a tested image."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


VERSION = re.compile(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:[0-9A-Za-z-]+)(?:\.[0-9A-Za-z-]+)*)?")


def validate_event(event_name: str, event: dict) -> str:
    release = event.get("release", {})
    tag = release.get("tag_name", "")
    if event_name != "release" or event.get("action") != "published" or release.get("draft") is not False:
        raise ValueError("only a published non-draft Release can publish an image")
    # Leave six characters for the per-architecture tag suffix.
    if not isinstance(tag, str) or not VERSION.fullmatch(tag) or len(tag) > 122:
        raise ValueError("release tag must be OCI-compatible vX.Y.Z[-prerelease], at most 122 characters, without build metadata")
    if "-" in tag:
        for identifier in tag.split("-", 1)[1].split("."):
            if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
                raise ValueError("numeric prerelease identifiers must not have leading zeros")
    return tag


def command(*arguments: str, **kwargs) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{arguments[0]} operation failed: {result.stderr[-1500:]}")
    return result.stdout.strip()


def prepare(event_name: str, event: dict, repository: str) -> dict:
    tag = validate_event(event_name, event)
    revision = command("git", "rev-parse", f"refs/tags/{tag}^{{commit}}")
    if revision != command("git", "rev-parse", "HEAD"):
        raise ValueError("checkout must be the exact Release tag revision")
    return {"tag": tag, "revision": revision, "source": f"https://github.com/{repository}",
            "image": f"ghcr.io/{repository.split('/')[0].lower()}/iaas-runtime"}


def check_labels(labels: dict, metadata: dict) -> None:
    for name in ("source", "revision", "version"):
        expected = metadata["tag" if name == "version" else name]
        if labels.get(f"org.opencontainers.image.{name}") != expected:
            raise ValueError(f"image {name} does not match release; existing versions are never overwritten")


ARCHITECTURES = ("amd64", "arm64")


def registry_manifest(reference: str, insecure: bool = False) -> dict | None:
    flags = ["--insecure"] if insecure else []
    result = subprocess.run(["docker", "manifest", "inspect", *flags, reference], capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    if any(marker in result.stderr.lower() for marker in ("manifest unknown", "no such manifest", "name unknown")):
        return None
    raise RuntimeError("registry lookup failed; cannot establish that version is absent")


def pulled_digest(reference: str, architecture: str) -> str:
    output = command("docker", "pull", "--platform", f"linux/{architecture}", reference)
    match = re.search(r"(?m)^Digest: (sha256:[0-9a-f]{64})$", output)
    if not match:
        raise RuntimeError("registry pull did not report a digest")
    return match[1]


def verify_image(manifest: dict | None, digest: str, record: dict) -> None:
    descriptor = record.get("Descriptor") or {}
    # Containerd exposes a manifest descriptor; classic Docker exposes the config ID.
    matches = descriptor["digest"] == digest if descriptor else (
        manifest is not None and manifest.get("config", {}).get("digest") == record["Id"])
    if manifest is None or not matches:
        raise ValueError("registry image differs from tested artifact; existing versions are never overwritten")


def verify_index(index: dict, image: str, records: dict, insecure: bool = False) -> None:
    manifests = index.get("manifests", [])
    if len(manifests) != len(ARCHITECTURES) or {
        (item.get("platform", {}).get("os"), item.get("platform", {}).get("architecture"))
        for item in manifests
    } != {("linux", arch) for arch in ARCHITECTURES}:
        raise ValueError("existing version must contain exactly linux/amd64 and linux/arm64; never overwritten")
    for item in manifests:
        architecture = item["platform"]["architecture"]
        child = registry_manifest(f"{image}@{item['digest']}", insecure)
        verify_image(child, item["digest"], records[architecture])


def publish(metadata: dict, tested_image: str, *, insecure: bool = False) -> str:
    image = metadata["image"]
    version = f"{image}:{metadata['tag']}"
    records = {}
    # Admit both tested artifacts before writing anything to the registry.
    for architecture in ARCHITECTURES:
        record = json.loads(command("docker", "image", "inspect", "--platform", f"linux/{architecture}",
                                    f"{tested_image}-{architecture}"))[0]
        check_labels(record["Config"].get("Labels") or {}, metadata)
        if (record["Os"], record["Architecture"]) != ("linux", architecture):
            raise ValueError("tested image architecture mismatch")
        records[architecture] = record
    existing = registry_manifest(version, insecure)
    if existing is not None:
        verify_index(existing, image, records, insecure)
        digest = pulled_digest(version, "amd64")
    else:
        references = []
        for architecture in ARCHITECTURES:
            child_tag = f"{version}-{architecture}"
            child = registry_manifest(child_tag, insecure)
            if child is None:
                command("docker", "tag", f"{tested_image}-{architecture}", child_tag)
                # Export only the tested platform, excluding any local build index/attestation.
                command("docker", "push", "--platform", f"linux/{architecture}", child_tag)
            child_digest = pulled_digest(child_tag, architecture)
            reference = f"{image}@{child_digest}"
            verify_image(registry_manifest(reference, insecure), child_digest, records[architecture])
            references.append(reference)
        flags = ["--insecure"] if insecure else []
        command("docker", "manifest", "create", *flags, version, *references)
        output = command("docker", "manifest", "push", *flags, "--purge", version)
        digest = output.splitlines()[-1]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise RuntimeError("manifest publication did not report a digest")
    reference = f"{image}@{digest}"
    published = registry_manifest(reference, insecure)
    if published is None:
        raise RuntimeError("published manifest is unavailable")
    verify_index(published, image, records, insecure)
    return reference


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "publish"])
    parser.add_argument("--metadata", default="release.json")
    parser.add_argument("--tested-image", default="iaas-runtime:release-tested")
    args = parser.parse_args()
    if args.action == "prepare":
        metadata = prepare(os.environ["GITHUB_EVENT_NAME"], json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()), os.environ["GITHUB_REPOSITORY"])
        Path(args.metadata).write_text(json.dumps(metadata) + "\n")
        return
    metadata = json.loads(Path(args.metadata).read_text())
    with tempfile.TemporaryDirectory(prefix="iaas-ghcr-auth-") as config:
        os.environ["DOCKER_CONFIG"] = config
        command("docker", "login", "ghcr.io", "--username", os.environ["GITHUB_ACTOR"], "--password-stdin", input=os.environ["GITHUB_TOKEN"])
        digest = publish(metadata, args.tested_image)
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(f"digest={digest}\n")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        summary.write(f"Release: {metadata['tag']}\n\nSource: {metadata['revision']}\n\nRegistry image: `{digest}`\n\nPush/existing-version verification succeeded; anonymous consumption is pending.\n")


if __name__ == "__main__":
    main()
