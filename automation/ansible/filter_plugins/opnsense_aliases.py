"""Controller-only alias planning using the shared offline contract."""

from pathlib import Path
import sys

_AUTOMATION_SRC = Path(__file__).resolve().parents[2] / 'src'
if str(_AUTOMATION_SRC) not in sys.path:
    sys.path.insert(0, str(_AUTOMATION_SRC))

from iaas_automation.opnsense_validation import validate_document
from iaas_automation.opnsense_validation.aliases import plan_aliases


def opnsense_alias_plan(records, live):
    validate_document('aliases', {'opnsense_aliases': records})
    return plan_aliases(records, live)


class FilterModule:
    def filters(self):
        return {'opnsense_alias_plan': opnsense_alias_plan}
