## Why

The repository declares Pyright configuration and Ansible lint dependencies, while OpenSpec changes define contractual behavior, but the default offline gate does not execute all three. A green `make check` can therefore miss type, Ansible, or specification regressions.

## What Changes

- Add repository-owned targets for Pyright, Ansible lint, and strict OpenSpec validation.
- Make the aggregate offline gate invoke those targets without infrastructure credentials or mutation.
- Manage the OpenSpec and Pyright toolchain through committed project dependencies so cloud CI runs the same commands as local operators.
- Update CI setup and operator documentation for the expanded gate.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `iaas-validation-entrypoints`: The aggregate offline gate gains static typing, Ansible lint, and strict OpenSpec contract validation.

## Impact

- Root Makefile, Python and pnpm dependency metadata, CI setup, validation documentation, and Ansible lint compliance.
- No online PVE, OPNsense, switch, SSH, 1Password, plan, apply, or mutation operation is introduced.
