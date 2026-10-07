"""Scope the OPNsense proxy opt-in to management API clients and providers."""

from collections.abc import Iterator, Mapping, MutableMapping
from contextlib import contextmanager

import requests

from iaas.runtime_execution.network_proxy import NEUTRALIZED_NAMES, PROXY_NAMES


def api_environment(environment: Mapping[str, str], use_proxy: bool = False) -> dict[str, str]:
    if type(use_proxy) is not bool:
        raise ValueError('api_use_proxy must be a boolean')
    return {name: environment.get(name, '') if use_proxy and name in PROXY_NAMES else ''
            for name in PROXY_NAMES | NEUTRALIZED_NAMES}


@contextmanager
def provider_environment(environment: MutableMapping[str, str], use_proxy: bool = False) -> Iterator[None]:
    names = PROXY_NAMES | NEUTRALIZED_NAMES
    selected = api_environment(environment, use_proxy)
    previous = {name: environment.get(name) for name in names}
    try:
        environment.update(selected)
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                environment.pop(name, None)
            else:
                environment[name] = value


class ApiSession(requests.Session):
    """Default direct API access, preserving the existing TLS and CA rules."""

    def __init__(self, use_proxy: bool = False):
        if type(use_proxy) is not bool:
            raise ValueError('api_use_proxy must be a boolean')
        super().__init__()
        self.use_proxy = use_proxy

    def merge_environment_settings(self, url, proxies, stream, verify, cert):
        settings = super().merge_environment_settings(url, proxies, stream, verify, cert)
        if not self.use_proxy:
            settings['proxies'] = {}
        else:
            settings['proxies'] = {name: value for name, value in settings['proxies'].items()
                                   if name in {'http', 'https'}}
        return settings
