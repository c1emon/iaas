"""Protected Collection failure to safe field/reason evidence."""
from pathlib import Path
import sys

_AUTOMATION_SRC = Path(__file__).resolve().parents[3] / 'src'
if str(_AUTOMATION_SRC) not in sys.path:
    sys.path.insert(0, str(_AUTOMATION_SRC))

from iaas.opnsense_workflow.save_diagnostics import public_failure_diagnostics, validation_details  # noqa: E402


class FilterModule:
    def filters(self):
        return {'opnsense_validation_details': validation_details,
                'opnsense_public_failure_diagnostics': public_failure_diagnostics}
