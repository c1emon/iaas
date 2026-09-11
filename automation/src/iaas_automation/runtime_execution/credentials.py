"""Materialize explicit file credentials in the task's private home."""

from __future__ import annotations

import os
import json
from pathlib import Path
import shlex
import shutil
import stat

from iaas_automation.common.errors import require
from iaas_automation.common.io import write_text


AWS_FILE_VARIABLES = {"aws_credentials": "AWS_SHARED_CREDENTIALS_FILE", "aws_config": "AWS_SHARED_CONFIG_FILE",
                      "aws_ca": "AWS_CA_BUNDLE", "aws_web_identity": "AWS_WEB_IDENTITY_TOKEN_FILE"}


def protected_file(path: Path, *, secret: bool = True) -> None:
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid(), "protected file must be owned by the execution user")
    require(not info.st_mode & (0o077 if secret else 0o022), "protected file permissions are too broad")
    require(info.st_size > 0, "protected file is empty")


def prepare_file_credentials(files: dict[str, Path], home: Path, environ: dict[str, str]) -> None:
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    environ["HOME"] = str(home)
    for alias, variable in AWS_FILE_VARIABLES.items():
        if alias in files:
            protected_file(files[alias], secret=alias != "aws_ca")
            environ[variable] = str(files[alias])
    for variable in ("AWS_SHARED_CREDENTIALS_FILE", "AWS_SHARED_CONFIG_FILE", "AWS_CA_BUNDLE", "AWS_WEB_IDENTITY_TOKEN_FILE"):
        if variable in environ:
            protected_file(Path(environ[variable]), secret=variable != "AWS_CA_BUNDLE")
    if "runtime_secrets" in files:
        from iaas_automation.k3s_automation.secrets import load_protected_environment_json
        load_protected_environment_json(files["runtime_secrets"])
    if "known_hosts" not in files:
        return
    protected_file(files["known_hosts"], secret=False)
    ssh = home / ".ssh"
    ssh.mkdir(mode=0o700)
    shutil.copyfile(files["known_hosts"], ssh / "known_hosts")
    (ssh / "known_hosts").chmod(0o600)
    config = f"Host *\n    StrictHostKeyChecking yes\n    UserKnownHostsFile {json.dumps(str(ssh / 'known_hosts'))}\n"
    if "ssh_key" in files:
        protected_file(files["ssh_key"])
        shutil.copyfile(files["ssh_key"], ssh / "id_runtime")
        (ssh / "id_runtime").chmod(0o600)
        config += f"    IdentitiesOnly yes\n    IdentityFile {json.dumps(str(ssh / 'id_runtime'))}\n"
    write_text(ssh / "config", config, secure=True)
    environ["ANSIBLE_HOST_KEY_CHECKING"] = "True"
    environ["ANSIBLE_SSH_ARGS"] = f"-F {shlex.quote(str(ssh / 'config'))}"
