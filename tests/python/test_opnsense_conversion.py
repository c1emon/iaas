"""Pure wire contracts and bounded properties; never consult an appliance."""
from copy import deepcopy

from hypothesis import given, settings, strategies as st
import pytest

from iaas_automation.common.conversion import ConversionError, convert_bool
from iaas_automation.opnsense_workflow.conversion import convert_provider_row, normalize_standard_record
from iaas_automation.opnsense_workflow.conversion.resources import unexpressed_fields
from iaas_automation.opnsense_workflow.conversion.types import selected
from test_opnsense_workflow_reader import ROWS, FakeCollection, reader

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('value', [False, 0, 0.0, '0', 'false', 'False', 'No', 'OFF', 'n', 'F'])
def test_false(value):
    assert convert_bool(value) is False


@pytest.mark.parametrize('value', [True, 1, 1.0, '1', 'true', 'YES', 'on', 'y', 'T'])
def test_true(value):
    assert convert_bool(value) is True


@pytest.mark.parametrize('value', ['fasle', '', None, ' false ', 2, -1, [], {}, [0]])
def test_invalid_boolean_is_not_a_default(value):
    with pytest.raises(ConversionError, match='^invalid_boolean$'):
        convert_bool(value)


@settings(max_examples=35)
@given(st.booleans(), st.sampled_from(['aliases', 'filter-rules', 'dnat', 'one-to-one-nat']))
def test_source_aware_inversion_and_immutability(enabled, resource):
    raw = {'disabled': int(not enabled)}
    canonical = {'enabled': enabled}
    both = raw | canonical
    before = deepcopy(both)
    assert convert_provider_row(resource, raw).fields == canonical
    assert convert_provider_row(resource, canonical).fields == canonical
    assert convert_provider_row(resource, both).fields == canonical
    assert both == before
    with pytest.raises(ConversionError, match='conflicting_native_alias'):
        convert_provider_row(resource, raw | {'enabled': not enabled})


@settings(max_examples=30)
@given(st.sampled_from(list(ROWS)), st.permutations(['198.51.100.1', '192.0.2.1']))
def test_normalization_is_idempotent_and_does_not_mutate(resource, content):
    record = deepcopy(ROWS[resource][0]) | {'state': 'present'}
    if resource == 'aliases':
        record['content'] = list(content)
    before = deepcopy(record)
    normalized = normalize_standard_record(resource, record)
    assert normalize_standard_record(resource, normalized) == normalized
    assert record == before
    assert normalize_standard_record(resource, {'state': 'absent'}) == {'state': 'absent'}


@settings(max_examples=30)
@given(st.text(min_size=8).map(lambda text: 'secret=' + text))
def test_sensitive_inputs_and_dynamic_keys_are_not_reported(secret):
    with pytest.raises(ConversionError) as caught:
        selected({secret: {'selected': secret}})
    assert secret not in str(caught.value)
    assert caught.value.__cause__ is None
    converted = convert_provider_row('aliases', {secret: 0})
    assert unexpressed_fields('aliases', converted.extras, converted.fields) == ['unknown_native_field']


@pytest.mark.parametrize('field,value', [('enabled', 'fasle'), ('sequence', True), ('action', 123)])
def test_invalid_configuration_retains_identity_and_references(field, value):
    rows = deepcopy(ROWS)
    rows['filter-rules'][0][field] = value
    result = reader(FakeCollection(rows)).read(['filter-rules'])['filter-rules']
    assert result['status'] == 'complete'
    item = result['objects'][0]
    assert item['configuration'] is None
    assert item['recovery'] == 'manual_required'
    assert 'aliases:NETS' in item['references']


def test_nested_aliases_consume_only_known_leaves_and_detect_conflicts():
    raw = {'source': {'network': 'NETS', 'secret-key': True}, 'source_net': 'NETS'}
    converted = convert_provider_row('dnat', raw)
    assert converted.fields['source_net'] == 'NETS'
    assert converted.extras == {'source': {'secret-key': True}}
    assert unexpressed_fields('dnat', converted.extras, converted.fields) == ['source']
    equivalent = convert_provider_row(
        'filter-rules', {'source': {'network': 'NETS'}, 'source_net': ['NETS']}
    )
    assert equivalent.fields['source_net'] == ['NETS']
    with pytest.raises(ConversionError, match='conflicting_native_alias'):
        convert_provider_row('dnat', raw | {'source_net': 'OTHER'})


def test_filter_empty_native_state_timeout_is_a_neutral_unexpressed_value():
    converted = convert_provider_row('filter-rules', {'statetimeout': ''})
    assert converted.fields == {'state_timeout': ''}
    assert converted.errors == ()
    assert unexpressed_fields('filter-rules', converted.extras, converted.fields) == []
    assert convert_provider_row('filter-rules', {'statetimeout': None}).errors == ('state_timeout',)
    assert convert_provider_row('filter-rules', {'statetimeout': 'invalid'}).errors == ('state_timeout',)
    assert convert_provider_row('filter-rules', {'sequence': ''}).errors == ('sequence',)
    assert convert_provider_row('dnat', {'statetimeout': ''}).errors == ('state_timeout',)
    nondefault = convert_provider_row('filter-rules', {'statetimeout': '30'})
    assert unexpressed_fields('filter-rules', nondefault.extras, nondefault.fields) == ['state_timeout']

    rows = deepcopy(ROWS)
    rows['filter-rules'][0]['statetimeout'] = ''
    observed = reader(FakeCollection(rows)).read(['filter-rules'])['filter-rules']
    assert observed['status'] == 'complete'
    assert observed['objects'][0]['recovery'] == 'expressible'


def test_dnat_compatibility_nested_leaves_are_consumed_but_unknowns_fail_closed():
    row = deepcopy(ROWS['dnat'][0])
    row.pop('source_net')
    row.pop('destination_net')
    row.update(
        source={'network': 'any', 'address': '', 'port': '', 'not': '0'},
        destination={
            'network': 'PUBLIC_ALIAS', 'address': '',
            'port': 'WEB_PORT', 'not': '0', '%network': 'NATIVE_DESTINATION_NETWORK',
        },
        nordr='0',
    )
    converted = convert_provider_row('dnat', row)
    assert converted.fields['source_net'] == 'any'
    assert converted.fields['destination_net'] == 'PUBLIC_ALIAS'
    assert converted.fields['source_port'] == ''
    assert converted.fields['destination_port'] == 'WEB_PORT'
    assert 'source' not in converted.extras
    assert 'destination' not in converted.extras
    assert unexpressed_fields('dnat', converted.extras, converted.fields) == []

    unknown = deepcopy(row)
    unknown['source']['unexpected'] = 'UNSUPPORTED'
    converted_unknown = convert_provider_row('dnat', unknown)
    assert unexpressed_fields('dnat', converted_unknown.extras, converted_unknown.fields) == ['source']

    for value in (None, [], {}, 'UNSUPPORTED_ADDRESS'):
        unknown_address = deepcopy(row)
        unknown_address['source']['address'] = value
        converted_address = convert_provider_row('dnat', unknown_address)
        assert unexpressed_fields('dnat', converted_address.extras, converted_address.fields) == ['source']

    from iaas_automation.opnsense_workflow.reader import _configuration
    configuration, reason = _configuration('dnat', row)
    assert reason is None
    assert configuration['destination_net'] == 'PUBLIC_ALIAS'
    assert _configuration('dnat', row | {'nordr': '1'})[1] == 'unsupported_no_port_forward_mode'


@pytest.mark.parametrize('value', [0, '0', False, 'No'])
def test_dnat_no_port_forward_uses_common_boolean_alias_contract(value):
    converted = convert_provider_row('dnat', {'nordr': value, 'no_port_forward': False})
    assert converted.fields == {'no_port_forward': False}
    assert unexpressed_fields('dnat', converted.extras, converted.fields) == []
    with pytest.raises(ConversionError, match='conflicting_native_alias'):
        convert_provider_row('dnat', {'nordr': '1', 'no_port_forward': False})
    assert convert_provider_row('dnat', {'nordr': 'fasle'}).errors == ('no_port_forward',)


def test_selector_identifiers_and_alias_member_map():
    assert selected({'001': {'selected': 'yes', 'value': 'Display'}}) == '001'
    assert selected([{'key': '001', 'value': 'Display', 'selected': 1}]) == '001'
    assert selected([{'value': '001', 'selected': 'true'}]) == '001'
    assert convert_provider_row('aliases', {'name': '001', 'content': {'NETS': 'label'}}).fields == {'name': '001', 'content': ['NETS']}
    for bad in ([{'key': 'x', 'selected': 1}] * 2,
                {'x': {'selected': 1}, 'y': {'selected': 1}},
                {'x': {'selected': 'fasle'}}):
        with pytest.raises(ConversionError, match='malformed_native_selector'):
            selected(bad)


def test_invalid_reference_fails_closed():
    with pytest.raises(ConversionError, match='invalid_identity_or_reference'):
        convert_provider_row('filter-rules', {'destination_net': {'secret-key': 'NETS'}})


def test_active_consumer_rejects_partial_provider_conversion():
    from iaas_automation.opnsense_workflow.reader import _HttpFailure, _flatten_provider_row

    row = {
        'uuid': '11111111-1111-4111-8111-111111111111',
        'description': 'iaas:opnsense:filter:demo:ports',
        'enabled': 'fasle',
        'protocol': 'tcp',
        'source_port': 'any',
        'destination_port': 'WEB_PORTS',
        'action': 'pass',
    }
    with pytest.raises(_HttpFailure, match='invalid_configuration'):
        _flatten_provider_row(row, 'filter-rules')
    assert _flatten_provider_row(row, 'filter-rules', allow_partial=True)['destination_port'] == ['WEB_PORTS']


@pytest.mark.parametrize('flag', [0, '0', False, 'No', 'off', 'f', 0.0])
def test_gateway_observation_uses_shared_flag_semantics(flag):
    from iaas_automation.opnsense_workflow.gateway_checks import check_gateway_current
    from test_opnsense_gateway_checks import DESIRED, GATEWAY_ROWS
    rows = deepcopy(GATEWAY_ROWS)
    rows['rows'][0].update(monitor_disable=flag, monitor_noroute=flag)
    result = check_gateway_current(DESIRED, [], rows, route_expectation={'purpose': 'monitor_host', 'destination': '192.0.2.1'})
    assert result['checks']['monitor_configuration']['status'] == 'verified'
    assert result['checks']['route']['status'] == 'failed'  # required but absent


@pytest.mark.parametrize('flag', [None, 'fasle', ' false '])
def test_invalid_monitor_flag_stays_unknown(flag):
    from iaas_automation.opnsense_workflow.gateway_checks import check_gateway_current
    from test_opnsense_gateway_checks import DESIRED, GATEWAY_ROWS
    rows = deepcopy(GATEWAY_ROWS)
    rows['rows'][0].update(monitor_disable=flag, monitor_noroute=flag)
    result = check_gateway_current(DESIRED, [], rows, route_expectation={'purpose': 'monitor_host', 'destination': '192.0.2.1'})
    assert result['checks']['monitor_configuration']['status'] == 'unknown'
    assert result['checks']['route']['status'] == 'unknown'


def test_vip_composed_address_cannot_override_or_hide_native_source():
    row = {'subnet': '192.0.2.1', 'subnet_bits': '32', 'address': '192.0.2.1/32'}
    assert convert_provider_row('vips', row).fields['address'] == '192.0.2.1/32'
    with pytest.raises(ConversionError, match='conflicting_native_alias'):
        convert_provider_row('vips', row | {'address': '192.0.2.2/32'})
    with pytest.raises(ConversionError, match='invalid_identity_or_reference'):
        convert_provider_row('vips', row | {'subnet_bits': True})
