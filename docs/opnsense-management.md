# OPNsense Management Plan

OPNsense is the core router/firewall. Automation must start conservatively.

## Management boundary

Initially managed by Ansible:

- API connectivity checks
- read-only configuration queries
- configuration snapshots
- later: aliases, Unbound overrides/forwarding, DHCP reservations, syslog, monitoring

Initially not managed by automation:

- WAN / PPPoE
- VLAN interfaces
- management access rules
- default firewall policy
- critical NAT / public ingress rules

## Secret handling

OPNsense API credentials are not stored in Git.

Use environment variables:

- `OPNSENSE_API_KEY`
- `OPNSENSE_API_SECRET`

Preferred local execution with 1Password:

```bash
cd ansible
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense-readonly.yml
```

## Bootstrap workflow

From `ansible/`:

```bash
uv sync
uv run ansible-galaxy collection install -r requirements.yml
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense-readonly.yml
```

Before any future write playbook:

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense-snapshot.yml
```

## Safety rules

- Use `--check --diff` whenever supported.
- Prefer `alias_multi` / `rule_multi` for coherent bulk changes later.
- Use OPNsense savepoints before firewall/NAT changes.
- Do not mix manual and Ansible ownership for the same rule set without a migration plan.
- Pin OPNsense and `oxlorg.opnsense` versions once actual management starts.
