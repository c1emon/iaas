"""Exercise the shipped runtime using only synthetic external mounts."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="iaas-runtime:oci-release-test")
    parser.add_argument("--tofu", action="store_true", help="also init/validate the external root; permits provider downloads")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="iaas-runtime-smoke-") as temporary:
        work = Path(temporary)
        environment = work / "environment"
        shutil.copytree(root / "tests/fixtures/runtime", environment / "inventory")
        shutil.copytree(root / "tests/fixtures/k3s", environment / "k3s")
        (environment / "ansible").mkdir()
        (environment / "ansible/inventory.yml").write_text(
            "all:\n  children:\n    opnsense:\n      hosts:\n        synthetic-firewall: {}\n")
        (environment / "diagnostic.json").write_text(
            '{"schema_version":1,"kind":"states","selector":{"source_ip":"invalid"}}')
        output = work / "output"
        output.mkdir()
        command = ["docker", "run", "--rm", "--network", "none", "--read-only",
                   "--user", f"{os.getuid()}:{os.getgid()}", "--tmpfs", "/tmp:rw,mode=1777",
                   "-v", f"{environment}:/environment:ro", "-v", f"{output}:/output",
                   "-e", "ENVIRONMENT_DIR=/environment", "-e", "OUTPUT_DIR=/output", "-e", "HOME=/tmp/home"]

        def run(*arguments: str, succeeds: bool = True) -> str:
            result = subprocess.run([*command, args.image, *arguments], text=True, capture_output=True)
            if (result.returncode == 0) != succeeds:
                raise RuntimeError(f"runtime smoke failed: {arguments}\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
            return result.stdout + result.stderr

        run()
        assert not list(output.iterdir()), "help created output"
        run("generate")
        run("check-generated")
        diagnostic = run("opnsense-diagnose", "OPNSENSE_TARGET=synthetic-firewall",
                         "OPNSENSE_DIAGNOSTICS_REQUEST=/environment/diagnostic.json", succeeds=False)
        assert "invalid_request_or_output" in diagnostic, "diagnostic admission did not run"
        # Parse the shipped roles/playbooks without running their tasks.
        for playbook in ("verify-guests.yml", "bootstrap-guests.yml"):
            subprocess.run([*command, "-e", "ANSIBLE_LOCAL_TEMP=/tmp/ansible",
                            "--entrypoint", "ansible-playbook", args.image, "--syntax-check",
                            "-i", "/output/generated/ansible/pve.yml",
                            f"/opt/iaas/automation/ansible/playbooks/pve/{playbook}"], check=True,
                           capture_output=True, text=True)
        plugin_check = """
from ansible.plugins.loader import lookup_loader, filter_loader, init_plugin_loader
init_plugin_loader()
assert lookup_loader.get('k3s_protected_secret') is not None
assert lookup_loader.get('vm_baseline_protected_secret') is not None
assert list(filter_loader.all())
assert filter_loader.get('opnsense_diagnostic_controller') is not None
assert filter_loader.get('opnsense_alias_plan') is not None
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common import utils
from ansible_collections.oxlorg.opnsense.plugins.modules import alias
from ansible_collections.c1emon.xikeos.plugins.modules import xikeos_command
import os, json, pathlib, shutil
from packaging.specifiers import SpecifierSet
records = [json.loads(path.read_text())['collection_info'] for path in
    pathlib.Path('/opt/iaas/automation/ansible/collections/ansible_collections').glob('*/*/MANIFEST.json')]
versions = {record['namespace'] + '.' + record['name']: record['version'] for record in records}
for record in records:
    for name, constraint in record['dependencies'].items():
        assert name in versions and versions[name] in SpecifierSet(constraint), 'Collection closure is incomplete'
from iaas_automation.pve_inventory.pve_api.runtime import load_api_runtime_config
from iaas_automation.k3s_automation.secrets import load_protected_environment_json
from iaas_automation.common.errors import ValidationError
assert shutil.which('op') is None
assert 'OP_SERVICE_ACCOUNT_TOKEN' not in os.environ
config = load_api_runtime_config({'TF_VAR_pve_endpoint': 'https://pve.example.invalid',
    'TF_VAR_pve_api_username': 'synthetic@pve', 'TF_VAR_pve_api_token_id': 'synthetic',
    'TF_VAR_pve_api_token_secret': 'synthetic-value'})
assert config.api_token_secret == 'synthetic-value'
secret_file = pathlib.Path('/tmp/runtime-secrets.json')
secret_file.write_text(json.dumps({'op://synthetic/cluster/token': 'synthetic-value'}))
secret_file.chmod(0o600)
assert load_protected_environment_json(secret_file).resolve('op://synthetic/cluster/token').status == 'resolved'
secret_file.chmod(0o644)
try:
    load_protected_environment_json(secret_file)
except ValidationError:
    pass
else:
    raise AssertionError('unsafe secret file accepted')
"""
        subprocess.run([*command, "-e", "ANSIBLE_LOCAL_TEMP=/tmp/ansible",
                        "--entrypoint", "python", args.image, "-c", plugin_check], check=True,
                       capture_output=True, text=True)
        run("k3s-render", "K3S_INTENT=/environment/k3s/intent.yml",
            "K3S_INVENTORY=/environment/k3s/generated-pve.yml")
        assert (output / "runtime/k3s/review.yml").is_file()
        if args.tofu:
            working_root = work / "tofu-root"
            shutil.copytree(root / "tests/fixtures/runtime-root", working_root)
            lock = working_root / ".terraform.lock.hcl"
            original_lock = lock.read_bytes()
            tofu = ["docker", "run", "--rm", "--read-only", "--user", f"{os.getuid()}:{os.getgid()}",
                    "--tmpfs", "/tmp:rw,mode=1777", "-e", "HOME=/tmp", "-v", f"{working_root}:/root:rw",
                    "-v", f"{output}:/output:ro", "--entrypoint", "tofu", args.image, "-chdir=/root"]
            subprocess.run([*tofu, "init", "-backend=false", "-lockfile=readonly", "-input=false"], check=True)
            subprocess.run([*tofu, "validate"], check=True)
            assert lock.read_bytes() == original_lock, "provider lock changed"
            assert not list(working_root.glob("*.tfstate*")), "validation created state"
        assert (output / "generated/docs/services.md").stat().st_uid == os.getuid()
        (output / "generated/docs/services.md").write_text("stale\n")
        run("services-check", succeeds=False)
        run("pve-generate", "ENVIRONMENT_DIR=/missing", succeeds=False)
        run("pve-generate", "OUTPUT_DIR=/environment/inventory", succeeds=False)
        run("pve-generate", "ASTRA=legacy", succeeds=False)
        run("pve-generate", "ENVIRONMENT_DIR=", succeeds=False)
        print("runtime smoke: offline generation/check, K3s rendering, OPNsense plugins/admission, UID, missing/unsafe/stale inputs passed")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit((exc.stderr or exc.stdout or str(exc))[-3000:]) from exc
