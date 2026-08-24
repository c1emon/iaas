## Context

The multi-NIC renderer uses each declared NIC name as netplan `set-name`. Linux interface names have a 15-character maximum, while the current validator reuses the 63-character DNS-label pattern. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**

- Fail offline validation before an unusable guest network-config is generated.
- Keep the existing lower-case DNS-label character policy and unique-within-VM rule.

**Non-Goals:**

- Do not change MAC matching, routing, DNS, bridge attachment, or generated artifact shape.
- Do not introduce automatic truncation, aliases, or guest-side post-boot renaming.

## Decisions

### Limit the existing NIC name field to 15 characters

The declared value is directly rendered into `set-name`; validation must match the strictest downstream platform constraint. Rejecting invalid input is safer than truncating, because truncation could cause duplicate or surprising interface names.

### Preserve the role field's DNS-label limit

NIC roles are descriptive inventory metadata and are not rendered as Linux interface names. Their existing validation remains unchanged.

## Risks / Trade-offs

- Existing unpublished inventories with long names will fail validation → operators must rename the interface deliberately before provisioning.
- A future non-Linux guest target may permit longer names → introduce a guest-platform abstraction only when such a target is actually supported.

## Migration Plan

1. Add the boundary validation and tests.
2. Regenerate/check artifacts; current inventory already uses compliant names.
3. Operators rename any future overlength declarations before running cloud-init render or apply.
