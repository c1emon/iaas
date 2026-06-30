## Context

The repository has grown into a small IaaS automation workspace with multiple operator-facing capabilities:

```text
inventory/*.yml
  operator-authored source of truth

scripts/*
  validation, generation, PVE health/preflight, service metadata helpers

infra/tofu/pve/
  OpenTofu PVE VM lifecycle root

infra/packer/proxmox/debian-13/
  Debian template build helper path

ansible/
  OPNsense, switch, PVE guest verification, and host bootstrap automation

docs/
  architecture, runbooks, roadmap, decisions, generated references
```

The root README should become the stable human entrypoint for operating the repository. It should not replace detailed runbooks or module guides; it should route readers to them.

## Goals / Non-Goals

**Goals:**

- Make root `README.md` an operator manual rather than a loose project status note.
- Give readers a capability map covering PVE, OPNsense, switches, service metadata, validation, generation, and safety boundaries.
- Document which files are source of truth and which generated outputs are committed.
- Explain command safety classes: offline-safe, online read-only, and mutation-capable.
- Provide common workflows and command examples at a concise level.
- Describe runtime parameter and secret-injection conventions without duplicating every module detail.
- Make `docs/README.md` a useful documentation index.
- Preserve module README files as module-specific usage references.

**Non-Goals:**

- Do not change command behavior, validation behavior, infrastructure behavior, or generated output content.
- Do not implement roadmap items or archive OpenSpec changes.
- Do not make root README a full copy of all module documentation.
- Do not move existing docs into a new hierarchy in this change unless the implementation identifies a tiny navigation-only adjustment.
- Do not create new automation, scripts, Make targets, playbooks, OpenTofu resources, or inventory fields.

## Decisions

### Root README is the operator manual

The root README should answer the first-order questions an operator has:

```text
What does this repository manage?
Which files do I edit?
Which outputs are generated?
Which commands are safe offline?
Which commands contact live infrastructure?
Which commands may mutate infrastructure?
How are secrets injected?
Which parameters matter for common workflows?
Where are detailed docs and runbooks?
```

Recommended structure:

```text
Overview
Repository capabilities
Source-of-truth files
Generated outputs
Safety model
Quick start
Common workflows
Runtime parameters
Secrets and sensitive files
Documentation map
Operational cautions
```

### Use safety classes consistently

The operator manual should classify workflows using stable language:

```text
offline-safe
  no live infrastructure access, no runtime secrets, no mutation

online read-only
  contacts live infrastructure, requires runtime credentials/context, does not mutate

mutation-capable
  may create, update, delete, upload, reboot, or otherwise change live state
```

This classification should appear before mutation-capable examples so readers understand risk before copying commands.

### Keep details below the top-level manual

The root README should include concise command examples and links. Deep details should remain in more specific files:

```text
docs/architecture.md
  architecture facts and topology

docs/roadmap.md
  current roadmap and backlog status

docs/pve-state-cache-secrets.md
  state/cache/generated artifact/secret handling runbook

docs/opnsense-management.md
  OPNsense management boundary and workflows

docs/service-metadata.md
  service metadata schema and boundaries

infra/tofu/pve/README.md
  OpenTofu PVE VM lifecycle module details

infra/packer/proxmox/debian-13/README.md
  template build details

ansible/README.md and playbook READMEs
  Ansible setup and playbook-specific usage
```

### Use docs index for navigation

`docs/README.md` should become a documentation index grouped by reader intent:

```text
Start here
Planning
Architecture
Operations and runbooks
OPNsense
PVE
Switches
Service metadata
Generated references
Decisions
Maintenance plans / historical context
```

The index should clearly distinguish current entries from historical/reference documents when applicable.

### Avoid changing implementation through documentation cleanup

This change must not change command targets, default validation gates, script behavior, generated file contents, or infrastructure operations. Any discrepancy discovered during documentation cleanup should be recorded as a follow-up, not silently fixed by changing behavior.

## Risks / Trade-offs

- **Risk: root README becomes too long.** Mitigation: use tables, concise workflow snippets, and links to detailed docs.
- **Risk: documentation duplicates module README details.** Mitigation: keep root README at operator-navigation level and leave module parameters/details in module README files.
- **Risk: readers confuse roadmap cleanup with operator manual cleanup.** Mitigation: reference `docs/roadmap.md` but keep roadmap status management in the separate roadmap consolidation change.
- **Risk: stale links.** Mitigation: validate touched links during implementation.

## Open Questions

- Should the operator manual be primarily English, primarily Chinese, or English with Chinese notes for local operation?
- Should command references remain in root README, or should very long command tables eventually move to a dedicated `docs/reference/commands.md`?
