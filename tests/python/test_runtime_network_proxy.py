import base64
import hashlib
import io
import os
import sys

import pytest

from iaas.runtime_execution.network_proxy import (
    ProxyConfigurationError, ProxyRedactor, normalize_proxy_environment, process_proxy_environment,
)
from iaas.runtime_execution.operations import capabilities, credential_names, process_environment
from iaas.runtime_execution.process import _capture_output, run_protected


@pytest.mark.parametrize('supplied', [
    {'http_proxy': ' http://proxy.example:3128 '},
    {'HTTP_PROXY': 'http://proxy.example:3128', 'http_proxy': 'http://proxy.example:3128'},
    {'HTTP_PROXY': ' ', 'http_proxy': 'http://proxy.example:3128'},
])
def test_proxy_normalization_and_independent_protocols(supplied):
    assert normalize_proxy_environment(supplied, network=True) == {
        'HTTP_PROXY': 'http://proxy.example:3128', 'http_proxy': 'http://proxy.example:3128'}
    assert normalize_proxy_environment(supplied, network=False) == {}


@pytest.mark.parametrize('value', [
    'socks5://proxy:1080', 'proxy:3128', 'http://', 'http://proxy:0', 'http://proxy:65536',
    'http://proxy:', 'http://proxy/path', 'http://proxy?', 'http://proxy#',
    'http://user%xx:password@proxy', 'http://:password@proxy', 'http://user@name:pass@proxy',
    'http://user%0A:pass@proxy', 'http://user%3Aname:pass@proxy', 'http://proxy\\evil',
])
def test_invalid_endpoints_do_not_echo_values(value):
    with pytest.raises(ProxyConfigurationError) as error:
        normalize_proxy_environment({'HTTPS_PROXY': value}, network=True)
    assert str(error.value) == 'HTTPS_PROXY has invalid proxy URL'


def test_conflicts_fail_closed_and_offline_does_not_parse():
    supplied = {'HTTP_PROXY': 'http://alice:secret@proxy', 'http_proxy': 'http://other'}
    with pytest.raises(ProxyConfigurationError, match='HTTP_PROXY/http_proxy proxy values conflict'):
        process_environment('pve', 'prepare-dependencies', supplied)
    assert process_environment('pve', 'check', supplied) == {}


def test_allowlist_and_capability():
    supplied = {'PATH': '/usr/bin', 'https_proxy': 'https://proxy:443/', 'NO_PROXY': ' target.example,10.0.0.7 ',
                'ALL_PROXY': 'socks5://ambient', 'FTP_PROXY': 'http://ambient',
                'AWS_SECRET_ACCESS_KEY': 'trap', 'PVE_API_TOKEN': 'trap', 'OP_TOKEN': 'trap', 'CUSTOM': 'trap'}
    assert process_environment('pve', 'prepare-dependencies', supplied) == {
        'PATH': '/usr/bin', 'HTTPS_PROXY': 'https://proxy:443/', 'https_proxy': 'https://proxy:443/',
        'NO_PROXY': 'target.example,10.0.0.7', 'no_proxy': 'target.example,10.0.0.7'}
    assert not credential_names('pve', 'prepare-dependencies')
    assert capabilities()['network_proxy_version'] == 1


@pytest.mark.parametrize('value', ['http://user:pass@proxy:80', 'http://user:@proxy',
                                 'https://us%65r:p%40ss@proxy:443', 'http://proxy:80/'])
def test_valid_basic_urls(value):
    assert normalize_proxy_environment({'HTTP_PROXY': value}, network=True)['http_proxy'] == value


def test_redaction_before_persistence_with_split_reads(tmp_path):
    proxy = 'http://unique%2Duser:synth%40password@proxy.example:3128'
    basic = base64.b64encode(b'unique-user:synth@password').decode()
    text = f'407 {proxy} unique%2Duser:synth%40password unique%2duser unique-user synth@password synth%40password Basic {basic}\n'
    class SplitReads(io.BytesIO):
        def read(self, size=-1):
            return super().read(7)
    destination = (tmp_path / 'capture').open('wb')
    failures = []
    with destination:
        _capture_output(SplitReads(text.encode()), destination, failures,
                        redactor=ProxyRedactor({'HTTP_PROXY': proxy}))
    protected = (tmp_path / 'capture').read_text()
    assert not failures and '[REDACTED]' in protected
    for secret in (proxy, 'unique%2Duser', 'unique%2duser', 'synth%40password', 'unique-user', 'synth@password', basic):
        assert secret not in protected


def test_actual_subprocess_receives_normalized_proxy_and_safe_capture(tmp_path):
    proxy = 'http://synthetic-user:synthetic-password@proxy.example:3128'
    environ = process_environment('pve', 'prepare-dependencies', {'http_proxy': proxy})
    script = "import os,sys; assert os.environ['HTTP_PROXY']==os.environ['http_proxy']; print(os.environ['HTTP_PROXY']); print('synthetic-user synthetic-password'); sys.exit(7)"
    capture = tmp_path / 'recovery.raw'
    result = run_protected([sys.executable, '-c', script], cwd=tmp_path, environ=environ, capture=capture)
    assert result.returncode == 7 and result.capture_complete
    assert 'synthetic' not in capture.read_text()
    assert '[REDACTED]' in capture.read_text()


def test_process_environment_updates_existing_urllib_opener_and_restores(monkeypatch):
    import urllib.request
    monkeypatch.setenv('HTTP_PROXY', 'http://ambient.example:80')
    monkeypatch.setenv('ALL_PROXY', 'socks5://ambient.example:80')
    old = urllib.request.build_opener()
    urllib.request.install_opener(old)
    normalized = normalize_proxy_environment({'http_proxy': 'http://controlled.example:3128',
                                              'no_proxy': 'target.example'}, network=True)
    with process_proxy_environment(normalized):
        assert os.environ['HTTP_PROXY'] == os.environ['http_proxy'] == 'http://controlled.example:3128'
        assert 'ALL_PROXY' not in os.environ
        handlers = [handler for handler in urllib.request._opener.handlers
                    if isinstance(handler, urllib.request.ProxyHandler)]
        assert handlers[0].proxies == {'http': 'http://controlled.example:3128'}
        assert urllib.request.proxy_bypass('target.example')
    assert os.environ['HTTP_PROXY'] == 'http://ambient.example:80'
    assert urllib.request._opener is old


def test_existing_image_download_consumes_authenticated_proxy_and_checksum(tmp_path):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from iaas.image.runtime import _download_base
    from iaas.common.errors import ValidationError
    body = b'controlled image fixture'
    observed = []
    expected_auth = 'Basic ' + base64.b64encode(b'fixture-user:fixture-password').decode()
    class Proxy(BaseHTTPRequestHandler):
        def do_GET(self):
            observed.append((self.path, self.headers.get('Proxy-Authorization') == expected_auth))
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    proxy = f'http://fixture-user:fixture-password@127.0.0.1:{server.server_port}'
    environ = normalize_proxy_environment({'HTTP_PROXY': proxy}, network=True)
    request = {'base': {'object_ref': 'http://target.synthetic.example/base.raw',
                        'checksum': {'algorithm': 'sha256', 'value': hashlib.sha256(body).hexdigest()}}}
    resources = {'work_min_free_bytes': 0, 'timeout_seconds': 5}
    try:
        with process_proxy_environment(environ):
            _download_base(request, tmp_path / 'base.raw', resources)
            assert (tmp_path / 'base.raw').read_bytes() == body
            request['base']['checksum']['value'] = '0' * 64
            with pytest.raises(ValidationError, match='checksum does not match'):
                _download_base(request, tmp_path / 'bad.raw', resources)
        assert observed == [('http://target.synthetic.example/base.raw', True)] * 2
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_basic_authentication_preserves_non_utf8_percent_decoded_bytes(tmp_path):
    proxy = 'http://synthetic%FFuser:synthetic%FEpassword@proxy.example:3128'
    environ = normalize_proxy_environment({'HTTP_PROXY': proxy}, network=True)
    raw_user, raw_password = b'synthetic\xffuser', b'synthetic\xfepassword'
    basic = base64.b64encode(raw_user + b':' + raw_password)
    text = b'407 Basic ' + basic + b' ' + raw_user + b' ' + raw_password + b'\n'
    capture = tmp_path / 'capture.raw'
    failures = []
    with capture.open('wb') as destination:
        _capture_output(io.BytesIO(text), destination, failures, redactor=ProxyRedactor(environ))
    assert not failures
    assert capture.read_bytes() == b'407 [REDACTED] [REDACTED] [REDACTED]\n'
