# OPNsense Management Plan

OPNsense is the core router/firewall. Automation must start conservatively.

## Management boundary

Initially managed by Ansible:

- API connectivity checks
- read-only configuration queries
- configuration snapshots
- local exports for first-stage review of aliases and Unbound configuration
- later: aliases, Unbound overrides/forwarding, DHCP reservations, syslog, monitoring

Initially not managed by automation:

- ISC DHCP, DHCPv6, router advertisements, and prefix delegation
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
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/readonly.yml
```

## Read-only configuration export

Export selected OPNsense configuration and observed facts from `ansible/`:

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/export.yml
```

The playbook writes raw review artifacts under `exports/opnsense/` at the repository root. The `exports/` path is
ignored by Git by default because raw exports may contain network topology, lease data, hostnames, MAC addresses, and
IPv6 prefix details.

First-stage declarative-management candidates in the export are:

- firewall aliases
- Unbound host overrides
- Unbound forwarding entries

Exported firewall aliases are observed live state. They may help review or prepare future desired state, but the alias
management workflow does not read `exports/opnsense/firewall-aliases.json` directly. Edit the hand-written
`ansible/vars/opnsense/aliases.yml` source instead.

Observed-only facts in the export are:

- DHCPv4 leases
- DHCPv6 leases
- DHCPv6 prefix leases

DHCP outputs are not desired-state configuration to apply. This export does not manage ISC DHCP, DHCPv6, prefix
delegation, interfaces, firewall rules, or NAT.

## Bootstrap workflow

From `ansible/`:

```bash
uv sync
uv run ansible-galaxy collection install -r requirements.yml
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/readonly.yml
```

Before any future write playbook:

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/snapshot.yml
```

Additively apply reviewed firewall aliases from `ansible/vars/opnsense/aliases.yml`:

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/manage-aliases.yml
```

Validate the alias management files before applying:

```bash
uv run ansible-playbook --syntax-check playbooks/opnsense/manage-aliases.yml
uv run yamllint vars/opnsense/aliases.yml playbooks/opnsense/manage-aliases.yml
uv run ansible-lint playbooks/opnsense/manage-aliases.yml
```

## Safety rules

- Use `--check --diff` whenever supported.
- `manage-aliases.yml` creates or updates only aliases listed in `aliases.yml`; unlisted aliases are not deleted,
  disabled, or purged.
- Alias type changes are not automatically migrated by delete/recreate; handle type migrations explicitly after review.
- Prefer `alias_multi` / `rule_multi` for coherent bulk changes later.
- Use OPNsense savepoints before firewall/NAT changes.
- Do not mix manual and Ansible ownership for the same rule set without a migration plan.
- Pin OPNsense and `oxlorg.opnsense` versions once actual management starts.
