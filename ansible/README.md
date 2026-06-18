# Ansible Automation

This directory contains Ansible automation for homelab network and service
management. Current workflows cover OPNsense API management and SKS8300/XikeOS
switch read-only facts plus safe configuration previews.

## Setup

Install Python dependencies and Ansible collections from this directory:

```bash
cd ansible
uv sync
uv run ansible-galaxy collection install -r requirements.yml
```

If Ansible cannot find locally installed collections, include the collection path
explicitly when running a command:

```bash
ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:$PWD/collections" \
uv run ansible-playbook --syntax-check playbooks/switches/config-plan.yml
```

Do not commit installed Galaxy collections. They are local dependencies managed
by `requirements.yml` and ignored by Git.

## Inventory and secrets

Default inventory is `inventories/homelab.yml`; `ansible.cfg` points Ansible at
that inventory and the repository role/collection paths.

Secrets are injected at runtime from 1Password environment templates:

- `../.env.opnsense.tpl` for OPNsense API variables
- `../.env.switch.tpl` for switch SSH variables

Never commit plaintext vault passwords, private keys, API keys, generated
exports, or environment-specific secrets.

## OPNsense playbooks

Run OPNsense commands with API credentials injected at runtime:

```bash
op run --env-file ../.env.opnsense.tpl -- \
uv run ansible-playbook playbooks/opnsense/readonly.yml
```

Common OPNsense workflows:

| Playbook | Use case | Notes |
| --- | --- | --- |
| `playbooks/opnsense/readonly.yml` | Read-only API connectivity smoke test | Safe first check; no config mutation. |
| `playbooks/opnsense/export.yml` | Export OPNsense configuration data | Writes generated files under ignored export paths. |
| `playbooks/opnsense/snapshot.yml` | Capture a configuration snapshot | Use before risky changes. |
| `playbooks/opnsense/manage-aliases.yml` | Manage firewall aliases | Uses OPNsense API modules. |
| `playbooks/opnsense/manage-filter-rules.yml` | Manage firewall filter rules | Review vars and check mode before apply. |
| `playbooks/opnsense/manage-gateways.yml` | Manage policy-based routing gateways | Requires API write privileges. |
| `playbooks/opnsense/manage-vips.yml` | Manage virtual IPs | Requires interface/VIP API privileges. |
| `playbooks/opnsense/manage-dnat.yml` | Manage DNAT workflows or documented fallback | Review module/API support before use. |

Example syntax check:

```bash
uv run ansible-playbook --syntax-check playbooks/opnsense/readonly.yml
```

## Switch playbooks

Switch hosts use `ansible.netcommon.network_cli` with
`ansible_network_os: c1emon.xikeos.xikeos`. The native collection dependency is
declared in `requirements.yml` and pinned to the v0.2.1+ baseline. Collection
installation does not install Python parser libraries, so keep control-node
runtime dependencies such as `ttp` and `textfsm` available when the collection
requires them.

Run switch workflows with SSH credentials injected at runtime:

```bash
op run --env-file ../.env.switch.tpl -- \
uv run ansible-playbook playbooks/switches/readonly-facts.yml
```

Common switch workflows:

| Playbook | Use case | Notes |
| --- | --- | --- |
| `playbooks/switches/network-cli-smoke.yml` | Basic network CLI connectivity smoke test | Run first when validating credentials/transport. |
| `playbooks/switches/readonly-facts.yml` | Collect collection-native read-only facts | Uses `c1emon.xikeos.xikeos_facts`; does not configure the switch. |
| `playbooks/switches/config-plan.yml` | Preview or apply lifecycle-safe resource configuration | Defaults to non-mutating plan/check behavior. |

The read-only playbook is the supported entrypoint. It calls
`c1emon.xikeos.xikeos_facts` directly and then runs the playbook-owned export
tasks. There is no separate read-only facts role. Custom callers that need a
different workflow can invoke `c1emon.xikeos.xikeos_facts` directly and reuse
the export task shape from `playbooks/switches/tasks/export-readonly-facts.yml`.

### Read-only facts

Collect facts for one switch:

```bash
op run --env-file ../.env.switch.tpl -- \
uv run ansible-playbook playbooks/switches/readonly-facts.yml --limit sw-core
```

Request YAML and JSON exports:

```bash
op run --env-file ../.env.switch.tpl -- \
uv run ansible-playbook playbooks/switches/readonly-facts.yml \
  -e '{"switch_export_formats":["yaml","json"]}'
```

### Configuration preview and apply

Desired switch configuration lives in host-specific vars such as
`vars/switches/sw-core-vlans.yml`. The `switch_config` role accepts
collection-native grouped resource calls:

```yaml
switch_config_resources:
  vlans:
    - state: merged
      config:
        - vlan_id: 3999
          name: ansible-test
  l2_interfaces:
    - state: merged
      config:
        - name: Ethernet1/0/48
          mode: access
          access_vlan: 3999
```

The default policy only allows `merged` states. In v0.2.1, L3 and LAG `merged`
operations are additive and should not remove existing addresses or members that
are omitted from the requested config. Add states such as `deleted` or
`replaced` to `switch_config_allowed_states` only when the intended workflow
needs non-additive behavior.

Safe preview against `sw-core`:

```bash
ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:$PWD/collections" \
op run --env-file ../.env.switch.tpl -- \
uv run ansible-playbook playbooks/switches/config-plan.yml \
  --check --limit sw-core -e switch_config_apply=false
```

Live apply is opt-in. Only run it after reviewing the preview output and desired
vars:

```bash
ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:$PWD/collections" \
op run --env-file ../.env.switch.tpl -- \
uv run ansible-playbook playbooks/switches/config-plan.yml \
  --limit sw-core -e switch_config_apply=true
```

The role rejects legacy `switch_config_intent`, raw command lists, unknown
resource groups, missing `state`/`config`, and states outside
`switch_config_allowed_states`.

## PVE node bootstrap

Bootstrap the `pve-ops` Linux account on PVE nodes with a runtime-supplied
existing administrator login. The playbook expects the SSH public key from the
`pve-ssh-automation-user` 1Password item and installs a limited sudoers entry
that is intended to end at the wrapper-only state.

Example run against a node alias:

```bash
PVE_SSH_AUTOMATION_PUBLIC_KEY="$(op read op://Astra/pve-ssh-automation-user/public_key)" \
uv run ansible-playbook -i 'cohe,' -u <existing-admin-login> --become \
  playbooks/pve/bootstrap-pve-ops.yml \
  -e pve_bootstrap_authorized_key="$PVE_SSH_AUTOMATION_PUBLIC_KEY"
```

If the operator needs a temporary preflight sudo allowlist beyond the wrapper,
override `pve_bootstrap_sudo_commands` explicitly and reduce it back to the
wrapper-only final state after validation.

The playbook creates `pve-ops`, locks its password, installs the SSH key, and
writes a `NOPASSWD` sudoers fragment validated with `visudo`.

Optional smoke checks on a live node, if the operator chooses to run them later:

```bash
ssh <existing-admin-login>@cohe 'sudo -n visudo -cf /etc/sudoers.d/astra-pve-template-build'
ssh pve-ops@cohe 'sudo -n /usr/local/sbin/astra-pve-template-build --help'
```

These checks are documentation-only here; they are not required for repository
validation and do not change the global node SSHD policy.

## Validation commands

Run these before committing Ansible workflow changes:

```bash
uv run python -m unittest tests/test_xikeos_migration.py
uv run python -m compileall filter_plugins module_utils
uv run yamllint roles/switch_config/defaults/main.yml \
  roles/switch_config/tasks/main.yml \
  roles/switch_config/tasks/validate.yml \
  roles/switch_config/tasks/diff.yml \
  roles/switch_config/tasks/apply.yml \
  roles/switch_config/tasks/export.yml \
  playbooks/switches/readonly-facts.yml \
  playbooks/switches/tasks/export-readonly-facts.yml \
  playbooks/switches/config-plan.yml \
  vars/switches/sw-core-vlans.yml
ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:$PWD/collections" \
uv run ansible-playbook --syntax-check playbooks/switches/readonly-facts.yml
ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:$PWD/collections" \
uv run ansible-playbook --syntax-check playbooks/switches/config-plan.yml
```

Use live switch check-mode previews only when credentials are available and the
target host is safe to contact.
