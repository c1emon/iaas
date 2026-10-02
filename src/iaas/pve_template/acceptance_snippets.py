"""Fixed acceptance user-data and bounded, isolated snippet transport."""
from __future__ import annotations

import hashlib
import json
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
    def prospective_permissions(self, principal: str, vmid: int, pool: str) -> dict:
        require(self.budget is not None, 'permission inspection requires frozen deadlines')
        assert self.budget is not None
        cutoff = self.budget.deadlines[f'{self.phase}_deadline_at']
        return self.call(['--prospective-permissions', '--principal', principal,
                          '--vmid', str(vmid), '--pool', pool, '--deadline-at', cutoff])

    def inspect_file(self, snippet: dict) -> dict:
        require(self.budget is not None, 'snippet inspection requires frozen deadlines')
        assert self.budget is not None
        cutoff = self.budget.deadlines[f'{self.phase}_deadline_at']
        return self.call(['--inspect-file', '--storage', snippet['storage'],
                          '--filename', snippet['file_name'], '--sha256', snippet['sha256'],
                          '--deadline-at', cutoff])

    def capabilities(self, helper: str) -> dict:
        require(helper in {'upload', 'delete'}, 'invalid snippet helper')
        remaining = self.deadline - time.monotonic()
        if self.budget is not None:
            remaining = min(remaining, self.budget.remaining(self.phase))
        require(remaining > 0, 'snippet deadline expired')
        command = ['sudo', '-n', '/usr/local/sbin/iaas-pve-snippet-' + helper, '--capabilities']
        try:
            response = subprocess.run([*self.command, shlex.join(command)], env=self.env,
                                      capture_output=True, text=True, timeout=remaining, check=True)
            require(len(response.stdout) <= 16384, 'helper capability response exceeds limit')
            declaration = json.loads(response.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            from .admission import AdmissionError
            raise AdmissionError('helper_unavailable', object=helper) from None
        from .admission import require_helper_capabilities
        require_helper_capabilities(declaration, helper)
        return declaration

    def upload(self, snippet: dict, content: str) -> None:
        require(self.budget is not None, 'acceptance upload requires frozen deadlines')
        assert self.budget is not None
        args = ['sudo', '-n', '/usr/local/sbin/iaas-pve-snippet-upload',
                '--storage', snippet['storage'], '--filename', snippet['file_name'],
                '--mode', 'acceptance', '--deadline-at', self.budget.deadlines['work_deadline_at']]
        for suffix, payload in [(['--create-only'], content),
                                (['--verify', '--sha256', snippet['sha256']], None)]:
            remaining = min(self.deadline - time.monotonic(), self.budget.remaining('work'))
            require(remaining > 0, 'snippet deadline expired')
            subprocess.run([*self.command, shlex.join([*args, *suffix])], input=payload,
                           env=self.env, capture_output=True, text=True, timeout=remaining, check=True)
