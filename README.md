# Astra Infrastructure

This repository is being re-initialized as the source of truth for Astra infrastructure automation.

Current scope:

- No real secrets committed to Git.
- PVE automation foundation with YAML source-of-truth inventory, generated OpenTofu input, generated Ansible inventory, generated VM documentation, and generated service metadata documentation.
- Debian 13 PVE template build helpers under `infra/packer/`, executed through audited PVE-node wrappers.
- OpenTofu VM lifecycle configuration under `infra/tofu/`, using local state for the initial single-operator workflow.
- The legacy `terraform/` directory is only a placeholder; live PVE automation uses OpenTofu.
- Ansible bootstrap and verification content is added incrementally around the same inventory model.

Key areas:

- `docs/` — architecture, runbooks, decision records.
- `inventory/` — operator-authored PVE cluster and VM source-of-truth YAML.
- `infra/packer/` — PVE template build helpers and runbooks.
- `infra/tofu/` — OpenTofu-managed PVE VM lifecycle.
- `ansible/` — host configuration, service deployment, and low-risk network automation.
- `scripts/` — validation, generation, and runtime helper scripts.

## Python toolchain

Python-based tooling is managed with `uv`.

```bash
uv sync
uv run ansible --version
uv run ansible-lint --version
uv run yamllint --version
```

Commit `pyproject.toml` and `uv.lock`; do not commit `.venv/`.

## Validation

The default offline-safe gate is the repository root `make check` target.

```bash
make generate
make check-generated
make check
```

`make check` runs `check-generated`, `test`, `lint-yaml`, `tofu-fmt`, and
`tofu-validate`. It is the default offline-safe gate and it does not require PVE
credentials, PVE plan/apply/destroy access, Packer builds, guest SSH
verification, or service-doc regeneration.

Optional explicit hygiene checks are available outside the default gate:

```bash
make secret-scan
make pve-ansible-syntax
```

`make secret-scan` uses the repository `gitleaks` configuration to scan for
committed secrets. Gitleaks was chosen over TruffleHog for the first pass because
it has a small single-binary CLI, a reviewable repository config file, redacted
output, and straightforward CI installation. It remains explicit rather than a
`make check` dependency until false-positive behavior is proven stable.

PVE online checks stay explicit and outside `make check` / cloud CI:

```bash
op run --env-file infra/tofu/pve/.env.pve-opentofu.tpl -- make pve-preflight
op run --env-file infra/tofu/pve/.env.pve-opentofu.tpl -- make pve-health
```

`pve-preflight` is the apply-readiness check for planned VM lifecycle changes.
`pve-health` is the current-cluster health check. It uses the same canonical
`TF_VAR_pve_*` API variables, but no SSH fields, and reports pass/warn/fail/skip
with thresholds of CPU >90% warn, memory >90% warn, rootfs >90% warn / >98% fail,
and datastore >85% warn / >95% fail. Long-lived VMs missing or stopped warn;
ephemeral lab VMs missing or stopped do not warn solely for that state.

`make pve-verify-guests` runs the explicit online PVE guest verification command
without mutating guests. It is Ansible-first, uses the generated inventory, and
relies on the local SSH agent / 1Password SSH Agent context.
`make pve-ansible-syntax` runs the explicit PVE guest verification syntax check
without contacting guests.

Ansible syntax validation is intentionally separate from `make check` in this P0
closure change. The current root target delegates to `make pve-ansible-syntax`,
which syntax-checks `ansible/playbooks/pve/verify-guests.yml` against the
generated PVE inventory. Guest reachability and SSH verification remain under
the explicit online `make pve-verify-guests` target; `make pve-ansible-check`
remains a compatibility alias.

Explicit online or mutation operations stay outside the default gate:

- `make pve-preflight`
- `make pve-health`
- `make pve-check-pve`
- `make pve-plan`
- `make pve-apply`
- `make pve-destroy`
- `make pve-packer-build`
- `make pve-verify-guests`
- `make pve-ansible-check` (compatibility alias)

See `docs/pve-state-cache-secrets.md` for PVE state backup/restore, cache
cleanup, generated-output sensitivity, and 1Password runtime secret injection
guidance.
