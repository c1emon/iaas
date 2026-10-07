"""Apply the IaaS management API proxy opt-in at the provider boundary."""

import os
import sys
from pathlib import Path

_SOURCE = str(Path(__file__).resolve().parents[3] / 'src')
if _SOURCE not in sys.path:
    sys.path.insert(0, _SOURCE)

from iaas.opnsense_workflow.proxy import api_environment  # noqa: E402


def opnsense_api_environment(use_proxy=False):
    return api_environment(dict(os.environ), use_proxy)


class FilterModule:
    def filters(self):
        return {'opnsense_api_environment': opnsense_api_environment}
