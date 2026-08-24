## 1. Managed validation toolchains

- [x] 1.1 Add Pyright to the uv-managed development dependencies and pin OpenSpec through pnpm.
- [x] 1.2 Add repository-owned typecheck, Ansible lint, and strict OpenSpec validation targets.

## 2. Offline gate implementation

- [x] 2.1 Include the new targets in the aggregate offline check without adding online operations.
- [x] 2.2 Resolve Ansible lint violations in maintained playbooks and roles.
- [x] 2.3 Update CI setup to install the locked Node toolchain before running the aggregate gate.
- [x] 2.4 Update operator documentation with the expanded validation contract.

## 3. Validation

- [x] 3.1 Run each new target independently.
- [x] 3.2 Run the complete offline gate and confirm it does not require runtime secrets.
- [x] 3.3 Run strict OpenSpec validation for this change and the repository.
