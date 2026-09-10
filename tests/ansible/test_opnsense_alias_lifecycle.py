"""Exercise actual alias task sequencing with an inert stateful API substitute."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / 'automation/ansible'


def alias(name, kind='host', content=None, state='present'):
    return dict(name=name,type=kind,content=content or ['192.0.2.1'],state=state,
                description='Synthetic private-description',enabled=True)


MODULE = '''
from ansible.module_utils.basic import AnsibleModule
import json
from pathlib import Path
m=AnsibleModule(argument_spec=dict(file=dict(required=True),action=dict(required=True),aliases=dict(type='list',elements='dict',default=[])),supports_check_mode=True)
p=Path(m.params['file']); state=json.loads(p.read_text()); action=m.params['action']
state['calls'].append(action)
def save(): p.write_text(json.dumps(state))
if action=='read':
    save();m.exit_json(changed=False,data=list(state['aliases'].values()))
if m.check_mode: m.fail_json(msg='mutation called in check mode')
if action=='reload':
    state['reloads']+=1;save();m.exit_json(changed=True)
changed=False
for a in m.params['aliases']:
    name=a['name']
    if name==state.get('fail_name'):
        save();m.fail_json(msg='synthetic write failure')
    if a['state']=='absent':
        if any(v['type']=='networkgroup' and name in v['content'] for v in state['aliases'].values()):
            save();m.fail_json(msg='server in-use guard')
        changed |= name in state['aliases'];state['aliases'].pop(name,None)
    else:
        if a['type']=='networkgroup' and any(n not in state['aliases'] for n in a['content']):
            save();m.fail_json(msg='provider reference admission')
        changed |= state['aliases'].get(name)!=a
        state['aliases'][name]=a
    if changed: state['changed'].append(name)
save();m.exit_json(changed=changed)
'''


def run_play(tmp_path, desired, live=(), check=False, force=False, fail_name=None, state_file=None):
    library=tmp_path/'library';library.mkdir(exist_ok=True)
    (library/'test_alias_api.py').write_text(MODULE)
    state_file=state_file or tmp_path/'state.json'
    if not state_file.exists():
        state_file.write_text(json.dumps(dict(aliases={r['name']:r for r in live}, calls=[],changed=[],reloads=0,fail_name=fail_name)))
    desired_file=tmp_path/'aliases.yml';desired_file.write_text(yaml.safe_dump({'opnsense_aliases':desired}))
    batch_path=tmp_path/'batch.yml'
    def convert(value):
        if isinstance(value,list): return [convert(v) for v in value]
        if isinstance(value,str):
            return value.replace('{{ playbook_dir }}/../../../..',str(ROOT)).replace('{{ playbook_dir }}/../../../src',str(ROOT/'automation/src'))
        if not isinstance(value,dict): return value
        result={}
        for key,item in value.items():
            if key in {'oxlorg.opnsense.list','oxlorg.opnsense.alias_multi','oxlorg.opnsense.reload'}:
                action={'oxlorg.opnsense.list':'read','oxlorg.opnsense.alias_multi':'write','oxlorg.opnsense.reload':'reload'}[key]
                result['test_alias_api']={'action':action,'file':str(state_file)}
                if action=='write':
                    assert item['reload'] is False
                    result['test_alias_api']['aliases']=item['aliases']
            elif key=='ansible.builtin.include_tasks': result[key]=str(batch_path)
            elif key=='ansible.builtin.import_tasks': result[key]=str(ANSIBLE/'playbooks/opnsense'/item)
            else: result[key]=convert(item)
        return result
    batch_path.write_text(yaml.safe_dump(convert(yaml.safe_load((ANSIBLE/'playbooks/opnsense/tasks/apply-alias-batch.yml').read_text()))))
    original=deepcopy(yaml.safe_load((ANSIBLE/'playbooks/opnsense/manage-aliases.yml').read_text())[0])
    original.pop('module_defaults');original['hosts']='localhost'
    original['vars']={'opnsense_alias_source':str(desired_file),'opnsense_api_key':'synthetic',
                      'opnsense_api_secret':'synthetic','opnsense_force_reload':force}
    play=tmp_path/'play.yml';play.write_text(yaml.safe_dump([convert(original)]))
    result=subprocess.run(['uv','run','ansible-playbook','-i','localhost,',str(play),*(['--check'] if check else [])],
                          cwd=ROOT,text=True,capture_output=True,env=os.environ|{'ANSIBLE_CONFIG':str(ANSIBLE/'ansible.cfg'),
                          'ANSIBLE_LIBRARY':str(library),'ANSIBLE_LOCAL_TEMP':str(tmp_path/'local')})
    assert 'private-description' not in result.stdout
    return result,json.loads(state_file.read_text())


def test_new_group_noop_and_force_reload(tmp_path):
    desired=[alias('GROUP','networkgroup',['HOST']),alias('HOST')]
    result,state=run_play(tmp_path,desired,[alias('UNLISTED')])
    assert result.returncode==0,result.stdout+result.stderr
    assert state['changed']==['HOST','GROUP'] and state['reloads']==1
    assert 'UNLISTED' in state['aliases']
    result,state=run_play(tmp_path,desired)
    assert result.returncode==0,result.stdout+result.stderr
    assert state['reloads']==1
    result,state=run_play(tmp_path,desired,force=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert state['reloads']==2


def test_check_mode_does_not_write_or_activate(tmp_path):
    result,state=run_play(tmp_path,[alias('GROUP','networkgroup',['HOST']),alias('HOST')],check=True,force=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert state['calls']==['read'] and not state['aliases'] and state['reloads']==0


@pytest.mark.parametrize('external', [False,True])
def test_invalid_graph_stops_before_first_write(tmp_path,external):
    desired=[alias('GROUP','networkgroup',['MISSING' if external else 'GROUP'])]
    result,state=run_play(tmp_path,desired)
    assert result.returncode!=0
    assert state['calls']==(['read'] if external else [])


def test_partial_write_stops_later_batches_and_activation(tmp_path):
    desired=[alias('LAST','networkgroup',['GROUP']),alias('GROUP','networkgroup',['HOST']),alias('HOST')]
    result,state=run_play(tmp_path,desired,fail_name='GROUP')
    assert result.returncode!=0
    assert state['changed']==['HOST'] and state['reloads']==0 and 'LAST' not in state['aliases']
    assert 'No rollback was performed' in result.stdout


def test_live_deletion_order_and_server_consumer_guard(tmp_path):
    desired=[alias('HOST',state='absent'),alias('GROUP','networkgroup',['OBSOLETE'],'absent')]
    result,state=run_play(tmp_path,desired,[alias('HOST'),alias('GROUP','networkgroup',['HOST'])])
    assert result.returncode==0,result.stdout+result.stderr
    assert state['changed']==['GROUP','HOST'] and state['reloads']==1
    other=tmp_path/'consumer';other.mkdir()
    result,state=run_play(other,[alias('HOST',state='absent')],[alias('HOST'),alias('EXTERNAL','networkgroup',['HOST'])])
    assert result.returncode!=0
    assert set(state['aliases'])=={'HOST','EXTERNAL'} and state['reloads']==0
