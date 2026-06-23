## Context

The repository now has a root offline validation contract through `make check` and a GitHub Actions workflow that runs it. That was the first P0 reliability milestone.

The remaining P0 items are not new infrastructure automation features. They are the operational safety rails that make the existing PVE automation repeatable:

```text
P0 validation entrypoints             Remaining P0 closure
────────────────────────              ──────────────────────────────
make check                            state backup/restore runbooks
├── check-generated                   .cache handling rules
├── test                              1Password env conventions
├── lint-yaml                         generated-output sensitivity
├── tofu-fmt                          secret scanning baseline
└── tofu-validate                     explicit Ansible syntax-check
                                      passthrough regression coverage
```

This change should finish the offline/documentation/testing side of P0 without crossing into P1 online operational closure.

## Goals / Non-Goals

**Goals:**

- Document local OpenTofu state backup and restore expectations.
- Document `.cache` directory contents, cleanup rules, and sensitivity boundaries.
- Document 1Password-driven runtime secret injection conventions for PVE, OPNsense, switch, Packer, OpenTofu, and cloud-init helper workflows.
- Make secret scanning available as an offline repository-owned validation path.
- Keep Ansible syntax-check explicit and standardized without making it part of the default offline gate yet.
- Reconfirm passthrough edge cases with offline tests or equivalent generated-output assertions.
- Preserve the rule that CI validates and reports only.

**Non-Goals:**

- Do not add PVE API online preflight.
- Do not add OpenTofu plan as part of default validation.
- Do not add Ansible guest reachability, SSH ping, or live guest verification.
- Do not implement internal Forgejo/Woodpecker tag-triggered CI.
- Do not introduce high-privilege PVE hardware mapping bootstrap.
- Do not add apply, destroy, Packer build, switch mutation, OPNsense mutation, or other live infrastructure changes to default checks.

## Decisions

### Treat this as P0 closure, not P1 expansion

The change should stay inside this boundary:

```text
safe anywhere / offline
┌────────────────────────────────────────────┐
│ docs, lint, tests, generated checks,       │
│ OpenTofu fmt/validate, secret scan         │
└────────────────────────────────────────────┘

explicit online / P1
┌────────────────────────────────────────────┐
│ PVE API preflight, plan, guest SSH,        │
│ internal runner trigger paths              │
└────────────────────────────────────────────┘
```

Alternative considered: include `pve-preflight`, `pve-plan`, and `ansible-pve-ping` because they appear in the roadmap P0 candidate list. Rejected for this change because they introduce live infrastructure, credentials, or environment-aware behavior and align better with the separate `add-pve-online-preflight` and `add-pve-guest-verification` changes.

### Add secret scanning with a reviewed baseline strategy

Secret scanning should become a repository-owned command rather than CI-inline logic. The likely shape is:

```text
make secret-scan
└── gitleaks or trufflehog with repo-owned config/baseline
```

The implementation should prefer a scanner/configuration that can run locally and in GitHub Actions without credentials. If initial findings include acceptable historical or placeholder values, the baseline or allowlist must be explicit and reviewable.

Whether `secret-scan` becomes a dependency of `make check` should be decided during implementation based on scanner stability:

- Preferred final state: `make check` includes `secret-scan`.
- Acceptable fallback: CI invokes both `make check` and `make secret-scan` while local `make check` remains unchanged until false positives are resolved.

### Keep Ansible syntax-check explicit for P0

The existing PVE module has `ansible-syntax` and the root Makefile exposes `pve-ansible-syntax`. This change may add a clearer generic or PVE-specific root target, but it should not make syntax-check a default `make check` dependency.

Rationale: Ansible playbook syntax-check is useful, but inventories, collections, and environment assumptions can drift. Promoting it into the default gate should be a later, explicit decision after playbook assumptions are stable.

### Document state/cache/secrets as operator contracts

The documentation should answer these operator questions:

- Which state files exist and how are they backed up?
- Which ignored cache paths may contain runtime-derived sensitive material?
- Which generated files are intentionally committed and non-sensitive?
- Which values are injected through `op run --env-file ...` and must never be committed?
- What should an operator check before and after plan/apply-like workflows?

The docs should not create new mutation behavior. They should clarify the boundary around existing helpers such as `make pve-backup-state`, cloud-init snippet rendering, Packer template env generation, and 1Password environment templates.

### Reconfirm passthrough through offline artifacts

Passthrough checks should remain local and generator-focused:

```text
inventory/vms.yml
   │
   ▼
scripts.pve_inventory validation
   │
   ▼
generated.auto.tfvars.json
   │
   ▼
OpenTofu dynamic hostpci inputs
```

The implementation should add or verify coverage for omitted, null, and empty passthrough declarations; generated Ansible inventory behavior for passthrough VMs; cloud-init user-data expectations; and OpenTofu dynamic host PCI block inputs. No live PCI device or PVE mapping check belongs in this change.

## Risks / Trade-offs

- Secret scanner false positives block useful work → Start with explicit config/baseline and review findings before adding scanner to the default gate.
- Too much P0 scope delays P1 online preflight → Keep online checks and runner trigger paths explicitly out of scope.
- Documentation can drift from Makefile behavior → Validation tasks should include checking documented command names against actual root targets.
- Ansible syntax-check may look offline but require collection/inventory assumptions → Keep it explicit until promoted by a later change.
- Passthrough tests may duplicate existing coverage → Prefer filling gaps and documenting confirmed coverage rather than rewriting stable tests.
