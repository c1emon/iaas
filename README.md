# Astra Infrastructure

This repository is being re-initialized as the source of truth for Astra infrastructure automation.

Current scope:

- No real secrets committed to Git.
- PVE automation foundation with YAML source-of-truth inventory, generated OpenTofu input, generated Ansible inventory, and generated VM documentation.
- Debian 13 PVE template build helpers under `infra/packer/`, executed through audited PVE-node wrappers.
- OpenTofu VM lifecycle configuration under `infra/tofu/`, using local state for the initial single-operator workflow.
- Ansible bootstrap and verification content is added incrementally around the same inventory model.

Key areas:

- `docs/` — architecture, runbooks, decision records.
- `inventory/` — operator-authored PVE cluster and VM source-of-truth YAML.
- `infra/packer/` — PVE template build helpers and runbooks.
- `infra/tofu/` — OpenTofu-managed PVE VM lifecycle.
- `ansible/` — host configuration, service deployment, and low-risk network automation.
- `scripts/` — validation, generation, and runtime helper scripts.

## Python toolchain

Python-based tooling is managed with `uv`.

```bash
uv sync
uv run ansible --version
uv run ansible-lint --version
uv run yamllint --version
```

Commit `pyproject.toml` and `uv.lock`; do not commit `.venv/`.
