## Context

The current repository already has PVE-specific helper targets and Python tooling. The next reliability step is not a new automation layer; it is a sharper command boundary.

The useful distinction is:

```text
                 safe anywhere
                      │
                      ▼
┌──────────────────────────────────────────────┐
│ Offline validation                            │
│ - generate / check-generated                  │
│ - Python tests                                │
│ - YAML lint                                   │
│ - OpenTofu fmt / validate                     │
│ - no PVE API, no 1Password, no SSH mutation   │
└──────────────────────────────────────────────┘
                      │
                      │ explicit operator action
                      ▼
┌──────────────────────────────────────────────┐
│ Online read-only / planning                   │
│ - PVE API preflight                           │
│ - Ansible ping / verification                 │
│ - OpenTofu plan                               │
│ - scoped credentials                          │
└──────────────────────────────────────────────┘
                      │
                      │ manual, reviewed, non-CI for now
                      ▼
┌──────────────────────────────────────────────┐
│ Mutation                                      │
│ - Packer build                                │
│ - OpenTofu apply / destroy                    │
│ - Ansible configuration changes               │
└──────────────────────────────────────────────┘
```

P0 should make the first box boring and repeatable. Later changes can improve online preflight, internal CI triggers, guest verification, and operations runbooks.

## Goals / Non-Goals

**Goals:**

- Provide root-level command names that are easy to run locally and from CI.
- Make `make check` the default offline safety gate.
- Ensure stale generated files are detected in the offline gate.
- Include Python tests, YAML lint, OpenTofu formatting, and OpenTofu validation in the offline gate where practical.
- Add cloud CI for offline validation only.
- Keep online checks explicit and outside the default CI path.
- Document command semantics so future CI platforms can call the same targets.

**Non-Goals:**

- Do not deploy Forgejo, Woodpecker, Drone, Jenkins, GitLab, or another internal CI platform in this change.
- Do not implement tag-triggered internal CI in this change.
- Do not add PVE online preflight functionality beyond preserving existing explicit targets if present.
- Do not run `tofu plan` as part of default offline `make check` if it requires provider initialization, live credentials, or environment-specific state.
- Do not run `tofu apply`, `tofu destroy`, Packer template builds, or Ansible mutation in CI.
- Do not introduce NetBox, Terragrunt, remote state, GitOps, or existing VM adoption.

## Decisions

### Use repository-owned commands as the stable CI contract

CI should be a thin wrapper around commands owned by the repository:

```text
make generate
make check-generated
make test
make lint-yaml
make tofu-fmt
make tofu-validate
make check
```

This avoids coupling validation semantics to a specific CI product. GitHub Actions, Woodpecker, Drone, Forgejo Actions, GitLab CI, or a manual shell session can all call the same targets.

Existing PVE-prefixed targets may remain as compatibility aliases. The root command surface should give operators short generic names for the default workflow while keeping risky commands visibly explicit.

### Keep offline checks offline

The aggregate `make check` target should not need:

- PVE API connectivity.
- OPNsense API connectivity.
- Switch SSH/API connectivity.
- 1Password secrets.
- SSH agent access.
- OpenTofu state access.
- Packer image downloads.

This means `make check` is suitable for cloud CI and for local validation before an operator moves to online work.

### Treat OpenTofu validation carefully

OpenTofu formatting is clearly offline. OpenTofu validation should be included only in a form that remains offline and reproducible for CI, for example after safe initialization without backend or live credentials if required by the provider layout.

If provider installation or module initialization is necessary, the implementation should document the expected initialization path and cache behavior. It should not require real PVE credentials or a live PVE endpoint.

### CI validates and reports only

The first cloud CI workflow should use GitHub Actions and run on pull requests and pushes to the main branch, but only for offline checks.

It should not expose infrastructure credentials. It should not perform online preflight, plan, apply, template builds, or Ansible mutation. If secret scanning is added, it should be configured to avoid leaking findings while still failing unsafe commits.

Secret scanning with tools such as `gitleaks` or `trufflehog` is deferred from the first P0 implementation so the initial change can focus on getting the command surface and offline CI stable before handling baseline findings or false positives.

### Online and mutation commands stay explicit

Targets such as PVE preflight, PVE plan, Packer build, apply, destroy, and guest verification should remain explicit and visually distinct. They may exist in the Makefile, but they should not be dependencies of `make check`.

Ansible syntax-check should also remain explicit for the first P0 implementation instead of becoming part of default `make check`. It can be promoted into the aggregate gate later after playbooks and inventories are stable enough to run without environment assumptions.

This preserves the roadmap rules:

```text
default checks = offline and safe
online operations = explicit
CI = validate and report, not auto-apply
```

## Open Questions

- Should YAML linting cover the whole repository immediately, or start with source-of-truth directories and expand after suppressing legacy noise?
