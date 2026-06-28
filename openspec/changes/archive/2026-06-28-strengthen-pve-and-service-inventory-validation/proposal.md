## Why

The Phase 3a review remediation roadmap calls out two related source-of-truth hardening gaps: PVE VM inventory accepts some identifiers and list values too loosely, and generated service documentation can be broken by Markdown table metacharacters in operator-authored strings.

These failures should surface early in offline validation rather than later in OpenTofu, Ansible, PVE provider behavior, or generated documentation review. The change should remain a narrow validation/rendering hardening pass, not a broader inventory rewrite.

## What Changes

- Harden PVE VM inventory validation for VM names used as hostnames, Ansible inventory groups, PVE tags, static IP declarations, and textual list fields.
- Make duplicate handling explicit for VM string-list fields that participate in generated outputs.
- Ensure invalid values fail with operator-readable validation errors that identify the relevant source field.
- Escape service metadata values rendered into Markdown tables so `|`, newlines, and carriage returns cannot corrupt table structure.
- Preserve the current offline validation boundary: no PVE, OPNsense, switch, SSH, 1Password, or mutation-capable access.
- Keep current `inventory/*.yml` valid; if a new rule rejects existing source data, treat that as either an input correction or an overly narrow rule to resolve deliberately.

## Capabilities

### Modified Capabilities
- `pve-inventory-validation-structure`: Adds source-of-truth value hardening for VM name/hostname, Ansible groups, PVE tags, string-list values, and static IP semantics.
- `service-metadata-inventory`: Requires generated service Markdown tables to escape operator-authored cell values while remaining non-sensitive and documentation-only.
- `iaas-validation-entrypoints`: Keeps these checks inside the existing offline validation/generation surface and preserves CLI validation error behavior.

## Impact

- Affected areas:
  - `scripts/pve_inventory/vm_validation.py` and focused validation helper/tests.
  - `scripts/services_inventory/render.py` and service documentation rendering tests.
  - Existing generated outputs if escaping changes any currently rendered special characters.
  - Existing `inventory/vms.yml` and `inventory/services.yml` as fixtures for valid current-state behavior.
- Operational impact:
  - Operators get faster, clearer feedback for unsafe YAML source-of-truth values.
  - Generated `docs/generated/services.md` remains reviewable even when service metadata contains Markdown metacharacters.
  - Default checks remain offline and CI-compatible.
- Non-goals:
  - OPNsense vars validation.
  - Refactoring `scripts/common/` primitives.
  - Live PVE/provider validation or online preflight expansion.
  - Changing inventory schema version or generated output shape beyond necessary escaping.
