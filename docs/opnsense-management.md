# OPNsense Management Plan

OPNsense is the core router/firewall. Automation must start conservatively.

## Management boundary

Initially managed by Ansible:

- API connectivity checks
- read-only configuration queries
- configuration snapshots
- local exports for first-stage review of aliases and Unbound configuration
- hand-written firewall aliases, IP Alias VIPs, and PBR gateway desired state
- later: aliases, Unbound overrides/forwarding, DHCP reservations, syslog, monitoring

Initially not managed by automation:

- ISC DHCP, DHCPv6, router advertisements, and prefix delegation
- WAN / PPPoE
- VLAN interfaces
- CARP, Proxy ARP, and Other Virtual IP modes
- static routes and gateway groups
- management access rules
- firewall rules
- DNAT and NAT
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

IP Alias VIP desired state is also hand-written in `ansible/vars/opnsense/vips.yml`. It is not generated from export
artifacts, and the VIP workflow does not read raw exports as apply input.

PBR gateway desired state is hand-written in `ansible/vars/opnsense/gateways.yml`. It is not generated from export
artifacts, and the gateway workflow does not read raw exports as apply input.

DNAT desired state has a placeholder file at `ansible/vars/opnsense/dnat.yml`, but DNAT management is intentionally not
implemented yet. The placeholder playbook fails before any API write because the current `oxlorg.opnsense` collection
does not provide a stable dedicated Destination NAT / port-forward module in this repository.

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

Additively apply reviewed IP Alias VIPs from `ansible/vars/opnsense/vips.yml`:

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/manage-vips.yml
```

Validate the VIP management files before applying:

```bash
uv run ansible-playbook --syntax-check playbooks/opnsense/manage-vips.yml
uv run yamllint vars/opnsense/vips.yml playbooks/opnsense/manage-vips.yml
uv run ansible-lint playbooks/opnsense/manage-vips.yml
```

Additively apply reviewed PBR gateways from `ansible/vars/opnsense/gateways.yml`:

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/manage-gateways.yml
```

Validate the PBR gateway management files before applying:

```bash
uv run ansible-playbook --syntax-check playbooks/opnsense/manage-gateways.yml
uv run yamllint vars/opnsense/gateways.yml playbooks/opnsense/manage-gateways.yml
uv run ansible-lint playbooks/opnsense/manage-gateways.yml
```

For the FakeIP PBR design, aliases and IP Alias VIPs are prerequisites. PBR gateway objects provide a next-hop such as
`GW_PROXY` for future firewall rules to reference. The firewall PBR rules themselves remain outside this gateway
workflow and are a separate future capability.

DNAT / port-forward management is represented only by a failing placeholder:

```bash
uv run ansible-playbook playbooks/opnsense/manage-dnat.yml
```

The placeholder loads `ansible/vars/opnsense/dnat.yml` for future review structure, then fails intentionally without
calling OPNsense APIs. Raw API DNAT workarounds require a separate reviewed change.

## Safety rules

- Use `--check --diff` whenever supported.
- `manage-aliases.yml` creates or updates only aliases listed in `aliases.yml`; unlisted aliases are not deleted,
  disabled, or purged.
- `manage-vips.yml` creates, updates, or removes only IP Alias VIPs listed in `vips.yml`; unlisted VIPs are not deleted,
  disabled, or purged.
- `manage-gateways.yml` creates, updates, or removes only PBR gateways listed in `gateways.yml`; unlisted gateways are
  not deleted, disabled, or purged.
- `manage-dnat.yml` is a placeholder only; it intentionally fails before any API write because DNAT is not managed yet.
- Gateway entries must set `default_gw: false`; this workflow does not manage default-route ownership.
- VIP entries use OPNsense interface identifiers / network port values such as `lan`, `wan`, or `opt1`, not UI display
  names or custom labels such as `LAN` or `MGMT`.
- Gateway entries also use OPNsense interface identifiers / network port values such as `lan`, `wan`, or `opt1`, not UI
  display names or custom labels.
- VIP desired state is hand-written and reviewed; do not promote generated export artifacts directly into apply input.
- Gateway desired state is hand-written and reviewed; do not promote generated export artifacts directly into apply input.
- CARP, Proxy ARP, Other VIP modes, firewall rules, DNAT, NAT, port-forward, static routes, gateway groups, interfaces,
  and VLANs remain outside the managed scope.
- Alias type changes are not automatically migrated by delete/recreate; handle type migrations explicitly after review.
- Prefer `alias_multi` / `rule_multi` for coherent bulk changes later.
- Use OPNsense savepoints before firewall/NAT changes.
- Do not mix manual and Ansible ownership for the same rule set without a migration plan.
- Pin OPNsense and `oxlorg.opnsense` versions once actual management starts.
