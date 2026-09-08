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
    if not isinstance(tag, str) or not VERSION.fullmatch(tag) or len(tag) > 128:
        raise ValueError("release tag must be OCI-compatible vX.Y.Z[-prerelease], without build metadata")
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


def publish(metadata: dict, tested_image: str) -> str:
    image = metadata["image"]
    version = f"{image}:{metadata['tag']}"
    check_labels(json.loads(command("docker", "image", "inspect", tested_image))[0]["Config"].get("Labels") or {}, metadata)
    existing = subprocess.run(["docker", "manifest", "inspect", version], capture_output=True, text=True)
    if existing.returncode == 0:
        command("docker", "pull", version)
        record = json.loads(command("docker", "image", "inspect", version))[0]
        check_labels(record["Config"].get("Labels") or {}, metadata)
    elif any(marker in existing.stderr.lower() for marker in ("manifest unknown", "no such manifest", "name unknown")):
        command("docker", "tag", tested_image, version)
        command("docker", "push", version)
        record = json.loads(command("docker", "image", "inspect", version))[0]
    else:
        raise RuntimeError("registry lookup failed; cannot establish that version is absent")
    digests = [value for value in record.get("RepoDigests", []) if value.startswith(image + "@sha256:")]
    if not digests:
        raise RuntimeError("image operation succeeded but registry digest is unavailable")
    return digests[0]


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
