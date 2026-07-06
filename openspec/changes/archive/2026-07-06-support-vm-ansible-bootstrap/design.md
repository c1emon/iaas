## Context

The PVE automation foundation already renders VM source-of-truth data into
OpenTofu inputs and a generated Ansible inventory. Cloud-init currently creates
guest users and first-boot access, while `pve-verify-guests` performs read-only
guest reachability and identity checks. There is no repository-owned workflow
that converges ordinary guest VMs after first boot.

K3s platform automation needs this missing layer before K3s-specific roles are
introduced. A common bootstrap role lets ordinary VMs and future K3s nodes share
the same base operating-system assumptions while keeping cloud-init narrow and
one-shot.

## Goals / Non-Goals

**Goals:**

- Add an explicit Ansible entrypoint for bootstrapping declared PVE guest VMs.
- Reuse `ansible/inventories/generated/pve.yml` and the generated `pve_vms`
  group as the target source of truth.
- Provide a reusable common VM baseline role for Debian cloud-image guests.
- Keep the bootstrap idempotent, reviewable, and safe to re-run.
- Make the workflow suitable as the base layer for future K3s node bootstrap.
- Preserve the existing read-only guest verification workflow as a separate
  validation stage.

**Non-Goals:**

- Managing K3s installation, Cilium, Flux, CSI, or application workloads.
- Rewriting guest network configuration, routes, or DNS in the first version.
- Creating, starting, stopping, destroying, importing, migrating, or otherwise
  mutating PVE VM lifecycle state.
- Managing PVE host networking, OPNsense, switches, DNS records, or storage
  services.
- Replacing cloud-init; cloud-init remains the first-boot handoff mechanism.
- Supporting non-Debian guest operating systems in the first version.

## Decisions

### Add a `vm_baseline` role and PVE guest bootstrap playbook

The implementation should add a reusable role such as `ansible/roles/vm_baseline`
and an explicit playbook such as `ansible/playbooks/pve/bootstrap-guests.yml`.
The playbook should target generated PVE guest hosts, apply the role with
privilege escalation, and remain safe to re-run.

Alternative considered: keep adding checks to `verify-guests.yml`. This was
rejected because verification is intentionally read-only and should not become a
remediation workflow.

### Target generated inventory, not ad-hoc host lists

Bootstrap should use the generated PVE inventory and default to the `pve_vms`
group, with an operator-provided limit available for narrower runs. This keeps VM
definitions in the existing YAML source of truth and avoids duplicated bootstrap
inventory.

Alternative considered: maintain a separate static bootstrap inventory. This was
rejected because it would drift from generated PVE VM metadata and complicate
future K3s grouping.

### Keep network changes out of the first version

The role may assert or report expected IP, gateway, DNS, and route facts from the
generated inventory, but it should not edit guest network files. Network
initialization remains cloud-init's responsibility until the separate multi-NIC
cloud-init design is implemented.

Alternative considered: have Ansible own network configuration immediately. This
was rejected because the current VM model is single-NIC cloud-init based, and
the next K3s milestone needs a dedicated multi-NIC schema and cloud-init
network-config change.

### Use package-manager primitives and standard Debian services

The baseline should use `ansible.builtin.apt`, `ansible.builtin.service`,
`ansible.builtin.user`, `ansible.builtin.authorized_key`, `ansible.builtin.copy`,
and related built-ins rather than shelling out where modules exist. Base packages
should include operational prerequisites such as qemu-guest-agent, curl,
ca-certificates, jq, iproute2, and time-sync tooling. Package lists should be
variable-driven so K3s roles can extend them later.

Alternative considered: run raw shell bootstrap scripts. This was rejected
because module-based Ansible is more idempotent, easier to lint, and easier to
audit.

### Separate bootstrap, syntax, and verification entrypoints

The root and PVE Makefiles should expose explicit targets for bootstrap and
syntax checking, while the existing guest verification target remains a separate
post-bootstrap check. The normal safety flow should be:

```text
pve-guest-bootstrap-syntax
  → pve-bootstrap-guests
  → pve-verify-guests
```

Alternative considered: make `pve-verify-guests` automatically remediate. This
was rejected to preserve the read-only contract of guest verification.

## Risks / Trade-offs

- **Bootstrap can change reachable guest state unexpectedly** → Scope changes to
  a common baseline, require explicit operator-run entrypoints, keep PVE and
  network mutation out of scope, and document affected tasks.
- **Running against powered-off or intentionally ephemeral VMs creates noise** →
  Support Ansible limits and make unreachable handling operator-readable.
- **Package upgrades may cause drift or reboot requirements** → Install baseline
  packages with controlled package state, avoid broad `latest` upgrades by
  default, and report reboot-required state rather than rebooting automatically.
- **Network ownership confusion with future multi-NIC work** → Make first-version
  network handling read-only and document that cloud-init owns initial network
  configuration.
- **K3s-specific assumptions leak into ordinary VMs** → Keep K3s packages,
  kernel parameters, and services in later K3s-specific roles; the common role
  only provides VM baseline behavior.

## Migration Plan

1. Add the common VM baseline role with conservative defaults.
2. Add the PVE guest bootstrap playbook targeting generated inventory.
3. Add Makefile targets for bootstrap and syntax check.
4. Update documentation to describe the cloud-init → Ansible bootstrap →
   verification flow.
5. Run syntax/lint checks and existing tests.
6. Bootstrap can be rolled back manually by reverting role-managed files or by
   restoring VM snapshots if an operator took snapshots before first rollout.

## Open Questions

- Should the first version install a monitoring or backup agent, or leave those
  for separate capabilities?
- Should baseline package lists differ for ephemeral/lab and long-lived VMs, or
  use one common default with per-group overrides?
- Should a later change promote read-only network validation into a shared role
  consumed by both bootstrap and guest verification?
