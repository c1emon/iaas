"""Keep Ansible's rich exception output inside the no_log boundary."""

from ansible.plugins.callback.default import CallbackModule as DefaultCallback

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
        if result.task.no_log or result.result.get('_ansible_no_log', False):
            return
        super()._handle_warnings_and_exception(result)
