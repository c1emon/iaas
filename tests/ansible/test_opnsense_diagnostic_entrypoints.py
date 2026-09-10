"""Real Make/Ansible/HTTP diagnostic entrypoints against a local synthetic API."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading

import pytest
import requests
import yaml

from iaas_automation.opnsense_diagnostics.adapter import MAX_RESPONSE_BYTES,Transport,observe
from iaas_automation.opnsense_diagnostics.schema import validate_request

ROOT=Path(__file__).resolve().parents[2]
ANSIBLE=ROOT/'automation/ansible'
FIXTURE=json.loads((ROOT/'tests/fixtures/opnsense-capabilities/diagnostic-responses.json').read_text())


@pytest.fixture
def api():
    state={'calls':[],'status':200,'body':None}
    routes={'/api/firewall/alias/search_item':'alias_configuration',
            '/api/firewall/alias_util/list/REMOTE_NETWORKS':'alias_table',
            '/api/firewall/filter/search_rule':'rule_configuration',
            '/api/diagnostics/firewall/list_rule_ids':'rule_ids',
            '/api/diagnostics/firewall/log':'logs','/api/diagnostics/firewall/query_states':'states'}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def handle_query(self):
            path=self.path.split('?')[0]
            payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0)))) if self.command=='POST' else None
            state['calls'].append((self.command,path,payload))
            assert path in routes
            body=state['body'] if state['body'] is not None else json.dumps(FIXTURE[routes[path]]).encode()
            self.send_response(state['status']);self.send_header('Content-Type','application/json');self.end_headers()
            try: self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError): pass
        do_GET=handle_query
        do_POST=handle_query
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    state['url']=f'http://127.0.0.1:{server.server_port}'
    yield state
    server.shutdown();server.server_close();thread.join()


def prepare(tmp_path,api,kind='alias',details=False):
    environment=tmp_path/'environment with spaces';(environment/'ansible').mkdir(parents=True)
    inventory=environment/'ansible/inventory.yml'
    inventory.write_text(yaml.safe_dump({'all':{'children':{'opnsense':{'hosts':{'fw':{
        'opnsense_api_host':api['url'],'opnsense_api_key':'synthetic-key-private',
        'opnsense_api_secret':'synthetic-secret-private','opnsense_ssl_verify':True}}}},'hosts':{'other':{}}}}))
    payload={'schema_version':1,'kind':kind,'include_details':details}
    payload.update({'alias_name':'REMOTE_NETWORKS'} if kind=='alias' else {'source_ip':'198.51.100.10'})
    request=tmp_path/'request with spaces.json';request.write_text(json.dumps(payload))
    output=tmp_path/'output';detail=output/'runtime/opnsense-diagnostics/fw/detail.json'
    variables={'opnsense_diagnostics_target':'fw','opnsense_diagnostics_request':str(request),
               'opnsense_diagnostics_output':str(detail) if details else ''}
    return environment,inventory,request,output,detail,variables


def execute(tmp_path,settings,*,make=False,limit=None):
    environment,inventory,request,output,detail,variables=settings
    extra=tmp_path/'extra.json';extra.write_text(json.dumps(variables))
    env=os.environ|{'ANSIBLE_CONFIG':str(ANSIBLE/'ansible.cfg'),'ANSIBLE_LOCAL_TEMP':str(tmp_path/'local'),
                    'ENVIRONMENT_DIR':str(environment),'OUTPUT_DIR':str(output)}
    for name in ('OPNSENSE_TARGET','OPNSENSE_DIAGNOSTICS_REQUEST','OPNSENSE_DIAGNOSTICS_OUTPUT'):
        env.pop(name,None)
    if make:
        command=['make','-f',str(ROOT/'Makefile'),'opnsense-diagnose',
                 'OPNSENSE_TARGET='+variables['opnsense_diagnostics_target'],
                 'OPNSENSE_DIAGNOSTICS_REQUEST='+str(request),
                 'OPNSENSE_DIAGNOSTICS_OUTPUT='+variables['opnsense_diagnostics_output']]
    else:
        command=['uv','run','ansible-playbook','-i',str(inventory),str(ANSIBLE/'playbooks/opnsense/diagnostics.yml'),'-e','@'+str(extra)]
        if limit is not None: command.extend(['--limit',limit])
    result=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True)
    assert 'synthetic-key-private' not in result.stdout+result.stderr
    assert 'synthetic-secret-private' not in result.stdout+result.stderr
    assert 'https://lists.example.invalid' not in result.stdout
    return result


@pytest.mark.parametrize('kind',['alias','rule_logs','states'])
def test_direct_read_only_diagnostic(tmp_path,api,kind):
    settings=prepare(tmp_path,api,kind)
    result=execute(tmp_path,settings)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'matched: 1' in result.stdout
    assert not settings[3].exists()
    assert all(not any(word in path for word in ('reload','flush','kill','add','set','del_')) for _,path,_ in api['calls'])


def test_make_details_support_spaces_and_private_files(tmp_path,api):
    settings=prepare(tmp_path,api,details=True)
    result=execute(tmp_path,settings,make=True)
    assert result.returncode==0,result.stdout+result.stderr
    path=settings[4]
    assert path.stat().st_mode&0o777==0o600 and path.parent.stat().st_mode&0o777==0o700
    assert json.loads(path.read_text())['rows']==[{'ip':'192.0.2.0/24'}]
    assert '192.0.2.0/24' not in result.stdout


@pytest.mark.parametrize('target,limit',[('',None),('*',None),('missing',None),('other',None),('fw','other'),('fw','missing')])
def test_selection_fails_before_credentials_or_api(tmp_path,api,target,limit):
    settings=prepare(tmp_path,api);settings[-1]['opnsense_diagnostics_target']=target
    result=execute(tmp_path,settings,limit=limit)
    assert result.returncode!=0 and not api['calls']
    assert 'Run OPNsense API credential preflight' not in result.stdout


def test_invalid_request_precedes_credentials(tmp_path,api):
    settings=prepare(tmp_path,api)
    settings[2].write_text(json.dumps({'schema_version':1,'kind':'states','source_ip':'not-an-ip'}))
    result=execute(tmp_path,settings)
    assert result.returncode!=0 and not api['calls']
    assert 'Run OPNsense API credential preflight' not in result.stdout


@pytest.mark.parametrize('status,body,expected,reason',[
    (401,b'private backend body','error','authentication_failed'),
    (403,b'private backend body','error','permission_denied'),
    (404,b'private backend body','unsupported','endpoint_unavailable'),
    (500,b'private backend body','error','http_failure'),
    (200,b'{bad-json','error','malformed_json'),
    (200,b'['+b' '*(MAX_RESPONSE_BYTES+1)+b']','unsupported','response_bound_exceeded'),
])
def test_transport_classifies_failures_without_backend_body(api,status,body,expected,reason):
    api.update(status=status,body=body)
    client=Transport(api['url'],'key','secret')
    try: result,rows=observe(client,validate_request({'schema_version':1,'kind':'states','source_ip':'192.0.2.1'}),'fw')
    finally: client.close()
    assert result['status']==expected and result['reason']==reason and not rows
    assert result['counts']['matched'] is None and 'private backend body' not in json.dumps(result)


def test_timeout_is_explicit(monkeypatch):
    client=Transport('https://example.invalid','key','secret')
    def timeout(*args,**kwargs):
        assert kwargs['timeout']==(5,15) and kwargs['allow_redirects'] is False and kwargs['verify'] is True
        raise requests.Timeout('private backend message')
    monkeypatch.setattr(client.session,'request',timeout)
    try: result,_=observe(client,validate_request({'schema_version':1,'kind':'states','source_ip':'192.0.2.1'}),'fw')
    finally: client.close()
    assert result['reason']=='timeout' and 'private backend' not in json.dumps(result)


@pytest.mark.parametrize('status,body,expected',[(403,b'private backend body','error'),(200,b'[]','unsupported')])
def test_non_ok_observation_has_nonzero_entrypoint_exit(tmp_path,api,status,body,expected):
    api.update(status=status,body=body)
    settings=prepare(tmp_path,api,'rule_logs')
    result=execute(tmp_path,settings)
    assert result.returncode!=0 and f'status: {expected}' in result.stdout
    assert 'private backend body' not in result.stdout+result.stderr


def test_unsafe_detail_destination_never_contacts_api(tmp_path,api):
    settings=prepare(tmp_path,api,details=True)
    settings[-1]['opnsense_diagnostics_output']=str(tmp_path/'outside.json')
    result=execute(tmp_path,settings)
    assert result.returncode!=0 and not api['calls'] and not (tmp_path/'outside.json').exists()
