"""Keep Ansible's rich exception output inside the no_log boundary."""

import json
from pathlib import Path
import sys

from ansible.plugins.callback.default import CallbackModule as DefaultCallback

_AUTOMATION_SRC = Path(__file__).resolve().parents[4] / 'src'
if str(_AUTOMATION_SRC) not in sys.path:
    sys.path.insert(0, str(_AUTOMATION_SRC))

from iaas.common.public_diagnostics import MARKER, assertion_diagnostics, safe_diagnostics, task_diagnostics  # noqa: E402

DOCUMENTATION = """
name: iaas_safe_default
type: stdout
short_description: Default screen output respecting protected diagnostics
description:
  - Uses the default callback while suppressing protected task diagnostics.
extends_documentation_fragment:
  - default_callback
  - result_format_callback
"""


class CallbackModule(DefaultCallback):
    CALLBACK_NAME = 'iaas_safe_default'

    def _handle_warnings_and_exception(self, result):
        # CallbackTaskResult already censors protected payloads. Use its public
        # outcome/warning metadata; never reach into the private task result.
        values = {**result.result, 'failed': result.is_failed(), 'unreachable': result.is_unreachable(),
                  'warnings': [None] * min(len(result.warnings), 1000)}
        protected = bool(result.task.no_log or result.result.get('_ansible_no_log', False))
        entries = task_diagnostics(values, result.task.action, protected=protected)
        if protected and result.is_failed() and result.task.action.rsplit('.', 1)[-1] == 'assert':
            entries.extend(assertion_diagnostics(result.task.args.get('fail_msg')))
        message = result.result.get('msg')
        if isinstance(message, dict):
            entries.extend(safe_diagnostics(message.get('iaas_public_diagnostics')))
        for entry in entries:
            self._display.display(MARKER + json.dumps(entry))
        if result.task.no_log or result.result.get('_ansible_no_log', False):
            return
        super()._handle_warnings_and_exception(result)
