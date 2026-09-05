## 1. Policy contract

- [x] 1.1 Add synthetic baseline-egress fixtures for omitted, `present`, and `absent` lifecycle; explicit policy path; deb822 sources and signing keyrings; APT proxy/direct exceptions; custom CA; and independently enabled shell/Git proxies; verify they contain no real Astra endpoints or credentials.
- [x] 1.2 Add fail-closed validation for lifecycle, source identities, role-managed key SHA-256 or package-managed key fingerprint, fixed role-owned paths, proxy modes, runtime secret references, exact CA SHA-256, consumer-specific bypass values, and unknown keys; verify copied VM facts, plaintext credentials, and out-of-bound retirement are rejected.
- [x] 1.3 Compose generated `pve_nics` addresses and subnets with declared bypass policy without changing PVE inventory validation or generated inventory shape; verify deterministic normalized output and consumer-specific APT versus shell/Git rendering.

## 2. VM baseline convergence

- [x] 2.1 Add controller-side digest validation for role-managed key artifacts and read-only host prechecks for required trust tools, package-managed keyring existence/readability/fingerprint, unresolved secrets, and exclusive-source conflicts before mutation; add atomic role-owned signing-keyring and verified custom-CA management before repository access, and verify changed CAs refresh system trust while unchanged CAs do not.
- [x] 2.2 Add role-owned deb822 APT source and scoped APT proxy/auth rendering before package installation; verify restrictive credential-file permissions, host-only APT `DIRECT` entries, and failure before any mutation for unmanaged conflicts in exclusive mode.
- [x] 2.3 Refresh APT metadata only when declared policy or operator settings require it, then preserve the existing package-install behavior; verify ordering and repeat-run idempotence.
- [x] 2.4 Add independently enabled global shell and Git proxy handling for non-secret endpoints only; verify authenticated values are refused, disabled policy changes nothing, and Git is not installed solely for proxy configuration.
- [x] 2.5 Add `absent` convergence for declared deterministic role-owned paths; verify explicit cleanup refreshes trust/APT only when required, while omitted policy preserves state and unmanaged files remain unchanged.

## 3. Safety and operator surface

- [x] 3.1 Add protected runtime secret injection and redacted/no-diff tests for authenticated APT proxy or repository access; verify no plaintext credential enters CLI arguments, committed/generated/cached variables, Ansible facts/fact cache, ordinary controller temporary files, diffs, or logs, and verify protected temporary material is removed.
- [x] 3.2 Preserve guest-only scope; verify the role does not change interfaces, routes, DNS, firewall, PVE, K3s, container registries, or workload state.
- [x] 3.3 Add policy-vars selection to the existing bootstrap entrypoint while preserving its generated `pve_vms` default and narrower-limit behavior; verify a missing selected policy file fails before host contact and the no-policy baseline path remains unchanged.
- [x] 3.4 Document the build-time template mirror versus guest baseline policy boundary, managed-file lifecycle, optional shell/Git behavior, explicit retirement, and rollback by reapplying the previous reviewed policy.

## 4. Validation

- [x] 4.1 Run focused Ansible syntax/lint, YAML, deterministic-render, idempotence, invalid-policy, and redaction tests using synthetic inputs only.
- [x] 4.2 Run the complete repository offline gate and secret scan; verify no command contacts or mutates PVE, guests, package repositories, proxies, or external services.
- [x] 4.3 Strictly validate the OpenSpec change and review requirement-to-test coverage within the authorized software-only scope.
- [x] 4.4 Run complete GitNexus change analysis before commit and verify the final diff preserves existing PVE inventory and K3s ownership boundaries.
