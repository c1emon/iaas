"""Observe actual OPNsense API routing through Requests, HTTPX and Ansible."""

import base64
import importlib
import json
import os
import select
import socket
import ssl
import subprocess
import sys
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest

from iaas.opnsense_diagnostics.adapter import Transport
from iaas.opnsense_workflow.contracts import save as save_candidate
from iaas.opnsense_workflow.executor import apply, verify
from iaas.opnsense_workflow.planning import coverage, plan
from iaas.opnsense_workflow.proxy import (
    ApiSession,
    api_environment,
    provider_environment,
)
from iaas.opnsense_workflow.reader import FixedCollectionTransport, Reader, _HttpFailure
from iaas.opnsense_workflow.runtime import target_from_inventory
from iaas.opnsense_workflow.writer import Writer, _AnsibleProvider

ROOT = Path(__file__).resolve().parents[2]
API_KEY = 'test-api-key'
API_SECRET = 'test-api-secret'
PROXY_USER = 'test-proxy-user'
PROXY_SECRET = 'test-proxy-secret'
API_AUTH = 'Basic ' + base64.b64encode(f'{API_KEY}:{API_SECRET}'.encode()).decode()
PROXY_AUTH = 'Basic ' + base64.b64encode(f'{PROXY_USER}:{PROXY_SECRET}'.encode()).decode()
PROXY_NAMES = ('HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy',
               'NO_PROXY', 'no_proxy', 'ALL_PROXY', 'all_proxy', 'FTP_PROXY', 'ftp_proxy')


class ApiHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def respond(self):
        authenticated = self.headers.get('Authorization') == API_AUTH
        self.server.calls.append((self.command, self.path, authenticated))
        payload = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        status = 200 if authenticated else 401
        if self.path == '/api/firewall/alias/get':
            data = {'alias': {'aliases': {'alias': self.server.aliases}}}
        elif self.path == '/api/firewall/group/get_item':
            data = {'group': {'members': {'lan': {'value': 'LAN'}}}}
        elif self.path == '/api/firewall/filter/get':
            data = {'filter': {'rules': {'rule': {}}}}
        elif self.path == '/api/firewall/d_nat/get':
            data = {'DNat': {'rule': {}}}
        elif self.path == '/api/firewall/one_to_one/get':
            data = {'filter': {'onetoone': {'rule': {}}}}
        elif self.path == '/api/firewall/group/get':
            data = {'group': {'ifgroupentry': {}}}
        elif self.path == '/api/routing/settings/search_gateway':
            data = {'rows': [], 'current': 1, 'rowCount': 1000, 'total': 0}
        elif self.path == '/api/core/firmware/status':
            data = {'product': {'product_version': '26.7.3'}}
        elif self.path == '/api/firewall/alias/add_item':
            row = json.loads(payload)['alias']
            self.server.aliases['synthetic-id'] = row
            data = {'result': 'saved', 'uuid': 'synthetic-id'}
        elif self.path.endswith('/reconfigure') or self.path.endswith('/apply'):
            data = {'status': 'ok'}
        elif self.path == '/api/diagnostics/firewall/log':
            data = []
        else:
            status, data = 404, {}
        encoded = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_CONNECT(self):
        authenticated = self.headers.get('Proxy-Authorization') == PROXY_AUTH
        self.server.calls.append((self.path, authenticated))
        if self.server.fail or not authenticated:
            self.send_error(502 if authenticated else 407)
            return
        host, port = self.path.rsplit(':', 1)
        upstream = socket.create_connection((host.strip('[]'), int(port)), timeout=3)
        try:
            self.send_response(200)
            self.end_headers()
            sockets = [self.connection, upstream]
            while True:
                readable, _, _ = select.select(sockets, [], [], 3)
                if not readable:
                    return
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (upstream if source is self.connection else self.connection).sendall(data)
        finally:
            upstream.close()


@contextmanager
def running(server):
    thread = Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.fixture(scope='module')
def certificate(tmp_path_factory):
    root = tmp_path_factory.mktemp('opnsense-api-tls')
    cert, key = root / 'cert.pem', root / 'key.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-keyout', str(key), '-out', str(cert), '-days', '1', '-subj', '/CN=localhost',
                    '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1'],
                   check=True, capture_output=True, timeout=20)
    return cert, key


@pytest.fixture
def wire(certificate, monkeypatch):
    for name in PROXY_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv('REQUESTS_CA_BUNDLE', raising=False)
    monkeypatch.delenv('CURL_CA_BUNDLE', raising=False)
    cert, key = certificate
    api = ThreadingHTTPServer(('127.0.0.1', 0), ApiHandler)
    api.calls, api.aliases = [], {}
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    api.socket = context.wrap_socket(api.socket, server_side=True)
    proxy = ThreadingHTTPServer(('127.0.0.1', 0), ProxyHandler)
    proxy.calls, proxy.fail = [], False
    with running(api), running(proxy):
        yield SimpleNamespace(api=api, proxy=proxy, ca=cert,
                              endpoint=f'https://127.0.0.1:{api.server_port}',
                              proxy_url=f'http://{PROXY_USER}:{PROXY_SECRET}@127.0.0.1:{proxy.server_port}')


@pytest.fixture
def provider_session(monkeypatch):
    paths = os.environ.get('ANSIBLE_COLLECTIONS_PATH', '').split(os.pathsep)
    root = next((Path(path) for path in paths if path and
                 (Path(path) / 'ansible_collections/oxlorg/opnsense').is_dir()),
                ROOT / 'automation/ansible/collections')
    monkeypatch.syspath_prepend(str(root))
    return importlib.import_module('ansible_collections.oxlorg.opnsense.plugins.module_utils.base.api').Session


def module_for(wire, *, use_proxy=False, host='127.0.0.1'):
    def fail_json(*args, **kwargs):
        raise RuntimeError(kwargs.get('msg', args[0] if args else 'provider failed'))

    return SimpleNamespace(params={
        'firewall': host, 'api_port': wire.api.server_port, 'api_key': API_KEY,
        'api_secret': API_SECRET, 'api_credential_file': None, 'ssl_verify': True,
        'ssl_ca_file': str(wire.ca), 'api_timeout': 3, 'api_retries': 0,
        'debug': False,
    }, fail_json=fail_json)


def read_both(wire, provider_session, monkeypatch, use_proxy, host='127.0.0.1'):
    endpoint = f'https://{host}:{wire.api.server_port}'
    monkeypatch.setenv('REQUESTS_CA_BUNDLE', str(wire.ca))
    transport = FixedCollectionTransport(
        {'endpoint': endpoint, 'ssl_verify': True, 'api_use_proxy': use_proxy},
        {'OPNSENSE_API_KEY': API_KEY, 'OPNSENSE_API_SECRET': API_SECRET})
    try:
        assert transport.list('alias') == []
    finally:
        transport.close()
    with provider_environment(os.environ, use_proxy), provider_session(module_for(wire, host=host)) as session:
        assert session.get({'module': 'firewall', 'controller': 'alias', 'command': 'get'}) == {
            'alias': {'aliases': {'alias': {}}}}


@pytest.mark.parametrize('use_proxy,rule,host,proxied', [
    (False, '', '127.0.0.1', False),
    (True, '', '127.0.0.1', True),
    (False, '', 'localhost', False),
    (True, '', 'localhost', True),
])
@pytest.mark.parametrize('lower', [False, True])
def test_actual_read_routing_and_auth(wire, provider_session, monkeypatch,
                                      use_proxy, rule, host, proxied, lower):
    monkeypatch.setenv('https_proxy' if lower else 'HTTPS_PROXY', wire.proxy_url)
    monkeypatch.setenv('no_proxy' if lower else 'NO_PROXY', rule)
    from iaas.runtime_execution.network_proxy import normalize_proxy_environment
    for name, value in normalize_proxy_environment(os.environ, network=True).items():
        monkeypatch.setenv(name, value)
    # An unsupported ambient channel must not override the explicit decision.
    monkeypatch.setenv('ALL_PROXY', 'http://127.0.0.1:1')
    read_both(wire, provider_session, monkeypatch, use_proxy, host)
    assert len(wire.api.calls) == 2 and all(row[2] for row in wire.api.calls)
    assert len(wire.proxy.calls) == (2 if proxied else 0)
    assert all(row[1] for row in wire.proxy.calls)


def test_no_applicable_proxy_and_disabled_invalid_environment(wire, provider_session, monkeypatch):
    monkeypatch.setenv('HTTP_PROXY', wire.proxy_url)
    monkeypatch.setenv('ALL_PROXY', wire.proxy_url)
    read_both(wire, provider_session, monkeypatch, True)
    monkeypatch.setenv('HTTPS_PROXY', 'invalid')
    monkeypatch.setenv('https_proxy', wire.proxy_url)
    monkeypatch.setenv('NO_PROXY', '[invalid')
    read_both(wire, provider_session, monkeypatch, False)
    assert len(wire.api.calls) == 4 and wire.proxy.calls == []


def test_selected_proxy_failure_never_reaches_api(wire, provider_session, monkeypatch):
    wire.proxy.fail = True
    monkeypatch.setenv('HTTPS_PROXY', wire.proxy_url)
    monkeypatch.setenv('REQUESTS_CA_BUNDLE', str(wire.ca))
    transport = FixedCollectionTransport({'endpoint': wire.endpoint, 'ssl_verify': True, 'api_use_proxy': True},
                                         {'OPNSENSE_API_KEY': API_KEY, 'OPNSENSE_API_SECRET': API_SECRET})
    try:
        with pytest.raises(_HttpFailure) as read_error:
            transport.list('alias')
    finally:
        transport.close()
    with provider_environment(os.environ, True), provider_session(module_for(wire)) as session:
        with pytest.raises(Exception) as provider_error:
            session.post({'module': 'firewall', 'controller': 'alias', 'command': 'reconfigure'})
    assert wire.api.calls == [] and len(wire.proxy.calls) == 2
    for error in (read_error, provider_error):
        assert API_SECRET not in str(error.value) and PROXY_SECRET not in str(error.value)


@pytest.mark.parametrize('use_proxy', [False, True])
def test_ipv6_actual_routing(certificate, wire, provider_session, monkeypatch, use_proxy):
    class IPv6Server(ThreadingHTTPServer):
        address_family = socket.AF_INET6

    try:
        api = IPv6Server(('::1', 0), ApiHandler)
    except OSError:
        pytest.skip('IPv6 loopback is unavailable in this test environment')
    api.calls, api.aliases = [], {}
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(*certificate)
    api.socket = context.wrap_socket(api.socket, server_side=True)
    monkeypatch.setenv('HTTPS_PROXY', wire.proxy_url)
    monkeypatch.setenv('NO_PROXY', '')
    monkeypatch.setenv('REQUESTS_CA_BUNDLE', str(wire.ca))
    with running(api):
        transport = FixedCollectionTransport(
            {'endpoint': f'https://[::1]:{api.server_port}', 'ssl_verify': True, 'api_use_proxy': use_proxy},
            {'OPNSENSE_API_KEY': API_KEY, 'OPNSENSE_API_SECRET': API_SECRET})
        try:
            assert transport.list('alias') == []
        finally:
            transport.close()
        params = module_for(wire, use_proxy=True, host='::1')
        params.params['api_port'] = api.server_port
        with provider_environment(os.environ, use_proxy), provider_session(params) as session:
            session.get({'module': 'firewall', 'controller': 'alias', 'command': 'get'})
        assert len(api.calls) == 2 and all(row[2] for row in api.calls)
    assert len(wire.proxy.calls) == (2 if use_proxy else 0)


class StageExecution:
    def __init__(self, root, environment):
        self.root, self.environ, self.logs = root, environment, []
        self.outputs = self

    def path(self, category):
        path = self.root / category
        path.mkdir(parents=True, exist_ok=True)
        return path

    def run(self, phase, command, cwd):
        result = subprocess.run(command, cwd=cwd, env=self.environ,
                                capture_output=True, text=True, timeout=45, check=False)
        self.logs.append(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError('Ansible stage failed')


@pytest.mark.parametrize('use_proxy,rule,proxied', [(False, '', False), (True, '', True),
                                                 (False, '127.0.0.0/8', False)])
def test_workflow_read_save_activate_same_route(wire, monkeypatch, tmp_path, use_proxy, rule, proxied):
    monkeypatch.setenv('HTTPS_PROXY', wire.proxy_url)
    monkeypatch.setenv('NO_PROXY', rule)
    # This test exercises the real stage playbook; TLS validation is covered in
    # the wire tests above (the existing writer target supports a boolean).
    inventory = {'opnsense': {'hosts': {'fw': {'opnsense_api_host': wire.endpoint,
                  'opnsense_ssl_verify': False, 'opnsense_api_use_proxy': use_proxy}}}}
    target = target_from_inventory(inventory, 'fw')
    transport = FixedCollectionTransport(target, {'OPNSENSE_API_KEY': API_KEY, 'OPNSENSE_API_SECRET': API_SECRET})
    try:
        assert transport.list('alias') == []
    finally:
        transport.close()
    env = dict(os.environ, OPNSENSE_API_KEY=API_KEY, OPNSENSE_API_SECRET=API_SECRET,
               PYTHONPATH=str(ROOT / 'src'), ANSIBLE_CONFIG=str(ROOT / 'automation/ansible/ansible.cfg'),
               ANSIBLE_PYTHON_INTERPRETER=sys.executable, ANSIBLE_LOCAL_TEMP=str(tmp_path / 'ansible'))
    execution = StageExecution(tmp_path, env)
    writer = _AnsibleProvider(execution, target)
    save = writer.save('aliases', [{'name': 'PROXY_TEST', 'type': 'host', 'content': ['192.0.2.1'],
                                  'description': 'test', 'enabled': True, 'state': 'present'}], reload=False)
    assert save['status'] == 'accepted', execution.logs
    assert not any(path.endswith('/reconfigure') for _, path, _ in wire.api.calls)
    activate = writer.activate('aliases')
    assert activate['status'] == 'confirmed', execution.logs
    assert sum(path.endswith('/add_item') for _, path, _ in wire.api.calls) == 1
    assert sum(path.endswith('/reconfigure') for _, path, _ in wire.api.calls) == 1
    assert all(authenticated for _, _, authenticated in wire.api.calls)
    assert bool(wire.proxy.calls) is proxied
    assert all(authenticated for _, authenticated in wire.proxy.calls)
    assert execution.environ == env
    for secret in (API_SECRET, PROXY_SECRET, API_AUTH, PROXY_AUTH, wire.proxy_url):
        assert secret not in ''.join(execution.logs)
        assert all(secret not in path.read_text() for path in (tmp_path / 'work').rglob('*.json'))


@pytest.mark.parametrize('stage', ['save', 'activate'])
def test_workflow_proxy_failure_no_fallback_or_replay(wire, monkeypatch, tmp_path, stage):
    wire.proxy.fail = True
    monkeypatch.setenv('HTTPS_PROXY', wire.proxy_url)
    target = {'host': 'fw', 'endpoint': wire.endpoint, 'ssl_verify': False, 'api_use_proxy': True}
    env = dict(os.environ, OPNSENSE_API_KEY=API_KEY, OPNSENSE_API_SECRET=API_SECRET,
               PYTHONPATH=str(ROOT / 'src'), ANSIBLE_CONFIG=str(ROOT / 'automation/ansible/ansible.cfg'),
               ANSIBLE_PYTHON_INTERPRETER=sys.executable, ANSIBLE_LOCAL_TEMP=str(tmp_path / 'ansible'))
    execution = StageExecution(tmp_path, env)
    writer = _AnsibleProvider(execution, target)
    if stage == 'save':
        result = writer.save('aliases', [{'name': 'PROXY_TEST', 'type': 'host', 'content': ['192.0.2.1'],
                                        'enabled': True, 'state': 'present', 'description': 'test'}], reload=False)
    else:
        result = writer.activate('aliases')
    assert result['status'] == 'failed'
    assert wire.api.calls == [] and len(wire.proxy.calls) == 1
    for secret in (API_SECRET, PROXY_SECRET, API_AUTH, PROXY_AUTH, wire.proxy_url):
        assert secret not in ''.join(execution.logs)
        assert all(secret not in path.read_text() for path in tmp_path.rglob('*.json'))


def test_diagnostics_use_same_proxy_policy(wire, monkeypatch):
    monkeypatch.setenv('https_proxy', wire.proxy_url)
    monkeypatch.setenv('REQUESTS_CA_BUNDLE', str(wire.ca))
    transport = Transport(wire.endpoint, API_KEY, API_SECRET, api_use_proxy=True)
    try:
        assert transport.call('logs') == []
    finally:
        transport.close()
    assert len(wire.proxy.calls) == 1 and len(wire.api.calls) == 1


def test_proxy_flag_boolean_validation_and_inventory_inheritance():
    inventory = {'opnsense': {'vars': {'opnsense_api_use_proxy': True},
                              'hosts': {'fw': {'opnsense_api_host': '127.0.0.1'}}}}
    assert target_from_inventory(inventory, 'fw')['api_use_proxy'] is True
    inventory['opnsense']['hosts']['fw']['opnsense_api_use_proxy'] = False
    assert target_from_inventory(inventory, 'fw')['api_use_proxy'] is False
    for value in ('false', 0, None):
        with pytest.raises(ValueError):
            ApiSession(value)


@pytest.mark.parametrize('use_proxy', [False, True])
def test_provider_environment_is_scoped_and_restored_after_error(use_proxy):
    original = {'HTTPS_PROXY': 'http://proxy:8080', 'https_proxy': 'http://proxy:8080',
                'NO_PROXY': '10.0.0.0/8', 'ALL_PROXY': 'http://unsupported:8080',
                'OPNSENSE_API_SECRET': API_SECRET, 'REQUESTS_CA_BUNDLE': '/test/ca.pem'}
    environment = dict(original)
    selected = api_environment(environment, use_proxy)
    assert selected['HTTPS_PROXY'] == (original['HTTPS_PROXY'] if use_proxy else '')
    assert selected['NO_PROXY'] == (original['NO_PROXY'] if use_proxy else '')
    assert selected['ALL_PROXY'] == ''
    with pytest.raises(RuntimeError):
        with provider_environment(environment, use_proxy):
            assert environment['HTTPS_PROXY'] == selected['HTTPS_PROXY']
            assert environment['NO_PROXY'] == selected['NO_PROXY']
            assert environment['ALL_PROXY'] == ''
            assert environment['OPNSENSE_API_SECRET'] == API_SECRET
            assert environment['REQUESTS_CA_BUNDLE'] == '/test/ca.pem'
            raise RuntimeError('synthetic provider failure')
    assert environment == original


@pytest.mark.parametrize('use_proxy', [False, True])
def test_actual_plan_apply_verify_use_same_setting(wire, monkeypatch, tmp_path, use_proxy):
    monkeypatch.setenv('HTTPS_PROXY', wire.proxy_url)
    target = {'host': 'fw', 'endpoint': wire.endpoint, 'ssl_verify': False, 'api_use_proxy': use_proxy}
    credentials = {'OPNSENSE_API_KEY': API_KEY, 'OPNSENSE_API_SECRET': API_SECRET}
    reader = Reader(target, credentials)
    record = {'name': 'PROXY_TEST', 'type': 'host', 'content': ['192.0.2.1'],
              'description': 'test', 'enabled': True, 'state': 'present'}
    documents = {'aliases': {'opnsense_aliases': [record]}}
    request = {'schema_version': 1, 'selection': {'aliases': 'all'}}
    runtime = {'image_digest': 'sha256:' + 'a' * 64, 'platform': 'linux/arm64', 'interface_version': 1}
    env = dict(os.environ, **credentials, PYTHONPATH=str(ROOT / 'src'),
               ANSIBLE_CONFIG=str(ROOT / 'automation/ansible/ansible.cfg'),
               ANSIBLE_PYTHON_INTERPRETER=sys.executable, ANSIBLE_LOCAL_TEMP=str(tmp_path / 'ansible'))
    execution = StageExecution(tmp_path, env)
    try:
        candidate = plan(documents, request, reader.read(coverage([{'resource': 'aliases'}])),
                         target, runtime, {'inputs': []})
        assert candidate['admission']['status'] == 'ready'
        assert candidate['target']['api_use_proxy'] is use_proxy
        assert all(method == 'GET' or path.endswith('/search_gateway') for method, path, _ in wire.api.calls)
        digest = save_candidate(tmp_path / 'candidate.json', candidate)
        result = apply(candidate, digest, reader, Writer(_AnsibleProvider(execution, target)),
                       'execution-1', {'target': target, 'candidate_sha256': digest,
                                       'execution_id': 'execution-1', 'checked_no_pending': True,
                                       'serialized': True}, tmp_path / 'recovery')
        assert result['status'] != 'failed', result
        assert verify(candidate, reader)['status'] == 'fully_verified'
        assert sum(path.endswith('/add_item') for _, path, _ in wire.api.calls) == 1
        assert sum(path.endswith('/reconfigure') for _, path, _ in wire.api.calls) == 1
        assert bool(wire.proxy.calls) is use_proxy
        assert all(authenticated for _, _, authenticated in wire.api.calls)
        for secret in (API_SECRET, PROXY_SECRET, wire.proxy_url):
            assert secret not in ''.join(execution.logs)
    finally:
        reader.close()
