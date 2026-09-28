"""Real Linux OpenTofu/provider TLS smoke test, using only a loopback API stub.

Run with the current source mounted into the repository's runtime image::

    docker run --rm --entrypoint uv \
      -v "$PWD:/repo:ro" -e PYTHONPATH=/repo/src \
      iaas-runtime:refactor-local run --project /opt/iaas \
      python /repo/tests/integration/provider_private_ca.py

Downloads the provider selected by the existing fixture lock. No PVE or SSH
endpoint is contacted, and no resources are created. This is intentionally
separate from the default offline pytest suite.
"""

import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from iaas.runtime_execution.pve_provider import AUTH, prepare_provider_environment


def command(args, cwd, *, env=None):
    return subprocess.run(args, cwd=cwd, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=180, check=False)


def check_command(args, cwd, *, env=None):
    result = command(args, cwd, env=env)
    assert result.returncode == 0, result.stdout
    return result.stdout


def main():
    repo = Path(__file__).resolve().parents[2]
    version = json.loads(check_command(['tofu', 'version', '-json'], repo))
    assert version['platform'].startswith('linux_'), version
    dockerfile = (repo / 'automation/oci/iaas-runtime/Dockerfile').read_text()
    tofu_version = re.search(r'opentofu/releases/download/v([\d.]+)/', dockerfile)[1]
    assert version['terraform_version'] == tofu_version, version
    lock = repo / 'tests/fixtures/runtime-root/.terraform.lock.hcl'
    provider_version = re.search(r'version\s*=\s*"([^"]+)"', lock.read_text())[1]

    with tempfile.TemporaryDirectory(prefix='iaas-provider-tls-') as directory:
        work = Path(directory)
        # Synthetic material is temporary and never leaves this container.
        check_command(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                       '-keyout', 'ca.key', '-out', 'ca.pem', '-days', '1',
                       '-subj', '/CN=iaas synthetic provider CA',
                       '-addext', 'basicConstraints=critical,CA:TRUE'], work)
        check_command(['openssl', 'req', '-newkey', 'rsa:2048', '-nodes',
                       '-keyout', 'server.key', '-out', 'server.csr',
                       '-subj', '/CN=localhost'], work)
        (work / 'server.ext').write_text('subjectAltName=IP:127.0.0.1\n'
                                       'extendedKeyUsage=serverAuth\n')
        check_command(['openssl', 'x509', '-req', '-in', 'server.csr',
                       '-CA', 'ca.pem', '-CAkey', 'ca.key', '-CAcreateserial',
                       '-out', 'server.pem', '-days', '1', '-extfile', 'server.ext'], work)
        hits = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                body = json.dumps({'data': []}).encode()
                self.send_response(200 if self.path == '/api2/json/nodes' else 404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(work / 'server.pem', work / 'server.key')
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = f'https://127.0.0.1:{server.server_port}'
            document = {
                'terraform': {'required_providers': {'proxmox': {
                    'source': 'bpg/proxmox', 'version': provider_version}}},
                'provider': {'proxmox': {
                    'endpoint': '${var.pve_endpoint}', 'insecure': '${var.pve_insecure}',
                    'api_token': 'synthetic@pve!synthetic=synthetic'}},
                'variable': {'pve_endpoint': {'type': 'string'},
                             'pve_insecure': {'type': 'bool'}},
                'data': {'proxmox_virtual_environment_nodes': {'synthetic': {}}},
            }
            (work / 'main.tf.json').write_text(json.dumps(document))
            shutil.copyfile(lock, work / '.terraform.lock.hcl')
            base = {key: value for key, value in os.environ.items()
                    if key not in {'SSL_CERT_FILE', 'SSL_CERT_DIR', 'PVE_API_CA'}
                    and not key.startswith(('TF_VAR_', 'PROXMOX_VE_'))}
            base['HOME'] = str(work)
            base['TF_IN_AUTOMATION'] = '1'
            check_command(['tofu', 'init', '-backend=false', '-input=false',
                           '-lockfile=readonly', '-no-color'], work, env=base)
            for label, ca, insecure, success in (
                ('strict_without_ca', None, False, False),
                ('strict_private_ca', work / 'ca.pem', False, True),
                ('strict_next_task_without_ca', None, False, False),
                ('insecure_invalid_ca', work / 'invalid.pem', True, True),
            ):
                (work / 'invalid.pem').write_text('invalid synthetic CA')
                env = dict(base)
                env.update({'TF_VAR_' + name: 'synthetic' for name in AUTH})
                if ca is not None:
                    env['PVE_API_CA'] = str(ca)
                prepare_provider_environment({'api_endpoint': endpoint, 'insecure': insecure,
                                              'ssh_enabled': False}, {}, env)
                if success and not insecure:
                    bundle = Path(env['SSL_CERT_FILE']).read_bytes()
                    assert (work / 'ca.pem').read_bytes().strip() in bundle
                    assert len(bundle) > (work / 'ca.pem').stat().st_size * 10
                else:
                    assert 'SSL_CERT_FILE' not in env
                previous_hits = len(hits)
                result = command(['tofu', 'plan', '-input=false', '-no-color',
                                  '-lock=false'], work, env=env)
                if success:
                    assert result.returncode == 0, result.stdout
                    assert len(hits) > previous_hits
                    assert set(hits) == {'/api2/json/nodes'}
                else:
                    assert result.returncode != 0, result.stdout
                    assert 'certificate signed by unknown authority' in result.stdout, result.stdout
                    assert len(hits) == previous_hits
                print(f'{label}: PASS', flush=True)
            print(f'OpenTofu {tofu_version}; bpg/proxmox {provider_version}; '
                  f'{version["platform"]}; loopback TLS only', flush=True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
