# Ansible

This directory contains Ansible automation for Astra host and service management.

Current scope:

- OPNsense API bootstrap scaffolding.
- Read-only OPNsense API smoke test.
- OPNsense configuration snapshot playbook.
- SKS8300/XikeOS switch facts and configuration planning over SSH `network_cli` using `c1emon.xikeos`.

Install dependencies:

```bash
uv sync
uv run ansible-galaxy collection install -r requirements.yml
```

The switch workflow installs the native Galaxy collection `c1emon.xikeos` through
`requirements.yml`; use the repository requirements command above instead of an
out-of-band collection install so all Ansible dependencies stay reproducible.
Collection installation does not install Python parser libraries, so ensure the
control environment has collection runtime parser dependencies such as `ttp` and
`textfsm` available when collection-backed facts or resource modules require
them.

Run the read-only OPNsense smoke test with credentials injected at runtime:

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/readonly.yml
```

Run the read-only switch facts collection with credentials injected at runtime:

```bash
op run --env-file ../.env.switch.tpl -- uv run ansible-playbook playbooks/switches/readonly-facts.yml
```

Do not commit plaintext vault passwords, private keys, API keys, or environment-specific secrets.
