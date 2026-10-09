"""Rule port admission and zero-write failure over synthetic providers."""
from copy import deepcopy
import json

import pytest

from iaas.common.errors import ValidationError
from iaas.opnsense_validation import validate_document, validate_documents
from iaas.opnsense_workflow.writer import Writer, WriterError, provider_arguments
from iaas.opnsense_workflow.save_diagnostics import validation_details, REDACTED_REASON
from test_opnsense_workflow import Appliance, alias, candidate, documents, execute, rule


INVALID = [([8848, 9848], 'explicit port alias'), ('8848,9848', 'comma-separated'),
           (0, '1..65535'), (65536, '1..65535'), ('70000', '1..65535'),
           ('9848-8848', 'ascending'), ('0-80', 'ascending'), ('1-65536', 'ascending'),
           ('80-', 'syntax'), ('-80', 'syntax'), ('1-2-3', 'syntax'),
           ('80:90', 'syntax'), (True, 'must be a port'), ([], 'requires one'),
           (['443', '444'], 'explicit port alias')]


@pytest.mark.parametrize('field', ['source_port', 'destination_port'])
@pytest.mark.parametrize('value,reason', INVALID)
def test_invalid_rule_ports_rejected_by_check_plan_and_writer(field, value, reason):
    row = rule('any', **{field: value})
    docs = documents(filter_rules=[row])
    device = Appliance()
    with pytest.raises(ValidationError, match=field + '.*' + reason):
        validate_document('filter-rules', docs['filter-rules'])
    with pytest.raises(ValidationError, match=field + '.*' + reason):
        candidate(device, docs)
    with pytest.raises(WriterError, match=field + '.*' + reason):
        # An invalid later record must block the whole batch before the first save.
        Writer(device).save('filter-rules', [rule('any', slug='valid'), row])
    with pytest.raises(WriterError, match=field + '.*' + reason):
        provider_arguments('filter-rules', row)
    assert device.calls == []


@pytest.mark.parametrize('value,expected', [(443, '443'), ('443', '443'),
    ([443], '443'), ('8848-9848', '8848-9848'), (['8848-9848'], '8848-9848'),
    ('1-65535', '1-65535'), ('NACOS_PORTS', 'NACOS_PORTS')])
def test_valid_rule_ports_keep_exact_meaning(value, expected):
    port_alias = alias('NACOS_PORTS', ['8848', '9848'], type='port')
    row = rule('any', destination_port=value)
    docs = documents(aliases=[port_alias], filter_rules=[row])
    validate_documents(docs)
    planned = candidate(Appliance(), docs)
    assert planned['stages']
    assert provider_arguments('filter-rules', row)['destination_port'] == expected
    assert row['destination_port'] == value


def test_port_alias_type_checked_in_selected_documents_and_rule_context():
    row = rule('any', destination_port='NACOS_PORTS')
    wrong = alias('NACOS_PORTS')
    with pytest.raises(ValidationError, match='destination_port.*port type alias'):
        validate_documents(documents(aliases=[wrong], filter_rules=[row]))
    with pytest.raises(WriterError, match='destination_port.*port type alias'):
        provider_arguments('filter-rules', row, context={'interface_networks': {}, 'aliases': [wrong]})
    with pytest.raises(ValidationError, match='incompatible.*type'):
        candidate(Appliance(aliases=[wrong]), documents(filter_rules=[row]))


def test_tampered_apply_document_rejected_before_any_write(tmp_path):
    device = Appliance()
    planned = candidate(device, documents(filter_rules=[rule('any', destination_port=443)]))
    planned['documents']['filter-rules']['opnsense_filter_rules'][0]['destination_port'] = [8848, 9848]
    result = execute(tmp_path, device, planned)
    assert result['status'] == 'failed'
    assert device.calls == []


def test_validation_evidence_retains_field_reason_and_never_private_response():
    reason = 'Please specify a valid portnumber, name, alias or range.'
    message = f"API call failed | Error: {{'filter.rules.rule.private-id.destination_port': {reason!r}, 'api_secret': 'private-secret', 'rule.source_port': 'bad value private-config'}} | Response: private-cookie"
    failure = {'msg': message, 'invocation': {'api_secret': 'private-secret'}, 'results': [
        {'failed': False, 'validations': {'rule.gateway': reason}},
        {'failed': True, 'validations': {'rule.destination_port': reason}},
    ]}
    details = validation_details(failure)
    assert details == [{'field': 'destination_port', 'reason': reason},
                       {'field': 'unknown_field', 'reason': REDACTED_REASON},
                       {'field': 'source_port', 'reason': REDACTED_REASON}]
    assert 'private' not in json.dumps(details)
    assert validation_details({'msg': 'API call failed | Error: malformed | Response: private'}) == []
    assert validation_details({'msg': 'API call failed | Error: ' + 'x' * 65536}) == []


def test_writer_and_workflow_persist_safe_failure_without_activation(tmp_path):
    reason = 'Please specify a valid portnumber, name, alias or range.'
    failure = {'validation_reported': True, 'http_status_codes': ['400'],
               'validation_details': [{'field': 'destination_port', 'reason': reason}],
               'invocation': {'api_secret': 'private-secret'}}

    class Provider:
        def save(self, resource, records, *, reload):
            return {'status': 'failed', 'result': {'failure': deepcopy(failure)}}

    class Device(Appliance):
        def save(self, resource, records):
            self.calls.append(('save', resource))
            return Writer(Provider()).save(resource, records)

    device = Device()
    planned = candidate(device, documents(filter_rules=[rule('any', destination_port=443)]))
    result = execute(tmp_path, device, planned)
    assert result['status'] == 'failed'
    assert device.calls == [('save', 'filter-rules')]
    for name in ('result.json', 'recovery.json'):
        text = (tmp_path / name).read_text()
        assert 'private-secret' not in text
        retained = json.loads(text)['stages'][0]['save_diagnostics']
        assert retained['validation_details'] == failure['validation_details']
