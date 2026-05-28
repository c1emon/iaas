# Astra Infrastructure

This repository is being re-initialized as the source of truth for Astra infrastructure automation.

Current scope:

- No live infrastructure changes.
- No real secrets committed to Git.
- Terraform, Ansible, and operational documents will be added incrementally after boundaries and safety workflows are defined.

Planned areas:

- `docs/` — architecture, runbooks, decision records.
- `terraform/` — infrastructure resources such as Proxmox VMs and DNS records.
- `ansible/` — host configuration, service deployment, and low-risk network automation.
- `scripts/` — local helper scripts only when needed.

## Python toolchain

Python-based tooling is managed with `uv`.

```bash
uv sync
uv run ansible --version
uv run ansible-lint --version
uv run yamllint --version
```

Commit `pyproject.toml` and `uv.lock`; do not commit `.venv/`.
