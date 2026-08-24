## Context

The SKS8300 configuration framework now provides a safe plan/diff/apply/verify lifecycle for VLAN definitions. The same framework already collects interface facts through the read-only profile parser, but the config resource registry only supports `vlans`. Operators therefore cannot manage port mode or tagged/untagged VLAN membership declaratively.

Interface VLAN changes are higher risk than VLAN definition changes because a bad change can disconnect hosts or uplinks. The implementation must keep plan-only behavior by default, render only validated commands, and verify post-state before marking an apply successful.

## Goals / Non-Goals

**Goals:**

- Add an `interfaces` resource to `switch_config_intent` for SKS8300 switchport VLAN configuration.
- Support access, trunk, and hybrid mode intent with access VLAN, tagged VLAN IDs, and untagged VLAN IDs.
- Match interfaces by name as the primary key.
- Reuse `parse_switch_interfaces()` current-state facts rather than duplicating parser logic.
- Generate resource diffs and command plans for mode and VLAN membership changes.
- Keep live mutation gated by `switch_config_apply: true` and validate on a low-risk unused port only with operator approval.

**Non-Goals:**

- Do not support arbitrary raw interface commands.
- Do not manage physical interface state, speed, duplex, description, LAG membership, STP, PoE, ACLs, or routed interface settings in this change.
- Do not implement automatic rollback generation for failed port changes.
- Do not attempt to save running configuration to startup configuration.
- Do not manage production/uplink/management ports during validation.

## Decisions

### Add `interfaces` as a registry resource

The profile registry should define an `interfaces` resource with primary key `name`, `collect_subset: interfaces`, and fields such as `mode`, `access_vlan`, `tagged_vlans`, `untagged_vlans`, and `state`.

Alternative considered: add port settings under each VLAN resource. Rejected because interface membership is naturally keyed by port name and a port can carry many VLANs.

### Use explicit desired membership lists

Operators should declare the desired VLAN membership for each managed interface. Diff generation should compare normalized sorted integer lists for tagged and untagged VLAN IDs.

Alternative considered: additive-only fields such as `add_tagged_vlans`. Rejected for first implementation because it weakens idempotency and makes verification ambiguous. Operators can still limit blast radius by only declaring low-risk interfaces.

### Render conservative SKS8300 interface command blocks

The renderer should enter the interface context and emit mode/membership commands only from validated diffs, for example:

```text
interface Ethernet1/0/3
switchport mode hybrid
switchport hybrid allowed vlan 10;21;50 tag
switchport hybrid allowed vlan 99 untag
exit
```

Exact syntax must be verified against SKS8300 behavior during implementation. If live testing shows SKS8300 requires a different separator or command form, the renderer should be adjusted before task completion.

Alternative considered: use Cisco IOS interface commands. Rejected because SKS8300 is Cisco-like but not Cisco IOS.

### Validate interface intent before rendering

Validation should reject unsupported modes, invalid interface names, invalid VLAN IDs, inconsistent fields, and operations outside `switch_config_allowed_operations`. Examples:

- `mode: access` requires `access_vlan` and should not use tagged VLANs.
- `mode: trunk` uses tagged VLANs and should not use access VLAN.
- `mode: hybrid` may use tagged and/or untagged VLANs.
- VLAN IDs must be integers in supported range.

Alternative considered: tolerate extra fields and ignore them. Rejected because silent ignores are unsafe for configuration workflows.

## Risks / Trade-offs

- Port VLAN changes can disrupt connectivity → Require explicit apply and live validation on an unused/low-risk port.
- SKS8300 interface command syntax may differ from parser assumptions → Verify rendered commands with plan-only review and controlled live tests.
- Full replacement of VLAN membership may remove needed VLANs if intent is incomplete → Document that declared interfaces are authoritative for managed fields and require careful review.
- Existing parser may not capture all interface forms → Extend parser normalization only where needed and keep test cases for access/trunk/hybrid examples.
- No automatic rollback → Keep change report and manual rollback guidance; do not apply to critical ports without an operator rollback plan.

## Migration Plan

1. Extend resource metadata and validation for `interfaces`.
2. Extend diff and render behavior for interface mode and VLAN membership.
3. Update host-specific switch vars examples to include interface intent.
4. Run Python smoke tests against synthetic current facts and intents.
5. Run `yamllint`, `ansible-playbook --syntax-check`, and `ansible-lint`.
6. Run plan-only against `sw-core` for a low-risk port.
7. After operator approval, apply and verify a reversible low-risk port configuration, then restore the previous state.

## Open Questions

- Which physical port is approved for live validation?
- Should the first implementation support authoritative removal of VLAN membership, or only mode/member additions until command syntax is proven?
- What exact SKS8300 command syntax is required to remove a single tagged or untagged VLAN from an interface?
