"""Resolve an action-scoped K3s secret directly into a ``no_log`` task.

The lookup deliberately accepts the protected JSON *path* and an external
reference, never a secret value.  It shares the Python channel's permission
and reference checks, and is only used in template or module arguments marked
``no_log``.  Lookup return values must not be assigned to Ansible facts.
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
name: k3s_protected_secret
short_description: Resolve one protected K3s runtime secret for a no_log task
description:
  - Reads a root/user-private JSON mapping through the shared K3s secret channel.
  - The value is intended solely for a no_log module/template argument.
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

    # Ansible's unannotated abstract stub is inferred as None; lookup results are lists.
    def run(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, terms: list[Any], variables: dict[str, Any] | None = None, **kwargs: Any
    ) -> list[str]:
        secret_file = kwargs.get("secret_file")
        if not isinstance(secret_file, str) or not secret_file:
            raise AnsibleError("k3s_protected_secret requires an explicit secret_file path")
        if not terms or not all(isinstance(reference, str) and reference for reference in terms):
            raise AnsibleError("k3s_protected_secret requires non-empty external references")

        try:
            channel = load_protected_environment_json(Path(secret_file))
            values: list[str] = []
            for reference in terms:
                channel.consume(reference, values.append)
            return values
        except Exception as exc:
            # The shared channel intentionally keeps both values and reference
            # detail out of error messages.  Preserve that property here.
            raise AnsibleError("unable to resolve required protected K3s runtime secret") from exc
