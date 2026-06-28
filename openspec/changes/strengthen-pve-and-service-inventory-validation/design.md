## Context

Phase 3a is about moving common source-of-truth mistakes left into repository validation:

```
inventory/*.yml
      │
      ▼
offline validation  ── rejects unsafe identifiers / malformed IPs / bad lists
      │
      ▼
renderers           ── escape documentation cells before Markdown emission
      │
      ▼
committed outputs   ── tfvars, Ansible inventory, generated docs
```

The key boundary is that this change validates repository-authored YAML and generated documentation only. It must not contact PVE, OPNsense, switches, guests, DNS, reverse proxies, or secret stores.

## Identifier Policy

The strictness should be domain-specific rather than one shared slug for everything:

| Field | Intended downstream use | Policy direction |
|---|---|---|
| `vms[].name` | PVE VM name, generated Ansible host, guest hostname context | DNS label / hostname-safe lower-case name |
| `vms[].ansible_groups[]` | Generated Ansible inventory group | Ansible-safe lower-case inventory group identifier |
| `vms[].tags[]` | PVE/OpenTofu tags and comma-joined provider inputs | PVE/provider-safe tag token, excluding delimiters/whitespace |
| service Markdown cells | Generated Markdown tables | Escape at render boundary, do not reject normal prose solely because it has Markdown metacharacters |

This keeps homelab naming policy separate from generic schema mechanics. It also avoids pushing PVE or Ansible policy into `services_inventory` except where service metadata references VM names that PVE validation already owns.

## Validation Shape

Prefer small, local helpers in the PVE validation area for this change. A later `extract-python-common-primitives` change can move truly generic helpers if duplication becomes painful.

Expected validation characteristics:

- errors include a field path or VM context;
- invalid operator-authored input raises the repository `ValidationError` boundary;
- negative tests cover each new policy;
- current valid inventory remains valid;
- normalized model keys and generated output schemas remain stable.

## Static IP Semantics

Static IP validation should continue to be offline and based on declared network data. The desired shape is:

```
vms[].static_ip ── parse CIDR interface
       │
       ├─ address family matches selected network
       ├─ prefix matches selected network CIDR
       ├─ host address is inside selected network
       ├─ address is usable host address for the declared network
       └─ address is unique across declared VMs
```

This avoids accepting values that parse syntactically but produce surprising cloud-init, OpenTofu, or operator documentation behavior.

## Markdown Escaping

Markdown escaping belongs at the renderer boundary. Validation should not reject normal operator prose just because it contains a pipe or newline. Table cells should be made one-line and safe:

- `|` becomes escaped so it does not create a new cell;
- `\n` and `\r` become a visible line-break placeholder or whitespace that keeps the row single-line;
- null/empty optional display values still use the existing `-` placeholder;
- warning table cells receive the same treatment as service endpoint rows.

## Open Questions

- Exact PVE tag character set should be based on the provider/PVE-accepted token set used by the current OpenTofu path, not an over-broad Markdown or shell-safe policy.
- For duplicate list elements, rejecting duplicates is simpler and safer for `ansible_groups` and `tags`; `dns` should remain governed by the existing selected-network equality rule unless implementation uncovers a clearer invariant.
