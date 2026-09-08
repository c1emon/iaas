"""Inspect standard Docker image layers for excluded runtime contents."""

import argparse
import json
from pathlib import PurePosixPath
import subprocess
import tarfile
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="iaas-runtime:oci-release-test")
    args = parser.parse_args()
    forbidden = []
    notices = set()
    with tempfile.TemporaryDirectory(prefix="iaas-layer-check-") as work:
        archive = f"{work}/image.tar"
        subprocess.run(["docker", "save", "-o", archive, args.image], check=True)
        with tarfile.open(archive) as image:
            manifest_file = image.extractfile("manifest.json")
            assert manifest_file is not None
            manifest = json.load(manifest_file)[0]
            assert len(manifest["Layers"]) > 1, "dependency and repository layers must be separate"
            for layer_name in manifest["Layers"]:
                layer_file = image.extractfile(layer_name)
                assert layer_file is not None
                with tarfile.open(fileobj=layer_file, mode="r|*") as layer:
                    for member in layer:
                        path = PurePosixPath(member.name)
                        parts = path.parts
                        if not parts:
                            continue
                        excluded = any(part in {"docs", "examples", "fixtures", "openspec", ".git", ".github", "__pycache__"} for part in parts)
                        excluded |= any(part in {"test", "tests"} and (index < len(parts) - 1 or member.isdir()) and (index == 0 or parts[index - 1] != "plugins") for index, part in enumerate(parts))
                        excluded |= path.name.lower().startswith("readme") or path.name.startswith("._")
                        excluded |= str(path).startswith(("opt/iaas/environments/", "usr/share/man/", "usr/share/info/"))
                        excluded |= str(path) in {"usr/local/bin/op", "usr/local/bin/pip", "usr/local/bin/pip3", "tmp/prune.py"}
                        if excluded:
                            forbidden.append(str(path))
                        for name in ("uv", "opentofu", "packer", "debian"):
                            if str(path).startswith(f"usr/share/licenses/{name}/") and member.isfile():
                                notices.add(name)
    assert not forbidden, f"excluded files in published layers: {forbidden[:12]} ({len(forbidden)} total)"
    assert notices == {"uv", "opentofu", "packer", "debian"}, "required license notices missing"
    print("image layers: excluded content absent; required tool and OS notices retained")


if __name__ == "__main__":
    main()
