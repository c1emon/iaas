# Ansible Automation

This directory contains Ansible automation for homelab network and service
management. Current workflows cover OPNsense API management and SKS8300/XikeOS
switch read-only facts plus safe configuration previews. Section 6 adds PVE guest
verification playbooks for read-only SSH/facts, hostname, static IP, resolver,
and qemu-guest-agent checks.

## Setup

Install Python dependencies and Ansible collections from this directory:

```bash
cd automation/ansible
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

The default Astra inventory is `../../environments/astra/ansible/inventory.yml`;
`ansible.cfg` points Ansible at that inventory, the reusable role path, and the
local collection cache at `collections/`.

PVE guest workflows use `../../environments/astra/generated/ansible/pve.yml`
explicitly instead of
the default inventory. That generated inventory is the source for `ops` login,
become settings, and non-secret host vars.

Secrets are injected at runtime from 1Password environment templates:

- `../../environments/astra/runtime/.env.opnsense.tpl` for OPNsense API variables
- `../../environments/astra/runtime/.env.switch.tpl` for switch SSH variables
- `../../environments/astra/runtime/.env.pve-opentofu.tpl` for PVE OpenTofu and generated
  cloud-init user material

Never commit plaintext vault passwords, private keys, API keys, generated
exports, or environment-specific secrets.

See `../../docs/pve-state-cache-secrets.md` for the shared state/cache/generated
artifact and 1Password runtime injection rules used by PVE, OPNsense, switch,
Packer, and guest workflows.

For PVE guest verification, DNS means the guest resolver configuration only:
the workflow checks `resolv.conf` nameserver entries against the NIC in
`pve_nics` marked `ansible_connection: true` and does not perform external DNS
lookups.

The canonical online guest verification command is repository-owned and lives at
`make pve-verify-guests` from the repository root. It is Ansible-first, uses the
generated PVE inventory, and never reads private keys from the repository.
Offline syntax validation remains separate at `make pve-ansible-syntax` for
verification and `make pve-bootstrap-guests-syntax` for bootstrap.

## PVE guest bootstrap

The PVE guest bootstrap flow is:

1. OpenTofu renders cloud-init identity and networking.
2. Ansible bootstraps the guest OS with `vm_baseline`.
3. Read-only guest verification confirms the result.

Bootstrap runs against the generated `pve_vms` inventory and uses the existing
`ops` SSH user plus sudo escalation from that inventory. It does not manage or
print private keys, and it does not mutate PVE lifecycle state. The first
version also keeps guest network configuration read-only; it only reports the
declared IP, gateway, and DNS facts from the Ansible-connection NIC.

### Optional guest package-access policy

The bootstrap playbook may receive an explicitly selected environment policy
file for the optional `vm_baseline` egress capability. Keep this file separate
from `environments/astra/generated/` and from the PVE VM inventory: generated
`pve_nics` facts remain authoritative for VM addresses and subnets, while the
policy declares package sources, trust material, proxy mode, and explicit
non-secret bypass destinations. Do not put passwords, tokens, private keys, or
certificate bodies in the policy.

The policy is applied only to the guest and is ordered before baseline package
installation. It may manage role-owned deb822 sources, verified signing
keyrings, custom CAs, APT proxy/auth files, and optional global shell/Git proxy
settings. It never changes PVE, guest interfaces/routes/DNS/firewall,
K3s/containerd registry policy, or workloads. The Packer APT mirror documented
in `../packer/proxmox/debian-13/README.md` remains build-time template input and
does not become this mutable guest policy.

Policy-enabled runs require the selected policy file and keep the existing
scope contract: the default limit is `pve_vms`, and `ANSIBLE_LIMIT` may narrow
the run to one or more named generated hosts. A missing selected file must fail
before contacting a guest. Pass the reviewed policy-vars file explicitly as an
entrypoint input through `VM_BASELINE_EGRESS_POLICY`:

```bash
make pve-bootstrap-guests \
  ANSIBLE_LIMIT=dev-web-01 \
  VM_BASELINE_EGRESS_POLICY=/path/to/reviewed-policy-vars.yml \
  VM_BASELINE_EGRESS_RUNTIME_SECRETS=/path/to/protected-runtime.json
```

Use the protected runtime-secret input required by the selected policy through
the documented runtime channel. Keep the file permission-restricted and
outside the repository; never pass resolved credentials as CLI values. Run the
syntax check with the same policy selection before an apply:

```bash
make pve-bootstrap-guests-syntax \
  VM_BASELINE_EGRESS_POLICY=/path/to/reviewed-policy-vars.yml
```

Lifecycle handling is explicit: no selected policy preserves existing state;
`present` converges it; `absent` removes only deterministic role-owned paths
declared for retirement. Unmanaged files and unknown APT sources are left
alone, and exclusive-source conflicts fail before mutation. Global shell/Git
proxy settings are off unless independently enabled with non-secret endpoints;
Git is not installed solely for proxy setup. For rollback, keep the previous
reviewed policy and re-run this same command with that file and its protected
runtime inputs. Do not roll back by deleting generated files or by omitting the
policy.

The shared `vm_baseline` role is intended for ordinary VMs first and can be
reused by future K3s nodes or other Debian guests that follow the same
generated inventory contract.

Example commands:

```bash
make pve-bootstrap-guests-syntax
make pve-bootstrap-guests ANSIBLE_LIMIT=dev-web-01
make pve-bootstrap-guests
make pve-verify-guests
```

## OPNsense playbooks

Run OPNsense commands with API credentials injected at runtime:

```bash
op run --env-file ../../environments/astra/runtime/.env.opnsense.tpl -- \
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
op run --env-file ../../environments/astra/runtime/.env.switch.tpl -- \
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
op run --env-file ../../environments/astra/runtime/.env.switch.tpl -- \
uv run ansible-playbook playbooks/switches/readonly-facts.yml --limit sw-core
```

Request YAML and JSON exports:

```bash
op run --env-file ../../environments/astra/runtime/.env.switch.tpl -- \
uv run ansible-playbook playbooks/switches/readonly-facts.yml \
  -e '{"switch_export_formats":["yaml","json"]}'
```

### Configuration preview and apply

Desired switch configuration lives in host-specific vars such as
`../../environments/astra/ansible/vars/switches/sw-core-vlans.yml`. The `switch_config` role accepts
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
op run --env-file ../../environments/astra/runtime/.env.switch.tpl -- \
uv run ansible-playbook playbooks/switches/config-plan.yml \
  --check --limit sw-core -e switch_config_apply=false
```

Live apply is opt-in. Only run it after reviewing the preview output and desired
vars:

```bash
ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:$PWD/collections" \
op run --env-file ../../environments/astra/runtime/.env.switch.tpl -- \
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

## PVE guest verification

Use the generated inventory explicitly when verifying guests:

```bash
make pve-verify-guests
```

That workflow is read-only: it confirms generated inventory assumptions, checks
hostname/static IP/qemu-guest-agent/sudo/root-SSH state on reachable guests, and
reports offline or DNS-mismatched guests as WARN without mutating anything.

The bootstrap workflow is separate from verification. It installs baseline guest
packages and services, converges or validates the hostname, reports reboot
markers, and prints read-only network facts. It still leaves PVE lifecycle and
guest network configuration untouched.

If you only need syntax validation for the Ansible playbook, use:

```bash
make pve-ansible-syntax
```

Guest configuration changes stay in Ansible roles. OpenTofu owns VM lifecycle,
cloud-init identity, and network inputs; Packer owns template creation.

## Validation commands

Run these before committing Ansible workflow changes:

```bash
uv run pytest ../../tests/ansible/test_xikeos_migration.py
uv run python -m compileall module_utils
uv run yamllint roles/switch_config/defaults/main.yml \
  roles/switch_config/tasks/main.yml \
  roles/switch_config/tasks/validate.yml \
  roles/switch_config/tasks/diff.yml \
  roles/switch_config/tasks/apply.yml \
  roles/switch_config/tasks/export.yml \
  playbooks/switches/readonly-facts.yml \
  playbooks/switches/tasks/export-readonly-facts.yml \
  playbooks/switches/config-plan.yml \
  ../../environments/astra/ansible/vars/switches/sw-core-vlans.yml
ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:$PWD/collections" \
uv run ansible-playbook --syntax-check playbooks/switches/readonly-facts.yml
ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:$PWD/collections" \
uv run ansible-playbook --syntax-check playbooks/switches/config-plan.yml
```

From the repository root, `make pve-ansible-syntax` is the explicit PVE guest
verification syntax-check target. It is intentionally outside default
`make check` and GitHub Actions for this P0 closure stage.

Use live switch check-mode previews only when credentials are available and the
target host is safe to contact.
