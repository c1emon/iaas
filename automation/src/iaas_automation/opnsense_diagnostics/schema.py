"""Shared request, inventory selection and protected output admission."""
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import UUID

import yaml

from iaas_automation.runtime_paths import validate_paths
from iaas_automation.opnsense_validation.aliases import ALIAS_NAME


class AdmissionError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AdmissionError(message)


def utc_time(value):
    require(isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z',value),
            'time selectors must be UTC RFC3339 strings')
    try:
        return datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        raise AdmissionError('invalid time selector') from None


def validate_request(data):
    require(isinstance(data,dict),'request must be a mapping')
    require(type(data.get('schema_version')) is int and data['schema_version']==1,'unsupported request version')
    kind=data.get('kind')
    require(kind in ('alias','rule_logs','states'),'unsupported diagnostic kind')
    common={'schema_version','kind','limit','include_details'}
    selectors={'alias':{'alias_name'},'rule_logs':{'rule','source_ip','destination_ip','protocol','source_port','destination_port','interface','since','until'},
               'states':{'source_ip','destination_ip','protocol','source_port','destination_port'}}
    require(not data.keys()-common-selectors[kind],'unknown or inappropriate request fields')
    request=data.copy();request.setdefault('limit',100);request.setdefault('include_details',False)
    require(type(request['limit']) is int and 1<=request['limit']<=1000,'limit must be an integer in 1..1000')
    require(type(request['include_details']) is bool,'include_details must be boolean')
    if kind=='alias':
        require(isinstance(request.get('alias_name'),str) and ALIAS_NAME.fullmatch(request['alias_name']),'invalid alias selector')
    else:
        require(any(key in request for key in ('source_ip','destination_ip','rule')),'a scoped selector is required')
    for key in ('source_ip','destination_ip'):
        if key in request:
            require(isinstance(request[key],str) and '%' not in request[key],'IP selector must be a literal address')
            try: request[key]=str(ipaddress.ip_address(request[key]))
            except ValueError: raise AdmissionError('IP selector must be a literal address') from None
    if 'protocol' in request:
        require(request['protocol'] in ('tcp','udp','icmp','icmpv6'),'invalid protocol selector')
    for key in ('source_port','destination_port'):
        if key in request:
            require(type(request[key]) is int and 1<=request[key]<=65535,'port selector must be an integer in 1..65535')
            require(request.get('protocol') in ('tcp','udp'),'ports require TCP or UDP')
    if 'interface' in request:
        require(isinstance(request['interface'],str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}',request['interface']),'invalid interface selector')
    if 'rule' in request:
        rule=request['rule'];require(isinstance(rule,dict),'invalid rule selector')
        require(set(rule) in ({'uuid'},{'scope','slug'}),'rule requires UUID or scope and slug')
        if 'uuid' in rule:
            try:
                require(isinstance(rule['uuid'],str) and str(UUID(rule['uuid']))==rule['uuid'],'invalid rule UUID')
            except (ValueError,AttributeError): raise AdmissionError('invalid rule UUID') from None
        else:
            require(all(isinstance(rule[k],str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,127}',rule[k]) for k in rule),'invalid rule identity')
    for key in ('since','until'):
        if key in request: utc_time(request[key])
    if 'since' in request and 'until' in request:
        require(utc_time(request['since'])<=utc_time(request['until']),'time window must be ordered')
    return request


def controller_target(target, groups, limit=None):
    require(isinstance(target,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',target),'an exact inventory target is required')
    require(target in groups.get('opnsense',[]) and target in groups.get('all',[]),'target must be one existing OPNsense host')
    require(not limit,'use the explicit diagnostic target without an Ansible --limit pattern')
    return 'localhost'


def admit(request_path, output_dir, detail_path, environment=None, inventories=()):
    request_path=Path(request_path)
    require(request_path.is_absolute() and request_path.is_file(),'request must be an explicit absolute file')
    require(request_path.stat().st_size<=65536,'request file exceeds size limit')
    try: request=validate_request(yaml.safe_load(request_path.read_text()))
    except (OSError,yaml.YAMLError): raise AdmissionError('cannot load request') from None
    require(isinstance(output_dir,str) and Path(output_dir).is_absolute(),'OUTPUT_DIR must be absolute')
    require(isinstance(detail_path,str),'invalid detail path')
    if not request['include_details']:
        require(not detail_path,'detail output requires include_details')
        return request,None
    require(bool(detail_path) and Path(detail_path).is_absolute(),'details require an explicit absolute output file')
    output=Path(detail_path);root=Path(output_dir)/'runtime/opnsense-diagnostics'
    require(output.resolve()!=root.resolve() and root.resolve() in output.resolve().parents,'detail output must be beneath the diagnostics root')
    require(not output.exists() or output.is_file(),'detail output must be a file')
    for component in [output,*output.parents]:
        require(not component.is_symlink(),'detail path must not contain symlinks')
        if component==Path(output_dir): break
    validate_paths(Path(environment) if environment else None,Path(__file__).resolve().parents[3],
                   [output], [request_path,*(Path(p) for p in inventories)])
    return request,output


def write_detail(path,result,rows,root):
    # The caller runs admission again immediately before this write.
    missing=[];parent=path.parent
    while not parent.exists(): missing.append(parent);parent=parent.parent
    for directory in reversed(missing): directory.mkdir(mode=0o700)
    for directory in [path.parent,*path.parent.parents]:
        directory.chmod(0o700)
        if directory==root: break
    descriptor,name=tempfile.mkstemp(prefix='.diagnostic-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w') as stream:
            json.dump(result|{'rows':rows},stream,indent=2);stream.write('\n')
        os.chmod(name,0o600);os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)
