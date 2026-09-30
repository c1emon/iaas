"""Fixed acceptance user-data and bounded, isolated snippet transport."""
from __future__ import annotations

import hashlib
import shlex
import subprocess
import time
from uuid import uuid4

import yaml

from iaas.common.errors import require
from iaas.pve_snippet_cleanup.runtime import Helper


def user_data(request: dict) -> str:
    user = request['template_record']['configuration'].get('ciuser')
    require(user is None or isinstance(user, str) and bool(user), 'invalid template cloud-init user')
    data = {'hostname': request['cloud_init']['hostname'], 'preserve_hostname': False,
            'manage_etc_hosts': True, 'users': [{'name': user, 'lock_passwd': True}] if user else ['default'],
            'ssh_pwauth': False, 'disable_root': user != 'root',
            'package_update': False, 'package_upgrade': False}
    return '#cloud-config\n' + yaml.safe_dump(data, sort_keys=False)


def record(request: dict, content: str) -> dict:
    vm = request['temporary_vm']
    storage = request['cloud_init']['snippet_storage']
    name = f'iaas-accept-{uuid4().hex}-{vm["vmid"]}-user-data.yml'
    return {'node': vm['node'], 'vmid': vm['vmid'], 'storage': storage,
            'file_name': name, 'file_id': f'{storage}:snippets/{name}',
            'sha256': hashlib.sha256(content.encode()).hexdigest(), 'uploaded': False}


class Snippets(Helper):
    def upload(self, snippet: dict, content: str) -> None:
        args = ['sudo', '-n', '/usr/local/sbin/iaas-pve-snippet-upload',
                '--storage', snippet['storage'], '--filename', snippet['file_name']]
        for suffix, payload in [(['--create-only'], content),
                                (['--verify', '--sha256', snippet['sha256']], None)]:
            remaining = self.deadline - time.monotonic()
            require(remaining > 0, 'snippet deadline expired')
            subprocess.run([*self.command, shlex.join([*args, *suffix])], input=payload,
                           env=self.env, capture_output=True, text=True, timeout=remaining, check=True)
