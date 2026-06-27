## 1. Scope Confirmation

- [x] 1.1 Confirm `ops` is the guest automation user and should satisfy `sudo -n true`.
- [x] 1.2 Confirm `clemon` remains the human administration user with password-protected sudo.
- [x] 1.3 Confirm `scripts/sks8300_smoke.py` should be removed or archived rather than repaired in this change.
- [x] 1.4 Confirm ignored local runtime artifacts should not be deleted automatically.
- [x] 1.5 Confirm Phase 2 cloud-init checksum/manifest work remains out of scope.

## 2. Guest Automation Sudo Alignment

- [x] 2.1 Update runtime cloud-init guest user rendering so `ops` has explicit non-interactive sudo suitable for guest verification and Ansible become.
- [x] 2.2 Preserve password-protected sudo for `clemon`.
- [x] 2.3 Ensure direct root SSH login remains disabled and SSH password authentication remains disabled.
- [x] 2.4 Add or update tests proving rendered guest user-data expresses the intended `ops` and `clemon` sudo policies.
- [x] 2.5 Add or update guest verification docs/spec references if wording currently implies `ops` should require sudo password input.

## 3. Legacy Script and Documentation Hygiene

- [x] 3.1 Remove or archive `scripts/sks8300_smoke.py` as a supported repository script.
- [x] 3.2 Search Makefile, docs, OpenSpec, and tests for references to `sks8300_smoke.py` and remove/update stale references.
- [x] 3.3 Correct `docs/architecture.md` PVE node facts that conflict with `inventory/pve-cluster.yml`.
- [x] 3.4 If useful, add a short note explaining that retired switch smoke behavior belongs to the current switch collection/test surface rather than the removed legacy script.

## 4. Runtime Artifact Hygiene

- [x] 4.1 Verify no `terraform.tfstate*` files are tracked by Git.
- [x] 4.2 Verify `.terraform/`, `.venv/`, `.cache/`, `ansible/collections/`, and `.DS_Store` are ignored or otherwise prevented from being tracked.
- [x] 4.3 Update `.gitignore`, documentation, or an offline hygiene check if tracked-file protection is incomplete.
- [x] 4.4 Do not delete ignored local runtime artifacts automatically as part of this change.

## 5. Validation CLI Error Boundary

- [x] 5.1 Update `scripts/pve_inventory/cli.py` to catch expected repository validation errors and print `FAIL validation: <message>` to stderr.
- [x] 5.2 Update `scripts/services_inventory/cli.py` to use the same expected validation error behavior.
- [x] 5.3 Preserve tracebacks for unexpected programming errors outside expected validation failures.
- [x] 5.4 Add tests proving CLI validation failures exit with status 1 and do not print Python tracebacks.
- [x] 5.5 Ensure error messages do not print secret values or runtime credential material.

## 6. Static IP Error Context

- [x] 6.1 Wrap invalid `static_ip` parsing failures in `scripts/pve_inventory/vm_validation.py` as repository validation errors.
- [x] 6.2 Include field context in the error message, such as the VM name and `static_ip` field path.
- [x] 6.3 Add a negative test for malformed `static_ip` input.
- [x] 6.4 Avoid broad VM name/group/tag validation changes in this change.

## 7. Validation

- [x] 7.1 Run `make check` locally.
- [x] 7.2 Run the PVE inventory test subset locally.
- [x] 7.3 Run the services inventory test subset locally if service CLI behavior changed.
- [x] 7.4 Run `git ls-files '*.tfstate*'` and confirm it is empty.
- [x] 7.5 Inspect generated output diffs and confirm changes are intentional.
- [x] 7.6 Run `openspec validate fix-review-p1-remediations`.
