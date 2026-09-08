# Reusable Automation

Container build, external input and release interface:
[OCI runtime](../docs/operations/06-oci-runtime.md).

This layer contains mechanisms reusable across environments. It does not own
Astra topology, VM declarations, runtime templates, generated inputs, or local
state.

- `src/iaas_automation/` — Python validation, rendering, and read-only check
  modules. Their supported CLI inputs and outputs are explicit.
- `ansible/` — reusable playbooks, roles, module utilities, and Ansible
  configuration.
- `opentofu/modules/` — reusable OpenTofu modules.
- `packer/` and `pve-node/` — reusable template-build and node-side wrappers.

本文件只说明可复用实现层，不定义 Astra 的操作流程。操作步骤、参数解释、准入和
验收仅见 [基础设施操作手册](../docs/operations/README.md)。开发者直接调用
Python 模块时需要 `PYTHONPATH=automation/src`；不存在 `scripts.*` 兼容包。
