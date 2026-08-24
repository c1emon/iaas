## Why

The OPNsense mutation playbooks currently perform uneven in-play assertions, and several checks run only after credential preflight. Malformed hand-written variables, unexpected keys, string-typed booleans, invalid ports, or invalid network values should fail deterministically offline and before any OPNsense API access or write attempt.

## What Changes

- Add one repository-owned, offline validator for the supported OPNsense mutation inputs: aliases, IP Alias VIPs, PBR gateways, and new filter rules.
- Validate exact top-level and per-record keys, required/optional fields, parsed value types, supported states/enums, identifier/interface syntax, IP/CIDR values, port values/ranges, numeric bounds, and duplicate managed identities.
- Add an explicit `make opnsense-validate` target and include it in the root aggregate offline check.
- Require each supported mutation playbook to invoke the same validator before API credential preflight and before any module capable of changing OPNsense state.
- Return concise field-path errors without credentials, full records, or Python tracebacks for expected validation failures.
- Keep existing resource-specific safety rules, including generated filter-rule identity and `default_gw: false`, and retain in-play assertions as defense in depth where useful.
- Keep the fail-closed DNAT placeholder outside this change because it has no mutation path and intentionally rejects all apply attempts.
- Do not add online existence checks, API reads, OPNsense writes, schema generation from exports, or automatic correction/coercion of invalid inputs.

## Capabilities

### New Capabilities

- `opnsense-mutation-input-validation`: Defines shared offline validation and pre-mutation admission behavior for supported OPNsense desired-state files.

### Modified Capabilities

- `iaas-validation-entrypoints`: Adds OPNsense desired-state validation to the repository-owned aggregate offline gate.

## Impact

- Affected areas:
  - A small Python validation package and unit tests under `scripts/`.
  - Root Make targets and the aggregate offline gate.
  - `ansible/playbooks/opnsense/manage-aliases.yml`, `manage-vips.yml`, `manage-gateways.yml`, and `manage-filter-rules.yml` pre-mutation ordering.
  - Operator documentation for OPNsense validation.
- Operational impact:
  - Invalid local desired state fails before credentials or network access are needed.
  - Direct playbook execution cannot bypass the shared local validation step.
  - Valid current desired-state files remain accepted; this change does not mutate OPNsense.
- Dependencies:
  - Reuse the existing uv-managed Python and PyYAML toolchain; add no new runtime service or infrastructure credential.
