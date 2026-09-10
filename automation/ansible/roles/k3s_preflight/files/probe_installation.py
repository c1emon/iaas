"""Read-only installation facts; never emit unit/configuration or token contents."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def _configuration(text):
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("token:")]


def probe(expected, root=Path("/"), run=subprocess.run):
    binary = root / "usr/local/bin/k3s"
    config = root / "etc/rancher/k3s/config.yaml"
    service = "k3s" if expected["role"] == "server" else "k3s-agent"
    unit = root / f"etc/systemd/system/{service}.service"
    datastore = root / "var/lib/rancher/k3s"
    result = {"state": "foreign", "version": "", "sha256": "", "service_active": False, "datastore": datastore.exists()}
    unit_paths = [root / f"{directory}/{name}.service"
                  for directory in ["etc/systemd/system", "usr/lib/systemd/system", "lib/systemd/system"]
                  for name in ["k3s", "k3s-agent"]]
    found_units = [path for path in unit_paths if path.exists()]
    extras = list((root / "etc/rancher/k3s/config.yaml.d").glob("*"))
    if not binary.exists():
        if not config.exists() and not found_units and not datastore.exists() and not extras:
            result["state"] = "fresh"
        return result
    if not binary.is_file() or binary.is_symlink():
        return result
    result["sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    if not config.exists() and not found_units and not datastore.exists() and not extras:
        if result["sha256"] != expected["sha256"]:
            return result
        result["state"] = "artifact-only"
    else:
        if found_units != [unit] or not config.is_file() or extras:
            return result
        if _configuration(config.read_text()) != _configuration(expected["config"]):
            return result
        if unit.read_text().strip() != expected["unit"].strip():
            return result
        observed = run(["systemctl", "show", service, "--property=FragmentPath,DropInPaths,ActiveState"],
                       capture_output=True, text=True, timeout=10, check=False)
        if observed.returncode != 0:
            return result
        properties = dict(line.split("=", 1) for line in observed.stdout.splitlines() if "=" in line)
        if properties.get("FragmentPath") != f"/etc/systemd/system/{service}.service" or properties.get("DropInPaths"):
            return result
        result["state"] = "managed"
        result["service_active"] = properties.get("ActiveState") == "active"
    version = run([str(binary), "--version"], capture_output=True, text=True, timeout=10, check=False)
    match = re.match(r"^k3s version (v\d+\.\d+\.\d+\+k3s\d+)(?:\s|$)", version.stdout)
    if version.returncode != 0 or match is None:
        result["state"] = "unknown"
        return result
    result["version"] = match[1]
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(probe(json.load(sys.stdin))))
    except Exception:
        print(json.dumps({"state": "unknown"}))
        sys.exit(1)
