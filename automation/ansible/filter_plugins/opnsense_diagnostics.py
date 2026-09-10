"""Validate diagnostic target selection while resolving the controller play."""
from pathlib import Path
import json
import sys
from ansible import context

_AUTOMATION_SRC=Path(__file__).resolve().parents[2]/'src'
if str(_AUTOMATION_SRC) not in sys.path:
    sys.path.insert(0,str(_AUTOMATION_SRC))

from iaas_automation.opnsense_diagnostics.schema import controller_target


def diagnostic_controller(target,groups,limit=None):
    if context.CLIARGS.get('syntax',False):
        return 'localhost'
    return controller_target(target,groups,limit)


def diagnostic_summary(value):
    try:
        result=json.loads(value)
        if not isinstance(result,dict) or result.get('schema_version')!=1: raise ValueError
        return result
    except (ValueError,TypeError):
        return {'schema_version':1,'status':'error','reason':'runtime_failed'}


class FilterModule:
    def filters(self):
        return {'opnsense_diagnostic_controller':diagnostic_controller,'opnsense_diagnostic_summary':diagnostic_summary}
