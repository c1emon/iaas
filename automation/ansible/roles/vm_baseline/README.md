# vm_baseline role

`vm_baseline` is a reusable Debian guest bootstrap role.

It installs inventory-declared baseline packages, manages inventory-declared
baseline services, converges or validates the hostname against the inventory
identity, reports reboot-required markers, and prints read-only network facts.

Key defaults:

- packages: none; declare `vm_baseline_packages` in inventory/group vars
- time sync packages: none; declare `vm_baseline_time_sync_packages` in
  inventory/group vars when needed
- services: none; declare `vm_baseline_services` in inventory/group vars
- hostname mode: `converge`
- reboot reporting: enabled
- network validation mode: `report`

The role is intended for ordinary VMs first and can be reused by future K3s
nodes or other Debian-based guests that share the same inventory contract.

## Optional baseline egress policy

The role can consume an explicitly selected, environment-owned package-access
policy. This policy is guest bootstrap state: it is applied to a cloned Debian
VM after cloud-init and before baseline package installation. It is not part of
the PVE VM inventory, generated VM facts, or the Debian template.

Keep the two mirror boundaries separate:

- The Packer path in `automation/packer/proxmox/debian-13/` uses its APT mirror
  only while building the template. It must not be treated as the runtime
  policy for cloned guests.
- The baseline egress policy owns only guest APT sources, verified keyrings,
  custom CA files, APT proxy/auth files, and explicitly enabled shell/Git
  settings. It does not change interfaces, routes, DNS, firewall, PVE state,
  K3s/containerd registry settings, or workloads.

When a policy is selected, the playbook validates the complete document and
runtime inputs before the first guest mutation. The effective bypass set is
composed from the selected generated inventory's `pve_nics` (including the
connection NIC's address/subnet) and explicit non-secret destinations in the
policy. Do not copy VM addresses or subnets into the policy; APT receives
repository-host `DIRECT` entries, while shell and Git receive only forms they
support.

The policy lifecycle is deliberately explicit:

- Omit the policy to leave existing APT, trust, proxy, shell, and Git state
  untouched. Omission is not deletion.
- Use `present` to converge the declared state. Keyrings and custom CAs are
  verified before installation; managed deb822 sources and protected APT
  proxy/auth files are rendered before APT metadata is refreshed and before
  package installation.
- Use `absent` with the reviewed managed identities to retire policy. Only
  fixed, deterministically named files owned by this role are removed. Unknown
  or unmanaged source, keyring, CA, proxy, and tool files are never removed
  automatically.

The role-owned path families are fixed by identity and consumer:

```text
/etc/apt/keyrings/vm-baseline-<id>.gpg
/etc/apt/sources.list.d/vm-baseline-<id>.sources
/usr/local/share/ca-certificates/vm-baseline-<id>.crt
/etc/apt/apt.conf.d/80-vm-baseline-proxy
/etc/apt/auth.conf.d/80-vm-baseline-auth.conf
/etc/profile.d/vm-baseline-proxy.sh
/etc/gitconfig.d/vm-baseline-proxy.conf
```

`<id>` is the lowercase policy identity, not an arbitrary path. A policy may
retire only the artifacts it declares within these role-owned boundaries.

Global shell and Git proxy settings are independently disabled by default.
Enable them only for non-secret endpoints. Enabling Git proxy configuration
requires Git to already be installed; this role does not install Git merely to
configure a proxy. Authenticated proxy use belongs in protected per-command or
APT runtime injection, never in `/etc/profile`, global Git configuration,
committed vars, generated output, facts, diffs, logs, or ordinary controller
temporary files. Secret-bearing tasks are redacted and use restrictive
node-side files that are removed when no longer needed.

For a policy change, retain the last reviewed policy document and its matching
runtime secret reference. To roll back, select that previous document and run
the same bootstrap entrypoint with the same explicit inventory and limit. To
retire it instead, select `absent`; do not rely on an omitted file or a guessed
path. The bootstrap entrypoint and examples are documented in
`../../README.md`.

Package and service lists are intentionally empty in role defaults so the role
stays reusable and inventory controls environment policy. Group or host
variables can manage multiple baseline packages and services without editing
role tasks. For PVE guests, see
`environments/astra/generated/ansible/group_vars/pve_vms.yml`.

Common Debian VM examples:

```yaml
vm_baseline_packages:
  - ca-certificates
  - curl
  - dnsutils
  - iproute2
  - jq
  - qemu-guest-agent
  - sudo

vm_baseline_time_sync_packages:
  - systemd-timesyncd

vm_baseline_services:
  - name: qemu-guest-agent
    enabled: true
    state: started
  - name: systemd-timesyncd
    enabled: true
    state: started
```
