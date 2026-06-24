## 1. Discovery and Existing Workflow Alignment

- [ ] 1.1 Inventory current `verify-guests`, `pve-ansible-check`, generated PVE inventory, Ansible vars, docs, and Makefile targets related to guest verification.
- [ ] 1.2 Confirm generated inventory fields are sufficient for hostname, static IP, DNS, qemu-guest-agent, sudo, root SSH, groups, and tag checks.
- [ ] 1.3 Decide whether first-version result aggregation is implemented entirely in Ansible, through a small wrapper script, or by combining Ansible JSON output with a Python reporter.
- [ ] 1.4 Confirm no guest verification task requires package installation, user creation, SSHD changes, DNS mutation, VM lifecycle operations, or PVE mutation.

## 2. Command Surface and Offline Boundary

- [ ] 2.1 Add canonical root `make pve-verify-guests` delegating to the PVE module guest verification target.
- [ ] 2.2 Add or refine `infra/tofu/pve` guest verification target invoking the repository-owned verification implementation.
- [ ] 2.3 Preserve compatibility for existing `pve-ansible-check` / `verify-guests` targets or document any target rename/alias decision.
- [ ] 2.4 Ensure guest verification is not a dependency of root `make check` or GitHub Actions cloud CI.
- [ ] 2.5 Keep syntax-only Ansible validation available separately from live guest verification.

## 3. Guest Verification Semantics

- [ ] 3.1 Target only repo-managed VMs rendered into the generated PVE Ansible inventory group.
- [ ] 3.2 Use `ops` as the guest SSH user and rely on local SSH agent / 1Password SSH Agent without reading private keys in repository code.
- [ ] 3.3 Report no declared/generated guests as SKIP with successful exit.
- [ ] 3.4 Report offline, powered-off, or SSH-unreachable declared guests as WARN with successful exit when no hard failures exist.
- [ ] 3.5 Report DNS mismatches as WARN in the first version.
- [ ] 3.6 Define pass/warn/fail/skip result output and exit behavior: non-zero only on hard failures.

## 4. Read-Only Guest Checks

- [ ] 4.1 Verify SSH reachability for generated guest hosts without mutating guests.
- [ ] 4.2 Verify guest hostname matches inventory hostname when reachable.
- [ ] 4.3 Verify declared static IP is present in gathered guest facts when reachable.
- [ ] 4.4 Verify qemu-guest-agent is installed/running or otherwise visible through read-only guest facts/commands.
- [ ] 4.5 Verify `ops` can run non-interactive sudo for a read-only command such as `sudo -n true`.
- [ ] 4.6 Verify root SSH login is disabled using read-only inspection of effective SSHD configuration where available.
- [ ] 4.7 Verify expected inventory groups/tags where available without requiring guest-side mutation.
- [ ] 4.8 Ensure all checks avoid changing files, services, users, packages, sudoers, SSHD configuration, DNS, firewall, switch, PVE, or VM lifecycle state.

## 5. Documentation

- [ ] 5.1 Document canonical invocation for guest verification and its dependency on guest SSH context.
- [ ] 5.2 Document that `ops` SSH access uses local SSH agent / 1Password SSH Agent and no repository-managed private key files.
- [ ] 5.3 Document WARN semantics for offline guests and DNS checks.
- [ ] 5.4 Update validation docs to keep guest verification outside `make check` and GitHub Actions cloud CI.
- [ ] 5.5 Document the relationship between PVE online preflight and guest verification: preflight checks PVE readiness; guest verification checks declared guest runtime state.

## 6. Tests and Offline Safety

- [ ] 6.1 Add tests or static checks proving `make check` and GitHub Actions do not invoke guest verification.
- [ ] 6.2 Add syntax/offline tests for the Ansible guest verification playbook or wrapper.
- [ ] 6.3 Add fixture or unit tests for no-guests SKIP behavior if a wrapper/reporter is introduced.
- [ ] 6.4 Add fixture or unit tests for WARN handling of unreachable guests and DNS mismatches if a wrapper/reporter is introduced.
- [ ] 6.5 Add tests ensuring no private key material, guest passwords, or resolved SSH credentials are printed or stored.
- [ ] 6.6 Add regression tests for generated inventory assumptions needed by guest verification.

## 7. Validation

- [ ] 7.1 Run `make check` locally.
- [ ] 7.2 Run guest verification syntax/offline tests locally.
- [ ] 7.3 Run `make secret-scan` locally.
- [ ] 7.4 Run `openspec validate add-pve-guest-verification`.
- [ ] 7.5 If a repo-managed guest is available and SSH context is configured, run `make pve-verify-guests` locally and record pass/warn/fail/skip results.
- [ ] 7.6 Inspect CI after pushing to confirm only offline validation runs in GitHub Actions.
