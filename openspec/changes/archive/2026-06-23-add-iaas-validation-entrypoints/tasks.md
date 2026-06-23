## 1. Command Surface

- [x] 1.1 Inventory existing root and PVE-specific Makefile targets and decide which become generic aliases.
- [x] 1.2 Add or standardize root `make generate` for committed generated PVE outputs.
- [x] 1.3 Add or standardize root `make check-generated` for stale generated output detection.
- [x] 1.4 Add root `make test` for Python/Ansible test suites that do not require live infrastructure.
- [x] 1.5 Add root `make lint-yaml` for source-of-truth YAML linting.
- [x] 1.6 Add root `make tofu-fmt` for recursive OpenTofu format checking.
- [x] 1.7 Add root `make tofu-validate` for offline OpenTofu validation.
- [x] 1.8 Add root `make check` that composes only offline-safe validation targets.
- [x] 1.9 Preserve explicit PVE operation targets such as `pve-check-pve`, `pve-plan`, `pve-apply`, and `pve-destroy` outside `make check`.

## 2. Offline Safety Boundaries

- [x] 2.1 Ensure `make check` succeeds without PVE API connectivity, OPNsense API connectivity, switch connectivity, 1Password secrets, SSH agent access, Packer builds, or OpenTofu apply-like operations.
- [x] 2.2 Ensure generated output checks fail when source YAML changes without regenerated committed outputs.
- [x] 2.3 Confirm generated outputs and CI logs do not contain passwords, password hashes, private keys, API token secrets, or other runtime secrets.
- [x] 2.4 Reconfirm passthrough edge cases covered by offline checks, including empty/null passthrough declarations and generated OpenTofu dynamic block inputs.

## 3. CI Validation

- [x] 3.1 Add a GitHub Actions cloud CI workflow that installs the repository toolchain and runs offline validation on pull requests and main-branch pushes.
- [x] 3.2 Ensure CI invokes repository-owned targets rather than duplicating validation logic inline.
- [x] 3.3 Ensure CI does not define or require PVE, OPNsense, switch, 1Password, SSH, or apply-capable secrets.
- [x] 3.4 Ensure CI does not run PVE preflight, OpenTofu plan/apply/destroy, Packer build, or Ansible mutation.
- [x] 3.5 Explicitly defer secret scanning with `gitleaks` or `trufflehog` to a follow-up change.
- [x] 3.6 Keep Ansible syntax-check available only as an explicit target, not as part of default `make check` in this P0 change.

## 4. Documentation

- [x] 4.1 Document the local validation flow: `make generate`, `make check-generated`, and `make check`.
- [x] 4.2 Document the difference between offline validation, explicit online checks, planning, and mutation.
- [x] 4.3 Document that CI is validation/reporting only and does not access internal infrastructure.
- [x] 4.4 Note that internal tag-triggered CI paths are deferred to `add-internal-ci-trigger-path`.

## 5. Validation

- [x] 5.1 Run the completed offline `make check` locally.
- [ ] 5.2 Run or inspect the CI workflow result after pushing the change.
- [x] 5.3 Verify no implementation step added mutation behavior to the default check path.
