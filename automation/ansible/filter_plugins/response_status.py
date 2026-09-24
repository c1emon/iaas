"""Use the shared external status conversion at Ansible provider boundaries."""
from pathlib import Path
import sys

_SOURCE = str(Path(__file__).resolve().parents[3] / 'src')
if _SOURCE not in sys.path:
    sys.path.insert(0, _SOURCE)

from iaas.common.conversion import normalize_response_status


class FilterModule:
    def filters(self):
        return {'iaas_response_status': normalize_response_status}
