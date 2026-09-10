"""Fixed read-only operations against the documented 26.1.11 response shapes."""
from datetime import datetime, timezone
import ipaddress
import json
import re
from typing import NoReturn
from urllib.parse import urlsplit
from uuid import UUID

import requests

from .schema import ALIAS_NAME,utc_time

MAX_RESPONSE_BYTES=2*1024*1024
MAX_TOTAL_BYTES=8*1024*1024
MAX_PAGES=5
OPERATIONS={
    'aliases':('POST','firewall/alias/search_item'),
    'table':('POST','firewall/alias_util/list'),
    'rules':('POST','firewall/filter/search_rule'),
    'rule_ids':('GET','diagnostics/firewall/list_rule_ids'),
    'logs':('GET','diagnostics/firewall/log'),
    'states':('POST','diagnostics/firewall/query_states'),
}


class ObservationError(Exception):
    def __init__(self,status,reason):
        self.status=status;self.reason=reason


def problem(reason,status='error') -> NoReturn:
    raise ObservationError(status,reason)


class Transport:
    def __init__(self,host,key,secret,verify=True):
        if not isinstance(host,str) or not host or not isinstance(key,str) or not key or not isinstance(secret,str) or not secret or type(verify) is not bool:
            problem('invalid_runtime_configuration')
        base=host if '://' in host else 'https://'+host
        try:
            parsed=urlsplit(base)
            if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username is not None or parsed.path not in ('','/') or parsed.query or parsed.fragment:
                problem('invalid_runtime_configuration')
            _=parsed.port
        except ValueError: problem('invalid_runtime_configuration')
        # Preserve caller-selected TLS verification; redirects and arbitrary operations are forbidden.
        self.base=base.rstrip('/')+'/api/';self.session=requests.Session()
        self.session.auth=(key,secret);self.verify=verify;self.used=0

    def close(self): self.session.close()

    def call(self,operation,payload=None,alias=None):
        if operation not in OPERATIONS: problem('unsupported_operation')
        method,path=OPERATIONS[operation]
        if operation=='table':
            if not isinstance(alias,str) or not ALIAS_NAME.fullmatch(alias): problem('invalid_alias_selector')
            path+='/'+alias
        try:
            with self.session.request(method,self.base+path,params=payload if method=='GET' else None,
                                      json=payload if method=='POST' else None,verify=self.verify,
                                      timeout=(5,15),allow_redirects=False,stream=True) as response:
                if response.status_code in (404,405,501): problem('endpoint_unavailable','unsupported')
                if response.status_code==401: problem('authentication_failed')
                if response.status_code==403: problem('permission_denied')
                if not 200<=response.status_code<300: problem('http_failure')
                content=bytearray()
                for chunk in response.iter_content(8192):
                    content.extend(chunk);self.used+=len(chunk)
                    if len(content)>MAX_RESPONSE_BYTES or self.used>MAX_TOTAL_BYTES:
                        problem('response_bound_exceeded','unsupported')
                try: return json.loads(content,parse_constant=lambda _: problem('malformed_json'))
                except (ValueError,UnicodeError): problem('malformed_json')
        except requests.Timeout: problem('timeout')
        except requests.RequestException: problem('transport_failure')


def page(data,current):
    if not isinstance(data,dict) or not isinstance(data.get('rows'),list): problem('malformed_page')
    if type(data.get('current')) is not int or data['current']!=current: problem('invalid_page')
    if type(data.get('total')) is not int or data['total']<0 or type(data.get('rowCount')) is not int or data['rowCount']<0:
        problem('malformed_page')
    if any(not isinstance(row,dict) for row in data['rows']) or len(data['rows'])>1000 or data['total']<len(data['rows']):
        problem('malformed_rows')
    return data['rows'],data['total']


def configuration(client,operation,selector):
    records=[];total=0
    for current in range(1,MAX_PAGES+1):
        rows,total=page(client.call(operation,{'rowCount':1000,'current':current}),current)
        records.extend(rows)
        if len(records)>=total: break
        if not rows: problem('incomplete_configuration','unsupported')
    if len(records)<total: problem('configuration_bound_exceeded','unsupported')
    matches=[]
    for row in records:
        for key in selector:
            if key not in row: problem('configuration_selector_unavailable','unsupported')
        if all(row[key]==value for key,value in selector.items()): matches.append(row)
    if not matches: problem('selected_object_not_found')
    if len(matches)!=1: problem('ambiguous_selected_object')
    return matches[0]


def timestamp(value):
    if not isinstance(value,str): return None
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo is not None else None
    except ValueError: return None


def match_row(row,request,kind,rid=None):
    fields={'source_ip':'src' if kind=='rule_logs' else 'src_addr',
            'destination_ip':'dst' if kind=='rule_logs' else 'dst_addr',
            'source_port':'srcport' if kind=='rule_logs' else 'src_port',
            'destination_port':'dstport' if kind=='rule_logs' else 'dst_port',
            'protocol':'protoname' if kind=='rule_logs' else 'proto','interface':'interface'}
    failures=[]
    for key,field in fields.items():
        if key not in request: continue
        try:
            if field not in row: problem('selector_field_unavailable','unsupported')
            value=row[field]
            if key.endswith('_ip'):
                try:
                    if not isinstance(value,str): raise ValueError
                    value=str(ipaddress.ip_address(value))
                except ValueError: problem('malformed_address')
            elif key.endswith('_port'):
                try:
                    if isinstance(value,bool) or not isinstance(value,(str,int)): raise ValueError
                    value=int(value)
                    if not 0<=value<=65535: raise ValueError
                except ValueError: problem('malformed_port')
            else:
                if not isinstance(value,str) or not value: problem('malformed_selector_field')
                if key=='protocol': value=value.lower()
            if value!=request[key]: return False
        except ObservationError as error:
            # An unrelated protocol/rule/address can still prove this row cannot match.
            failures.append(error)
    if rid is not None:
        if 'rid' not in row: failures.append(ObservationError('unsupported','rule_correlation_unavailable'))
        elif not isinstance(row['rid'],str): failures.append(ObservationError('error','malformed_rule_identity'))
        elif row['rid']!=rid: return False
    if 'since' in request or 'until' in request:
        observed=timestamp(row.get('__timestamp__'))
        if observed is None: failures.append(ObservationError('unsupported','timestamp_timezone_unavailable'))
        else:
            if 'since' in request and observed<utc_time(request['since']): return False
            if 'until' in request and observed>utc_time(request['until']): return False
    if failures:
        raise next((error for error in failures if error.status=='error'),failures[0])
    return True


def result_base(request,target):
    return {'schema_version':1,'target':target,'observed_at':datetime.now(timezone.utc).isoformat(),
            'kind':request.get('kind'),'selector':{k:v for k,v in request.items() if k not in {'schema_version','kind','limit','include_details'}},
            'status':'ok','reason':None,'observation_availability':'available',
            'counts':{'matched':None,'returned':None,'examined':None,'total':None},'truncated':False,
            'coverage':{'scope':'bounded_current_sample','pages':0},'metadata':{}}


def observe(client,request,target):
    kind=request['kind'];limit=request['limit'];rows=[]
    result=result_base(request,target)
    try:
        if kind=='alias':
            configured=configuration(client,'aliases',{'name':request['alias_name']})
            content=configured.get('content')
            alias_type=configured.get('type')
            if content is not None and not isinstance(content,str): problem('malformed_alias_configuration')
            if alias_type is not None and (not isinstance(alias_type,str) or not re.fullmatch(r'[a-z0-9_]{1,32}',alias_type)): problem('malformed_alias_configuration')
            count=(None if content is None or (',' in content and (alias_type is None or alias_type.startswith('url'))) else len([v for v in content.replace(',', '\n').splitlines() if v]))
            result['metadata']['configuration']={'name':request['alias_name'],'type':alias_type,
                'configured_entries':count,
                'enabled':(configured['enabled']=='1' if configured.get('enabled') in ('0','1') else None)}
            if result['metadata']['configuration']['configured_entries'] is None:
                result['metadata']['configuration']['count_reason']='not_exposed_or_ambiguous_content_separator'
            if alias_type is None: result['metadata']['configuration']['type_reason']='not_exposed'
            if result['metadata']['configuration']['enabled'] is None: result['metadata']['configuration']['enabled_reason']='not_exposed'
            result['metadata']['updated_at']={'value':None,'reason':'not_exposed_by_pinned_table_api'}
            raw,total=page(client.call('table',{'rowCount':limit,'current':1},alias=request['alias_name']),1)
            if not raw: problem('table_observation_unavailable','unsupported')
            for row in raw:
                if 'ip' not in row: problem('table_entry_unavailable','unsupported')
                try: ipaddress.ip_network(row['ip'],strict=False)
                except (ValueError,TypeError): problem('malformed_table_entry')
            rows=[{'ip':row['ip']} for row in raw[:limit]]
            result['counts']={'matched':total,'returned':len(rows),'examined':len(raw),'total':total}
            result['truncated']=len(rows)<total;result['coverage']['pages']=1
            result['metadata']['loaded_entries']=total
        else:
            rid=None;raw=[];total=None
            result['metadata']['rule_correlation']={'available':False,'reason':'not_requested'}
            if 'rule' in request:
                identity=request['rule']
                selector={'uuid':identity['uuid']} if 'uuid' in identity else {'description':f"iaas:opnsense:filter:{identity['scope']}:{identity['slug']}"}
                selected=configuration(client,'rules',selector)
                selected_uuid=selected.get('uuid')
                if selected_uuid is not None:
                    try:
                        if not isinstance(selected_uuid,str) or str(UUID(selected_uuid))!=selected_uuid: problem('malformed_rule_configuration')
                    except ValueError: problem('malformed_rule_configuration')
                result['metadata']['configuration']={'uuid':selected_uuid,'uuid_reason':None if selected_uuid else 'not_exposed'}
                mapping=client.call('rule_ids')
                if isinstance(mapping,dict) and 'items' not in mapping: problem('rule_correlation_unavailable','unsupported')
                if not isinstance(mapping,dict) or not isinstance(mapping.get('items'),list) or any(not isinstance(v,dict) for v in mapping['items']): problem('malformed_rule_mapping')
                matches=[v for v in mapping['items'] if selected_uuid and v.get('id')==selected_uuid]
                if not matches and 'description' in selector:
                    matches=[v for v in mapping['items'] if v.get('descr')==selector['description']]
                if len(matches)!=1 or not isinstance(matches[0].get('id'),str) or not matches[0]['id']:
                    problem('rule_correlation_unavailable','unsupported')
                rid=matches[0]['id'];result['metadata']['rule_correlation']={'available':True,'reason':None}
            if kind=='rule_logs':
                raw=client.call('logs',{'limit':limit})
                if not isinstance(raw,list) or any(not isinstance(v,dict) for v in raw): problem('malformed_log_rows')
                if len(raw)>limit: problem('row_bound_exceeded','unsupported')
                if not raw: problem('log_observation_unavailable','unsupported')
                result['truncated']=len(raw)>=limit
                result['coverage'].update(scope='recent_log_sample_not_history',pages=1)
                times=[timestamp(row.get('__timestamp__')) for row in raw]
                usable=[value for value in times if value is not None]
                result['coverage']['time_range']=([min(usable).isoformat(),max(usable).isoformat()] if usable and len(usable)==len(times) else None)
                result['coverage']['time_reason']=None if usable and len(usable)==len(times) else 'timezone_or_timestamp_unavailable'
            else:
                # Server search is only a candidate filter. Exact returned tuple matching is local.
                phrase=request.get('source_ip',request.get('destination_ip',''))
                for current in range(1,MAX_PAGES+1):
                    part,total=page(client.call('states',{'current':current,'rowCount':1000,'searchPhrase':phrase}),current)
                    raw.extend(part);result['coverage']['pages']=current
                    if len(raw)>=total: break
                    if not part: problem('incomplete_state_page','unsupported')
                if not raw: problem('state_observation_unavailable','unsupported')
                if total is None: problem('malformed_page')
                result['truncated']=len(raw)<total
                result['metadata']['tuple_semantics']='returned_src_addr_and_dst_addr'
            matched=[row for row in raw if match_row(row,request,kind,rid)]
            if kind=='states':
                for row in matched:
                    for field in ('route-to','reply-to','dup-to'):
                        if row.get(field) is not None and (not isinstance(row[field],str) or not row[field]):
                            problem('malformed_route_observation')
                    if row.get('rtable') is not None and (type(row['rtable']) is not int or row['rtable']<0):
                        problem('malformed_route_observation')
            fields=(('rid','src','dst','srcport','dstport','protoname','interface','action','dir','__timestamp__') if kind=='rule_logs'
                    else ('src_addr','dst_addr','src_port','dst_port','proto','iface','interface','nat_addr','nat_port','gateway',
                          'route-to','reply-to','dup-to','rtable','bytes','state'))
            rows=[{field:row[field] for field in fields if field in row} for row in matched[:limit]]
            result['truncated'] |= len(matched)>limit
            optional=('__timestamp__',) if kind=='rule_logs' else ('nat_addr','nat_port','gateway','route-to','reply-to','dup-to','rtable','interface','bytes')
            result['metadata']['optional_fields']={field:{
                'available_rows':sum((timestamp(row.get(field)) is not None if field=='__timestamp__' else row.get(field) is not None) for row in matched),
                'reason':'no_matching_observations' if not matched else 'only_reported_values_are_observed',
            } for field in optional}
            result['counts']={'matched':len(matched),'returned':len(rows),'examined':len(raw),'total':total}
    except ObservationError as error:
        result.update(status=error.status,reason=error.reason,observation_availability='unknown')
        result['counts']={key:None for key in result['counts']};rows=[]
        if 'bound' in error.reason or 'incomplete' in error.reason: result['truncated']=True
    return result,rows
