## Context

The repository now has a clear offline validation boundary and an explicit PVE online preflight that checks PVE control-plane readiness before plan/apply-like workflows. The remaining P1 gap is guest-side operational visibility: after repo-managed VMs are expected to exist, operators need a read-only command that verifies whether declared guests are reachable and have the expected identity/runtime signals.

There is already an Ansible playbook at `ansible/playbooks/pve/verify-guests.yml` and a generated inventory at `ansible/inventories/generated/pve.yml`. The current playbook asserts hostname, static IP, resolver nameservers, and qemu-guest-agent state, but it behaves like a fail-fast check and is not yet shaped as a canonical P1 verification workflow with warning semantics for intentionally offline guests.

Confirmed constraints for this change:

- Guest SSH user is fixed to `ops` for first-version verification.
- Declared VMs that are offline or unreachable produce warnings, not blocking failures.
- DNS checks produce warnings in the first version.
- Ansible is the primary implementation path.
- SSH credentials come from the local SSH agent / 1Password SSH Agent; repository code does not read private keys.

## Goals / Non-Goals

**Goals:**

- Add a canonical explicit guest verification target such as `make pve-verify-guests`.
- Verify only repo-managed VMs declared in `inventory/vms.yml` and rendered into generated Ansible inventory.
- Keep verification read-only and safe: no repair, package install, user creation, SSHD change, sudoers change, DNS mutation, VM lifecycle action, or PVE mutation.
- Use Ansible to check SSH reachability, guest hostname, declared static IP, qemu-guest-agent service, `ops` passwordless sudo, root SSH disabled, expected inventory group/tag metadata where available, and DNS as warning-only.
- Provide operator-readable pass/warn/fail/skip output and zero exit when only warnings/skips are present.
- Keep guest verification outside `make check` and GitHub Actions cloud CI.

**Non-Goals:**

- Do not create, start, stop, destroy, or modify VMs.
- Do not remediate guest configuration drift.
- Do not manage DNS, OPNsense, switch, or reverse-proxy records.
- Do not validate hand-created VMs that are not declared in `inventory/vms.yml`.
- Do not add automatic internal CI triggers; that remains a later change.
- Do not introduce NetBox, dynamic PVE inventory, or a new secrets system.

## Decisions

### Use Ansible as the verification engine

Guest verification is SSH-centric and maps naturally to Ansible inventory, facts, service checks, command checks, and host grouping. The existing generated inventory already contains `ansible_host`, `ansible_user`, `ansible_become`, VM metadata, network metadata, template metadata, and group membership, so the first version should refine the existing playbook rather than introduce a Python SSH framework.

Alternative considered: implement all checks in Python for preflight-style result aggregation. Rejected for first version because Ansible already owns guest reachability/configuration workflows and avoids duplicating SSH/facts behavior.

### Treat offline declared guests as warnings

Unlike PVE preflight, guest verification is not a blocking control-plane readiness gate in the first version. A declared VM may be intentionally stopped, absent before first apply, or temporarily unreachable. The command should therefore report offline/unreachable guests as WARN and exit successfully when no hard failures occur.

Hard failures should be reserved for cases where the command cannot run correctly or a reachable guest violates a core safety invariant, such as the expected `ops` user being unable to perform non-interactive sudo when the host is otherwise reachable.

### Keep DNS warning-only

The PVE automation foundation explicitly deferred DNS mutation. A DNS mismatch is still useful operator information, but it should not block guest verification until DNS automation or DNS source-of-truth support exists.

### Keep SSH credentials external to repository code

The generated inventory sets `ansible_user: ops`. Authentication should rely on the operator's normal SSH agent or 1Password SSH Agent. The playbook and Make targets must not read private keys from 1Password, write key files, or print credential material.

### Preserve offline validation boundaries

`make pve-verify-guests` is online and guest-reaching. It should be explicit and documented, not part of root `make check` or GitHub Actions. A syntax-only target may remain offline-compatible if it does not connect to guests.

## Risks / Trade-offs

- Warning-only offline guests can hide outages → Make the report clear and count warnings; a later stricter mode can promote offline guests to failures if operators want a readiness gate.
- Ansible assert failures are normally fatal → Use playbook structure that records per-host findings and avoids aborting the whole run for warning-class conditions.
- DNS checks can be environment-dependent → Keep DNS as warning-only and document the non-goal until DNS automation exists.
- Existing generated inventory may not include all expected metadata → Prefer using existing non-secret vars first; add only minimal generated vars if needed.
- No declared VMs or empty inventory can look like success → Report SKIP with exit 0 so operators know no guest verification was performed.
