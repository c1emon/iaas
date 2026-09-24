"""Identity shared by the independently validated NAT resources."""


def nat_identity(record: dict, path: str, resource: str) -> tuple[str]:
    from . import IDENTITY_PART, _state, _string

    scope = _string(record.get('scope'), f'{path}.scope', pattern=IDENTITY_PART)
    slug = _string(record.get('slug'), f'{path}.slug', pattern=IDENTITY_PART)
    _state(record.get('state'), f'{path}.state')
    return (f'iaas:opnsense:{resource}:{scope}:{slug}',)
