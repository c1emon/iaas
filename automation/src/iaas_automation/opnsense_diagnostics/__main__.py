"""Internal controller command; credentials arrive only through stdin."""
import argparse
import base64
import json
from pathlib import Path
import re
import sys

from .adapter import ObservationError,Transport,observe,result_base
from .schema import admit,write_detail


def redact(value,secrets):
    if isinstance(value,str):
        for secret in secrets:
            if secret: value=value.replace(secret,'[redacted]')
    elif isinstance(value,list): value=[redact(item,secrets) for item in value]
    elif isinstance(value,dict): value={key:redact(item,secrets) for key,item in value.items()}
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',required=True)
    parser.add_argument('--target',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--detail',default='')
    parser.add_argument('--environment',default='')
    parser.add_argument('--inventories',default='[]')
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    client=None
    result=result_base({},None)
    result.update(status='error',reason='invalid_request_or_paths',observation_availability='unknown')
    try:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',args.target): raise ValueError
        if not args.environment or not Path(args.environment).is_absolute() or not Path(args.environment).is_dir(): raise ValueError
        inventories=json.loads(args.inventories)
        if not isinstance(inventories,list) or any(not isinstance(p,str) for p in inventories): raise ValueError
        request,path=admit(args.request,args.output_dir,args.detail,args.environment,inventories)
        if not args.execute:
            print(json.dumps({'valid':True}));return 0
        result=result_base(request,args.target)
        try:
            config=json.loads(sys.stdin.read(65537))
            if not isinstance(config,dict): raise ValueError
            key=config.get('api_key');secret=config.get('api_secret')
            client=Transport(config.get('host'),key,secret,config.get('ssl_verify',True))
        except (ValueError,TypeError,ObservationError):
            result.update(status='error',reason='invalid_runtime_configuration',observation_availability='unknown')
            print(json.dumps(result));return 1
        result,rows=observe(client,request,args.target)
        secrets=(key,secret,base64.b64encode(f'{key}:{secret}'.encode()).decode())
        result=redact(result,secrets);rows=redact(rows,secrets)
        if path is not None:
            admit(args.request,args.output_dir,args.detail,args.environment,inventories)
            write_detail(path,result,rows,Path(args.output_dir)/'runtime/opnsense-diagnostics')
        print(json.dumps(result))
        return 0 if result['status']=='ok' else 1
    except (OSError,ValueError,TypeError):
        result.update(status='error',reason='invalid_request_or_output',observation_availability='unknown')
        result['counts']={key:None for key in result['counts']}
        print(json.dumps(result));return 1
    finally:
        if client is not None: client.close()


if __name__=='__main__':
    raise SystemExit(main())
