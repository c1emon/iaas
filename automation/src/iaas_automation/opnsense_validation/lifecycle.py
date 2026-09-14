"""Shared batch admission, with resource-specific provider arguments."""
from .nat import nat_identity


def resource_preflight(records: list, existing: list, resource: str) -> bool:
    from . import _error, _list, _mapping

    rows = [_mapping(row, 'existing entry') for row in _list(existing, 'existing entries')]
    for record in records:
        field = 'name' if resource == 'interface-groups' else 'description'
        identity = (record['name'] if field == 'name'
                    else nat_identity(record, resource, resource)[0])
        matches = [row for row in rows if row.get(field) == identity]
        if len(matches) > 1:
            _error(identity, 'multiple existing objects match the managed identity')
        if resource == 'interface-groups' and record['state'] == 'present':
            existing_groups = {row.get('name') for row in rows}
            if any(member in existing_groups for member in record['members']):
                _error(identity, 'nested interface groups are not supported')
        if resource == 'dnat' and record['state'] == 'present' and matches:
            if matches[0].get('no_port_forward') is not False:
                _error(identity, 'existing no_port_forward mode is enabled or cannot be determined')
    return True


def resource_arguments(record: dict, resource: str) -> dict:
    from . import TOP_LEVEL, validate_document

    validate_document(resource, {TOP_LEVEL[resource]: [record]})
    if resource == 'interface-groups':
        result = {'name': record['name'], 'state': record['state'], 'reload': False}
        if record['state'] == 'present':
            result.update(members=record['members'], gui_group=record['gui_group'],
                          sequence=record['sequence'], description=record.get('description', ''))
        return result
    result = {'description': nat_identity(record, resource, resource)[0],
              'state': record['state'], 'match_fields': ['description'], 'reload': False}
    if record['state'] == 'absent':
        return result
    if resource == 'dnat':
        for field in ('enabled', 'sequence', 'interface', 'ip_protocol', 'protocol',
                      'source_net', 'destination_net', 'target', 'nat_reflection', 'associated_rule'):
            result[field] = record[field]
        for field in ('source_port', 'destination_port', 'local_port', 'pool_opts', 'tag', 'tagged'):
            result[field] = record.get(field)
        result['no_port_forward'] = False
    elif resource == 'one-to-one-nat':
        for field in ('enabled', 'sequence', 'interface', 'type', 'external',
                      'source_net', 'destination_net', 'nat_reflection'):
            result[field] = record[field]
    else:
        raise ValueError('unsupported NAT resource')
    for field in ('source_invert', 'destination_invert', 'log'):
        result[field] = record.get(field, False)
    return result
