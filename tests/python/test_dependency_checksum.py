"""Archive validation and native readonly init verify different guarantees."""
import base64
import hashlib
import io
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile

import pytest

from iaas.common.errors import ValidationError
from iaas.runtime_execution.dependencies import restore_dependencies


def archive_package(path, lock, package_name, data):
    with tarfile.open(path, 'w:gz') as bundle:
        for name, content in [('.terraform.lock.hcl', lock), (package_name, data)]:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            member.mode = 0o755 if name != '.terraform.lock.hcl' else 0o600
            bundle.addfile(member, io.BytesIO(content))


def test_restore_rejects_member_and_lock_mismatch(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    (root / '.terraform.lock.hcl').write_bytes(b'caller-lock')
    for index, (lock, name) in enumerate([(b'caller-lock', '../escape'),
                                         (b'other-lock', '.terraform/providers/package')]):
        archive = tmp_path / f'{index}.tgz'
        archive_package(archive, lock, name, b'package')
        with pytest.raises(ValidationError):
            restore_dependencies(archive, root, tmp_path / f'restored-{index}')
        assert not (tmp_path / f'restored-{index}').exists()


@pytest.mark.skipif(shutil.which('tofu') is None, reason='native OpenTofu is required')
@pytest.mark.parametrize('tampered', [False, True])
def test_restored_package_native_readonly_checksum(tmp_path, tampered):
    # Native init verifies package bytes without executing this synthetic binary,
    # contacting a registry, or opening a backend. This is not download evidence.
    architecture = {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'amd64'}[platform.machine()]
    target = ('darwin' if platform.system() == 'Darwin' else 'linux') + '_' + architecture
    filename = 'terraform-provider-random_v3.6.3'
    data = b'synthetic provider package\n'
    file_hash = hashlib.sha256(data).hexdigest()
    directory_hash = hashlib.sha256(f'{file_hash}  {filename}\n'.encode()).digest()
    checksum = 'h1:' + base64.b64encode(directory_hash).decode()
    lock = (f'provider "registry.opentofu.org/hashicorp/random" {{\n'
            f'  version = "3.6.3"\n  hashes = ["{checksum}"]\n}}\n').encode()
    root = tmp_path / 'root'
    root.mkdir()
    (root / 'main.tf.json').write_text(json.dumps({'terraform': {'required_providers': {
        'random': {'source': 'hashicorp/random', 'version': '3.6.3'}}}}))
    (root / '.terraform.lock.hcl').write_bytes(lock)
    archive = tmp_path / 'dependencies.tgz'
    name = f'.terraform/providers/registry.opentofu.org/hashicorp/random/3.6.3/{target}/{filename}'
    archive_package(archive, lock, name, data + (b'tampered' if tampered else b''))
    providers = restore_dependencies(archive, root, tmp_path / 'restored')
    assert providers == tmp_path / 'restored/.terraform/providers'
    result = subprocess.run(['tofu', 'init', '-no-color', '-backend=false', '-input=false',
                             '-lockfile=readonly', '-get=false', f'-plugin-dir={providers}'],
                            cwd=root, env={'PATH': str(Path(shutil.which('tofu')).parent),
                                           'HOME': str(tmp_path)}, capture_output=True, text=True)
    assert (result.returncode != 0) == tampered, result.stdout + result.stderr
    if tampered:
        assert 'checksum' in result.stderr.lower()
    assert (root / '.terraform.lock.hcl').read_bytes() == lock
    assert not (root / 'terraform.tfstate').exists()
