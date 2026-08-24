## 1. Shared Validator Foundation

- [ ] 1.1 Add the `scripts/opnsense_validation` package with resource registry, safe YAML loading, validation error model, and CLI entrypoint.
- [ ] 1.2 Implement exact top-level/record key checks, required/optional fields, strict parsed-type helpers, identifier/interface token checks, IP/CIDR parsing, port/range parsing, and duplicate-identity helpers.
- [ ] 1.3 Ensure expected CLI validation failures exit `1` with concise field paths, no traceback, no complete-record dump, and no environment or credential values.

## 2. Resource Validation

- [ ] 2.1 Implement alias validation for repository-supported types/states, names, list content, type-aware values, strict enabled booleans, and unique names.
- [ ] 2.2 Implement IP Alias VIP validation for exact fields, interface syntax, IP-with-prefix addresses, strict bind/expand booleans, states, and unique `(address, interface)` match identities.
- [ ] 2.3 Implement PBR gateway validation for exact fields, names/interfaces, inet/inet6 address agreement, strict flags, numeric bounds/order, states, unique `(name, gateway)` match identities, and `default_gw: false`.
- [ ] 2.4 Implement new filter-rule validation for exact fields, generated identity, enums, scalar-or-list network/port tokens, booleans, sequence/port ranges, duplicate descriptions, and the existing deny/self-interface guard.
- [ ] 2.5 Keep the DNAT placeholder excluded from the supported mutation registry and verify that this change does not introduce a DNAT write path.

## 3. Offline and Playbook Admission Gates

- [ ] 3.1 Add `make opnsense-validate` for all supported desired-state files and include it in the root aggregate offline `check` target.
- [ ] 3.2 Wire resource-scoped validation into alias, VIP, PBR gateway, and new filter-rule playbooks before `include_vars`/credential preflight, with check-mode execution and `changed: false` behavior.
- [ ] 3.3 Retain or simplify resource-specific Ansible assertions only after confirming that the canonical Python validator and remaining defense-in-depth guards do not conflict.
- [ ] 3.4 Document the explicit offline validator, the direct-playbook admission gate, live-reference limitations, and the unsupported concurrent-edit assumption.

## 4. Tests and Validation

- [ ] 4.1 Add positive tests proving every committed supported OPNsense desired-state file passes without rewriting or coercion.
- [ ] 4.2 Add focused negative tests for unknown/missing keys, non-boolean values, invalid identifiers/interfaces, invalid IP/CIDR values, invalid ports/ranges, numeric bounds/order, unsafe default gateway ownership, and duplicate identities.
- [ ] 4.3 Add CLI tests for stable exit status and redacted operator-readable errors.
- [ ] 4.4 Add source/order tests proving every supported mutation playbook runs the canonical validator before credential preflight and mutation/reload modules.
- [ ] 4.5 Run focused validator tests, Ansible lint/syntax validation, strict OpenSpec validation, the aggregate offline gate, and secret scanning.
