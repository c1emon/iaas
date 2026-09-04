# Reusable Automation

This layer contains mechanisms reusable across environments. It does not own
Astra topology, VM declarations, runtime templates, generated inputs, or local
state.

- `src/iaas_automation/` — Python validation, rendering, and read-only check
  modules. Their supported CLI inputs and outputs are explicit.
- `ansible/` — reusable playbooks, roles, module utilities, and Ansible
  configuration.
- `opentofu/modules/` — reusable OpenTofu modules.
- `packer/` and `pve-node/` — reusable template-build and node-side wrappers.

Use the repository-root Makefile for Astra operations. Direct Python commands
need `PYTHONPATH=automation/src`; no `scripts.*` compatibility package exists.
