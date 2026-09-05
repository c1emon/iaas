"""Resolve an action-scoped VM-baseline secret in a ``no_log`` task.

The lookup accepts only an explicit protected runtime-secret file and an
external reference.  It delegates validation and consumption to the shared
protected channel, so a secret value is never put in ordinary lookup errors,
facts, or metadata.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

# Ansible invokes plugins in its own interpreter, outside the package command
# wrappers.  Resolve the repository's automation source explicitly instead of
# relying on a caller to export PYTHONPATH.
_AUTOMATION_SRC = Path(__file__).resolve().parents[3] / "src"
if str(_AUTOMATION_SRC) not in sys.path:
    sys.path.insert(0, str(_AUTOMATION_SRC))

from iaas_automation.k3s_automation.secrets import load_protected_environment_json

DOCUMENTATION = r"""
name: vm_baseline_protected_secret
short_description: Resolve one protected VM-baseline runtime secret for a no_log task
description:
  - Reads a root/user-private JSON mapping through the shared protected secret channel.
  - The value is intended solely for a no_log module or template argument.
options:
  _terms:
    description: One external C(op://) secret reference.
    required: true
  secret_file:
    description: Explicit path to the protected runtime-secret JSON file.
    required: true
    type: path
"""


class LookupModule(LookupBase):
    """Bridge the strict runtime channel into a redacted Ansible task."""

    def run(
        self, terms: list[Any], variables: dict[str, Any] | None = None, **kwargs: Any
    ) -> list[str]:
        secret_file = kwargs.get("secret_file")
        if not isinstance(secret_file, str) or not secret_file:
            raise AnsibleError(
                "vm_baseline_protected_secret requires an explicit secret_file path"
            )
        if not terms or not all(
            isinstance(reference, str) and reference for reference in terms
        ):
            raise AnsibleError(
                "vm_baseline_protected_secret requires non-empty external references"
            )

        try:
            channel = load_protected_environment_json(Path(secret_file))
            values: list[str] = []
            for reference in terms:
                channel.consume(reference, values.append)
            return values
        except Exception as exc:
            # Keep values and reference details out of ordinary Ansible output.
            raise AnsibleError(
                "unable to resolve required protected VM-baseline runtime secret"
            ) from exc
