from __future__ import annotations

import hashlib
import os
import shlex
import socket
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from iaas.image import runtime
from iaas.runtime_execution.execution import Execution
from iaas.runtime_execution.outputs import TaskOutputs

PROFILE = Path(__file__).parents[2] / "automation/packer/qemu/debian-13/packer.pkr.hcl"
RUNTIME = Path(__file__).parents[2] / "src/iaas/image/runtime.py"


def test_qemu_profile_keeps_system_disk_when_adding_seed_and_uefi() -> None:
    profile = PROFILE.read_text(encoding="utf-8")

    # Packer's qemuargs -drive override removes its generated system disk.
    assert "\n  qemuargs " not in profile
    assert 'vm_name              = "disk.qcow2"' in profile
    assert '"user-data" = file("${var.seed_directory}/build.user-data")' in profile
    assert '"meta-data" = file("${var.seed_directory}/build.meta-data")' in profile
    assert "cd_files =" not in profile
    assert 'cd_label = "cidata"' in profile
    assert 'efi_boot          = var.firmware == "uefi"' in profile
    assert "efi_firmware_code" in profile
    assert "efi_firmware_vars" in profile
    assert "efi_drop_efivars  = true" in profile
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"PKR_VAR_seed_directory": str(task)' in runtime
    assert "PKR_VAR_seed_image" not in runtime
    assert '"-serial", "file:" + str(directory / f"{phase}.serial.log")' in runtime


def test_image_builder_installs_pinned_tools_and_checks_recipe_separately() -> None:
    oci = PROFILE.parents[4] / "automation" / "oci"
    dockerfile = (oci / "disk-image-builder" / "Dockerfile").read_text(encoding="utf-8")
    checks = (oci / "checks" / "disk_image_builder.sh").read_text(encoding="utf-8")
    customize = PROFILE.parent / "ansible" / "customize.yml"
    playbook = customize.read_text(encoding="utf-8")
    assert "ansible-galaxy collection install --no-deps community.general:13.4.0" in dockerfile
    assert "packer plugins install github.com/hashicorp/qemu 1.1.3" in dockerfile
    assert "packer plugins install github.com/hashicorp/ansible 1.1.6" in dockerfile
    assert "ansible-playbook" not in dockerfile
    assert '--entrypoint virt-sysprep "$image" --list-operations' in checks
    assert "for operation in machine-id ssh-hostkeys logfiles tmp-files package-manager-cache net-hwaddr" in checks
    assert "--syntax-check -i localhost," in checks
    assert "RUN rm -rf /var/tmp && ln -s /tmp /var/tmp" in dockerfile
    assert "community.general.timezone" in playbook
    assert "community.general.locale_gen" in playbook
    assert "ansible.builtin.locale_gen" not in playbook
    assert "['locales', 'tzdata', 'util-linux-extra']" in playbook
    assert "['cloud-init-main.service']" in playbook
    assert 'loop: "{{ ([\'cloud-init\'] if image_cloud_init == \'installed\' else [])' not in playbook


def test_qemu_file_serial_argument_parses_and_quits_without_a_guest(tmp_path: Path) -> None:
    qemu = shutil.which("qemu-system-x86_64")
    if qemu is None:
        pytest.skip("qemu-system-x86_64 is required for the argv smoke test")
    serial = tmp_path / "serial.log"
    qmp = tmp_path / "qmp.sock"
    command = [qemu, "-machine", "none", "-nodefaults", "-display", "none",
               "-serial", f"file:{serial}", "-no-reboot", "-S",
               "-qmp", f"unix:{qmp},server=on,wait=off"]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 5
        connection: socket.socket | None = None
        while time.monotonic() < deadline and process.poll() is None:
            if qmp.exists():
                candidate: socket.socket | None = None
                try:
                    candidate = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    candidate.settimeout(0.5)
                    candidate.connect(str(qmp))
                    connection = candidate
                    break
                except OSError:
                    if candidate is not None:
                        candidate.close()
            time.sleep(0.01)
        if connection is None:
            detail = "qmp socket did not become available"
            if process.poll() is not None and process.stderr is not None:
                detail = process.stderr.read().decode(errors="replace")
            raise AssertionError(detail)
        with connection:
            connection.recv(4096)
            connection.sendall(b'{"execute":"qmp_capabilities"}\r\n')
            connection.recv(4096)
            connection.sendall(b'{"execute":"quit"}\r\n')
        assert process.wait(timeout=5) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.parametrize("firmware", ["bios", "uefi"])
def test_packer_command_capture_keeps_system_disk_and_boot_media(tmp_path: Path, firmware: str,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """Run Packer through tool substitutes; no guest or KVM is started."""
    packer = shutil.which("packer")
    ssh_keygen = shutil.which("ssh-keygen")
    if packer is None or ssh_keygen is None:
        pytest.skip("Packer and ssh-keygen are required for command capture")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    cloud_localds = bin_dir / "cloud-localds"
    cloud_localds.write_text("#!/bin/sh\nset -eu\n: > \"$1\"\n", encoding="utf-8")
    cloud_localds.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    seed = tmp_path / "seed"
    seed.mkdir()
    seed_outputs = TaskOutputs.create(tmp_path / "outputs", tmp_path / "implementation", [])
    seed_execution = Execution(seed_outputs, {})
    task = {"owned_resources": []}

    def seed_tool(execution: Execution, phase: str, command: list[str], cwd: Path) -> None:
        if Path(command[0]).name == "ssh-keygen":
            subprocess.run(command, cwd=cwd, check=True)
        elif Path(command[0]).name == "cloud-localds":
            Path(command[1]).write_bytes(b"seed")
        else:
            raise AssertionError(command)

    monkeypatch.setattr(runtime, "_run_tool", seed_tool)
    _, key = runtime._make_seed(seed_execution, seed, username="packer", phase="build", task=task)
    base = tmp_path / "base.qcow2"
    base.write_bytes(b"base")
    code = tmp_path / "OVMF_CODE.fd"
    vars_template = tmp_path / "OVMF_VARS.fd"
    code.write_bytes(b"code")
    vars_template.write_bytes(b"vars")
    argv_file = tmp_path / "qemu.argv"
    (bin_dir / "qemu-img").write_text(
        "#!/bin/sh\nset -eu\nlast=\"\"; for arg in \"$@\"; do last=\"$arg\"; done\n"
        "case \"$1\" in info) echo '{\"format\":\"qcow2\",\"virtual-size\":1073741824}';; create|convert) : > \"$last\" 2>/dev/null || true;; esac\n",
        encoding="utf-8")
    (bin_dir / "mkisofs").write_text(
        "#!/bin/sh\nset -eu\nout=\"\"; prev=\"\"; for arg in \"$@\"; do if [ \"$prev\" = \"-o\" ]; then out=\"$arg\"; fi; prev=\"$arg\"; done\n"
        "dd if=/dev/zero of=\"$out\" bs=1 count=1 2>/dev/null\n", encoding="utf-8")
    (bin_dir / "ansible-playbook").write_text(
        "#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo 'ansible-playbook [core 2.15.0]'; fi\nexit 0\n",
        encoding="utf-8")
    (bin_dir / "qemu-system-x86_64").write_text(
        f"#!/bin/sh\nif [ \"$1\" = \"-version\" ]; then echo 'QEMU emulator version 8.2.0'; exit 0; fi\nprintf '%s\\n' \"$@\" > {argv_file}\nexit 1\n",
        encoding="utf-8")
    for path in bin_dir.iterdir():
        path.chmod(0o755)
    checksum = hashlib.sha256(base.read_bytes()).hexdigest()
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    command = [packer, "build", "-machine-readable", "-var", f"base_image={base}",
               "-var", f"base_checksum=sha256:{checksum}", "-var", f"output_directory={tmp_path / 'out'}",
               "-var", f"firmware={firmware}", "-var", f"seed_directory={seed}", "-var", "ssh_username=packer",
               "-var", f"ssh_private_key_file={key}", "-var", "apt_mirror=https://deb.debian.org/debian",
               "-var", "apt_security_mirror=https://security.debian.org/debian-security", "-var", "cpus=1",
               "-var", "memory_mib=512"]
    if firmware == "uefi":
        command += ["-var", f"uefi_code={code}", "-var", f"uefi_vars={vars_template}"]
    command.append(str(PROFILE))
    result = subprocess.run(command, cwd=PROFILE.parent, env=env, capture_output=True, text=True, check=False)
    if not argv_file.exists() and "plugin" in (result.stdout + result.stderr).lower():
        pytest.skip("pinned Packer QEMU plugin is unavailable in this environment")
    assert argv_file.is_file(), result.stdout + result.stderr
    argv = argv_file.read_text(encoding="utf-8").splitlines()
    drives = [value for index, value in enumerate(argv) if index and argv[index - 1] == "-drive"]
    assert any(f"file={tmp_path / 'out' / 'disk.qcow2'}" in value for value in drives)
    assert any("media=cdrom" in value for value in drives)
    if firmware == "uefi":
        assert any(f"file={code}" in value and "pflash" in value for value in drives)
        assert any("efivars.fd" in value and "pflash" in value for value in drives)
    else:
        assert not any("pflash" in value for value in drives)


def test_packer_cd_contains_nocloud_root_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Build Packer's actual seed ISO and inspect its root directory."""
    required = ("packer", "ssh-keygen", "qemu-img", "mkisofs", "isoinfo")
    if any(shutil.which(command) is None for command in required):
        pytest.skip("Packer, QEMU image tools and ISO inspection tools are required")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    iso_copy = tmp_path / "captured.iso"
    qemu = bin_dir / "qemu-system-x86_64"
    qemu.write_text(
        "#!/bin/sh\nset -eu\n"
        "if [ \"${1:-}\" = \"-version\" ]; then echo 'QEMU emulator version 8.2.0'; exit 0; fi\n"
        "previous=\"\"\n"
        "for argument do\n"
        "  if [ \"$previous\" = \"-cdrom\" ]; then cp \"$argument\" "
        f"{shlex.quote(str(iso_copy))}\n"
        "  elif [ \"$previous\" = \"-drive\" ] && echo \"$argument\" | grep -q 'media=cdrom'; then\n"
        "    image=${argument#file=}; image=${image%%,*}; cp \"$image\" "
        f"{shlex.quote(str(iso_copy))}\n"
        "  fi\n"
        "  previous=\"$argument\"\n"
        "done\nexit 1\n",
        encoding="utf-8",
    )
    qemu.chmod(0o755)
    qemu_img = bin_dir / "qemu-img"
    qemu_img.write_text(
        "#!/bin/sh\nset -eu\n"
        "last=\"\"; for argument do last=\"$argument\"; done\n"
        "case \"$1\" in\n"
        "  info) echo '{\"format\":\"qcow2\",\"virtual-size\":1073741824}';;\n"
        "  create|convert) : > \"$last\";;\n"
        "esac\n",
        encoding="utf-8",
    )
    qemu_img.chmod(0o755)
    ansible = bin_dir / "ansible-playbook"
    ansible.write_text("#!/bin/sh\nset -eu\nexit 0\n", encoding="utf-8")
    ansible.chmod(0o755)
    cloud_localds = bin_dir / "cloud-localds"
    cloud_localds.write_text("#!/bin/sh\nset -eu\n: > \"$1\"\n", encoding="utf-8")
    cloud_localds.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")

    seed = tmp_path / "seed"
    seed.mkdir()
    outputs = TaskOutputs.create(tmp_path / "outputs", tmp_path / "implementation", [])
    execution = Execution(outputs, {})
    task = {"owned_resources": []}
    _, key = runtime._make_seed(execution, seed, username="packer", phase="build", task=task)
    base = tmp_path / "base.qcow2"
    base.write_bytes(b"base")
    checksum = hashlib.sha256(base.read_bytes()).hexdigest()
    command = [shutil.which("packer") or "packer", "build", "-machine-readable",
               "-var", f"base_image={base}", "-var", f"base_checksum=sha256:{checksum}",
               "-var", f"output_directory={tmp_path / 'out'}", "-var", "firmware=bios",
               "-var", f"seed_directory={seed}", "-var", "ssh_username=packer",
               "-var", f"ssh_private_key_file={key}", "-var", "apt_mirror=https://deb.debian.org/debian",
               "-var", "apt_security_mirror=https://security.debian.org/debian-security",
               "-var", "cpus=1", "-var", "memory_mib=512", str(PROFILE)]
    result = subprocess.run(command, cwd=PROFILE.parent, env=dict(os.environ), capture_output=True, text=True, check=False)
    if not iso_copy.exists() and "plugin" in (result.stdout + result.stderr).lower():
        pytest.skip("pinned Packer QEMU plugin is unavailable in this environment")
    assert iso_copy.is_file(), result.stdout + result.stderr
    listing = subprocess.run(["isoinfo", "-R", "-f", "-i", str(iso_copy)], capture_output=True, text=True, check=True).stdout
    names = {line.rsplit("/", 1)[-1].split(";", 1)[0].lower() for line in listing.splitlines() if line.strip()}
    assert any(name.startswith("user-dat") for name in names), names
    assert any(name.startswith("meta-dat") for name in names), names
    assert not any(name.startswith("build.") for name in names), names
