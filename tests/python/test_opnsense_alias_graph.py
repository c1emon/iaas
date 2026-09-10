"""Alias type admission and effective desired/live dependency planning."""
from copy import deepcopy

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_validation import validate_document
from iaas_automation.opnsense_validation.aliases import plan_aliases


def alias(name, kind='host', content=None, state='present', **extra):
    return dict(name=name, type=kind, content=content or ['192.0.2.1'],
                description='Synthetic', enabled=True, state=state, **extra)


def plan(desired, live):
    validate_document('aliases', {'opnsense_aliases': desired})
    return plan_aliases(desired, live)


@pytest.mark.parametrize('frequency', ['1', '1.0', '0.5', '0.1', '12.3'])
def test_url_table_frequency(frequency):
    desired=[alias('TABLE', 'urltable', ['https://lists.example.invalid/networks?v=1'], updatefreq_days=frequency)]
    assert plan(desired, [])['would_change']


@pytest.mark.parametrize('frequency', [1, 0.5, True, '0', '0.01', '0.15', '-1', '+1', ' 1', '1 ', '1e2', 'NaN', 'Infinity', '9007199254740993', '9'*400])
def test_reject_invalid_or_lossy_frequency(frequency):
    with pytest.raises(ValidationError):
        plan([alias('TABLE', 'urltable', ['https://lists.example.invalid/table'], updatefreq_days=frequency)], [])


@pytest.mark.parametrize('url', ['ftp://example.invalid/x', '/relative', 'https://user:pass@example.invalid/x',
                                  'https://example.invalid/x#', 'https://example.invalid/x#part',
                                  'https://example.invalid/x?token=private', 'https://example.invalid:99999/x'])
def test_reject_url_syntax_without_leaking_source(url):
    with pytest.raises(ValidationError) as error:
        plan([alias('TABLE', 'urltable', [url], updatefreq_days='1')], [])
    assert url not in str(error.value)


def test_type_specific_fields_and_provider_name_syntax():
    for record in [alias('HOST', updatefreq_days='1'), alias('TABLE','urltable',['https://example.invalid']),
                   alias('bad-name'), alias('1bad'), alias('__private'), alias('_'), alias('A'*32)]:
        with pytest.raises(ValidationError):
            plan([record], [])
    plan([alias('_A'), alias('A'*31)], [])
    assert plan([alias('TABLE', 'urltable', ['https://example.invalid'], 'absent')], [])['batches'] == []


def test_dependency_batches_and_unlisted_preservation():
    desired=[alias('GROUP','networkgroup',['TABLE','HOST']),
             alias('TABLE','urltable',['https://example.invalid/net'],updatefreq_days='0.5'), alias('HOST')]
    result=plan(desired,[alias('UNLISTED')])
    assert [batch[0]['name'] for batch in result['batches']] == ['HOST','TABLE','GROUP']
    assert not any(batch[0]['name']=='UNLISTED' for batch in result['batches'])


@pytest.mark.parametrize('members,others', [
    (['GROUP'], []), (['HOST','HOST'],[alias('HOST')]),
    (['HOST'],[alias('HOST',state='absent')]), (['PORTS'],[alias('PORTS','port',['443'])]),
    (['SECOND'],[alias('SECOND','networkgroup',['GROUP'])]),
])
def test_local_group_failures(members,others):
    with pytest.raises(ValidationError):
        plan([alias('GROUP','networkgroup',members),*others], [])


def test_absent_content_does_not_define_dependencies():
    desired=[alias('GROUP','networkgroup',['MISSING','MISSING'],'absent'), alias('HOST',state='absent')]
    live=[alias('GROUP','networkgroup',['HOST']), alias('HOST')]
    assert [b[0]['name'] for b in plan(desired,live)['batches']] == ['GROUP','HOST']
    assert plan(desired,[])['batches'] == []


def test_effective_graph_uses_desired_replacement_and_reference_release():
    live=[alias('GROUP','networkgroup',['OLD']),alias('OLD'),alias('EXTERNAL','networkgroup',['GROUP'])]
    desired=[alias('OLD',state='absent'),alias('GROUP','networkgroup',['NEW']),alias('NEW')]
    result=plan(desired,live)
    assert [b[0]['name'] for b in result['batches']] == ['NEW','GROUP','OLD']
    # Stale GROUP -> OLD is replaced before traversing EXTERNAL -> GROUP.
    result=plan(desired+[alias('ROOT','networkgroup',['EXTERNAL'])],live)
    assert [b[0]['name'] for b in result['batches']] == ['NEW','GROUP','ROOT','OLD']
    assert [r['name'] for r in live] == ['GROUP','OLD','EXTERNAL']


@pytest.mark.parametrize('external', [None, alias('EXTERNAL','port',['443']),
                                     alias('EXTERNAL','networkgroup',['GROUP']),
                                     alias('EXTERNAL','networkgroup',['!HOST']),
                                     alias('EXTERNAL','network',['unsupported.example.invalid'])])
def test_external_missing_type_cycle_and_unsupported_syntax(external):
    with pytest.raises(ValidationError):
        plan([alias('GROUP','networkgroup',['EXTERNAL'])], [] if external is None else [external])


def test_external_dependency_on_planned_removal_is_rejected():
    with pytest.raises(ValidationError):
        plan([alias('GROUP','networkgroup',['EXTERNAL']),alias('OLD',state='absent')],
             [alias('EXTERNAL','networkgroup',['OLD']),alias('OLD')])


def test_type_change_and_duplicate_live_identity_rejected():
    with pytest.raises(ValidationError,match='type changes'):
        plan([alias('HOST','network',['192.0.2.0/24'])],[alias('HOST')])
    with pytest.raises(ValidationError,match='ambiguous'):
        plan([alias('HOST')],[alias('HOST'),alias('HOST')])


def test_noop_frequency_and_content_order():
    desired=[alias('TABLE','urltable',['https://example.invalid/a','https://example.invalid/b'],updatefreq_days='1.0')]
    live=deepcopy(desired)
    live[0]['updatefreq_days']=1
    live[0]['content'].reverse()
    assert not plan(desired,live)['would_change']


def test_external_host_dns_leaf_and_live_host_reference_removal():
    result=plan([alias('GROUP','networkgroup',['EXTERNAL'])],[alias('EXTERNAL','host',['host.example.invalid'])])
    assert [b[0]['name'] for b in result['batches']]==['GROUP']
    desired=[alias('A',state='absent'),alias('Z',state='absent')]
    live=[alias('A','host',['Z']),alias('Z')]
    assert [b[0]['name'] for b in plan(desired,live)['batches']]==['A','Z']


def test_generic_gateway_and_rule_composition():
    from pathlib import Path
    import yaml
    root=Path(__file__).resolve().parents[1]/'fixtures/opnsense-capabilities'
    for resource,filename,key in [('aliases','aliases.yml','opnsense_aliases'),
                                  ('gateways','gateways.yml','opnsense_gateways'),
                                  ('filter-rules','filter-rules.yml','opnsense_filter_rules')]:
        document=yaml.safe_load((root/filename).read_text())
        validate_document(resource,document)
        if resource=='aliases':
            assert plan(document[key],[])['batches'][-1][0]['name']=='DESTINATION_GROUP'
