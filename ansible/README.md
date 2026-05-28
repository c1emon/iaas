# Ansible

This directory contains Ansible automation for Astra host and service management.

Current scope:

- OPNsense API bootstrap scaffolding.
- Read-only OPNsense API smoke test.
- OPNsense configuration snapshot playbook.

Install dependencies:

```bash
uv sync
uv run ansible-galaxy collection install -r requirements.yml
```

Run the read-only OPNsense smoke test with credentials injected at runtime:

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense-readonly.yml
```

Do not commit plaintext vault passwords, private keys, API keys, or environment-specific secrets.
