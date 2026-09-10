"""Representative request, observation and output-boundary cases."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from iaas_automation.opnsense_diagnostics.adapter import MAX_PAGES,ObservationError,OPERATIONS,observe
from iaas_automation.opnsense_diagnostics.schema import AdmissionError,admit,controller_target,validate_request,write_detail

ROOT=Path(__file__).resolve().parents[1]/'fixtures/opnsense-capabilities'
FIXTURE=json.loads((ROOT/'diagnostic-responses.json').read_text())


class API:
    def __init__(self,**overrides):
        self.data={'aliases':FIXTURE['alias_configuration'],'table':FIXTURE['alias_table'],
                   'rules':FIXTURE['rule_configuration'],'rule_ids':FIXTURE['rule_ids'],
                   'logs':FIXTURE['logs'],'states':FIXTURE['states']}|overrides
        self.calls=[]
    def call(self,operation,payload=None,alias=None):
        assert operation in OPERATIONS
        self.calls.append((operation,payload,alias))
        value=deepcopy(self.data[operation])
        if isinstance(value,Exception): raise value
        if callable(value): return value(payload)
        return value


def request(kind='states',**extra):
    defaults={'alias':{'alias_name':'REMOTE_NETWORKS'},'rule_logs':{'source_ip':'198.51.100.10'},'states':{'source_ip':'198.51.100.10'}}
    return validate_request({'schema_version':1,'kind':kind}|defaults[kind]|extra)


@pytest.mark.parametrize('kind',['alias','rule_logs','states'])
def test_implemented_diagnostic_kinds(kind):
    api=API();result,rows=observe(api,request(kind),'fw')
    assert result['status']=='ok' and result['counts']['matched']==1 and len(rows)==1
    assert 'rows' not in result and 'https://lists' not in json.dumps(result)
    assert result['metadata']


@pytest.mark.parametrize('kind',['rule_logs','states'])
def test_zero_matches_is_only_for_evaluable_sample(kind):
    result,rows=observe(API(),request(kind,source_ip='203.0.113.9'),'fw')
    assert result['status']=='ok' and result['counts']['matched']==0 and not rows


@pytest.mark.parametrize('kind,override',[('alias',{'table':{'current':1,'rowCount':0,'total':0,'rows':[]}}),
                                         ('rule_logs',{'logs':[]}),('states',{'states':{'current':1,'rowCount':0,'total':0,'rows':[]}})])
def test_backend_empty_ambiguity(kind,override):
    result,rows=observe(API(**override),request(kind),'fw')
    assert result['status']=='unsupported' and result['observation_availability']=='unknown'
    assert all(v is None for v in result['counts'].values()) and not rows
    if kind=='alias': assert result['metadata']['configuration']['configured_entries']==1


def test_detectable_invalid_state_page_is_error():
    result,_=observe(API(states={'current':0,'rowCount':0,'total':0,'rows':[]}),request(),'fw')
    assert result['status']=='error' and result['reason']=='invalid_page'


def test_rule_mapping_and_required_fields():
    rule={'scope':'example','slug':'route'}
    result,_=observe(API(),request('rule_logs',rule=rule),'fw')
    assert result['status']=='ok' and result['metadata']['rule_correlation']['available']
    for mapping in [{'items':[]},{'items':FIXTURE['rule_ids']['items']*2}]:
        result,_=observe(API(rule_ids=mapping),request('rule_logs',rule=rule),'fw')
        assert result['status']=='unsupported' and result['counts']['matched'] is None
    row=deepcopy(FIXTURE['logs'][0]);row.pop('src')
    result,_=observe(API(logs=[row]),request('rule_logs'),'fw')
    assert result['status']=='unsupported'
    row=deepcopy(FIXTURE['states']['rows'][0]);row.pop('gateway');row.pop('nat_addr')
    result,_=observe(API(states=FIXTURE['states']|{'rows':[row]}),request(),'fw')
    assert result['status']=='ok' and result['metadata']['optional_fields']['gateway']['available_rows']==0


def test_missing_and_duplicate_configuration_identity():
    for rows in [[],FIXTURE['alias_configuration']['rows']*2]:
        api=API(aliases={'current':1,'rowCount':len(rows),'total':len(rows),'rows':rows})
        result,_=observe(api,request('alias'),'fw')
        assert result['status']=='error' and len(api.calls)==1


def test_and_semantics_ports_and_unknown_timezone():
    result,_=observe(API(),request('rule_logs',destination_ip='192.0.2.10',protocol='tcp',destination_port=80),'fw')
    assert result['status']=='ok' and result['counts']['matched']==0
    result,_=observe(API(),request('rule_logs',since='2026-09-10T00:00:00Z'),'fw')
    assert result['status']=='unsupported' and result['reason']=='timestamp_timezone_unavailable'
    row=deepcopy(FIXTURE['logs'][0]);row['__timestamp__']+='Z'
    result,_=observe(API(logs=[row]),request('rule_logs',since='2026-09-10T00:00:00Z',until='2026-09-11T00:00:00Z'),'fw')
    assert result['status']=='ok'


def test_pagination_and_row_limits_are_bounded():
    api=API(states=lambda payload: FIXTURE['states']|{'current':payload['current'],'total':10})
    result,rows=observe(api,request(limit=2),'fw')
    assert len(api.calls)==MAX_PAGES and len(rows)==2 and result['truncated']
    result,_=observe(API(),request('rule_logs',limit=1),'fw')
    assert result['truncated']
    result,_=observe(API(logs=FIXTURE['logs']*2),request('rule_logs',limit=1),'fw')
    assert result['status']=='unsupported' and result['truncated']


@pytest.mark.parametrize('failure',[ObservationError('error','authentication_failed'),ObservationError('error','permission_denied'),
                                   ObservationError('error','timeout'),ObservationError('unsupported','endpoint_unavailable'),
                                   ObservationError('unsupported','response_bound_exceeded')])
def test_api_failure_never_becomes_zero(failure):
    result,rows=observe(API(states=failure),request(),'fw')
    assert result['status']==failure.status and result['counts']['matched'] is None and not rows


@pytest.mark.parametrize('payload',[None,[],{'rows':'bad'},{'rows':[1],'current':1,'total':1,'rowCount':1}])
def test_malformed_response(payload):
    result,_=observe(API(states=payload),request(),'fw')
    assert result['status']=='error'


@pytest.mark.parametrize('patch',[{'schema_version':True},{'limit':True},{'limit':0},{'limit':1001},{'include_details':'true'},
                                  {'source_ip':'192.0.2.0/24'},{'source_ip':'host.invalid'},{'source_port':443},
                                  {'protocol':'tcp','source_port':'443'},{'rule':{'uuid':'bad'}},
                                  {'rule':{'scope':'x'}},{'rule':{'scope':'x','slug':'y','uuid':'bad'}},
                                  {'since':'2026-09-11T00:00:00Z','until':'2026-09-10T00:00:00Z'},
                                  {'since':'2026-09-10'},{'unknown':True}])
def test_request_rejection(patch):
    with pytest.raises(AdmissionError): request('rule_logs',**patch)


def test_kind_scope_and_target_selection():
    for data in [{'schema_version':1,'kind':'states'}, {'schema_version':1,'kind':'alias','alias_name':'A','source_ip':'192.0.2.1'},
                 {'schema_version':1,'kind':'states','source_ip':'192.0.2.1','rule':{'scope':'x','slug':'y'}}]:
        with pytest.raises(AdmissionError): validate_request(data)
    groups={'all':['fw','other'],'opnsense':['fw']}
    assert controller_target('fw',groups)=='localhost'
    for target,limit in [('',None),('*',None),('missing',None),('other',None),('fw','*')]:
        with pytest.raises(AdmissionError): controller_target(target,groups,limit)


def test_opt_in_paths_permissions_and_input_overlap(tmp_path):
    source=tmp_path/'request.yml';source.write_text(json.dumps(request('alias',include_details=True)))
    output=tmp_path/'output';root=output/'runtime/opnsense-diagnostics';path=root/'detail.json'
    _,selected=admit(str(source),str(output),str(path))
    write_detail(selected,{'schema_version':1},[{'ip':'192.0.2.1'}],root)
    assert root.stat().st_mode&0o777==0o700 and path.stat().st_mode&0o777==0o600
    with pytest.raises(ValueError): admit(str(source),str(output),str(path),inventories=[str(path)])
    link=root/'link.json';link.symlink_to(path)
    with pytest.raises(ValueError): admit(str(source),str(output),str(link))
    with pytest.raises(ValueError): admit(str(source),str(output),str(tmp_path/'outside.json'))
    with pytest.raises(ValueError): admit(str(source),str(output),'')
    source.write_text(json.dumps(request('alias')))
    with pytest.raises(ValueError): admit(str(source),str(output),str(path))
    assert admit(str(source),str(output),'')[1] is None


def test_optional_configuration_fields_do_not_block_evaluable_observation():
    config=deepcopy(FIXTURE['alias_configuration']);config['rows']=[{'name':'REMOTE_NETWORKS'}]
    result,_=observe(API(aliases=config),request('alias'),'fw')
    assert result['status']=='ok' and result['metadata']['configuration']['configured_entries'] is None
    rules=deepcopy(FIXTURE['rule_configuration']);rules['rows'][0].pop('uuid')
    result,_=observe(API(rules=rules),request('rule_logs',rule={'scope':'example','slug':'route'}),'fw')
    assert result['status']=='ok' and result['metadata']['configuration']['uuid'] is None
