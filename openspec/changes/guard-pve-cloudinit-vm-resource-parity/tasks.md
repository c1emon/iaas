## 1. Document the Intentional Resource Split

- [ ] 1.1 Add one source comment explaining the static lifecycle boundary, protected/unprotected resource addresses, exact allowed differences, and parity test ownership.
- [ ] 1.2 Add unique protected/unprotected begin/end guard markers around the existing resource blocks without changing HCL resource content or addresses.
- [ ] 1.3 Confirm the marker-only source edit produces no semantic OpenTofu configuration change.

## 2. Implement the Fail-Closed Parity Guard

- [ ] 2.1 Add a focused test helper that requires each marker exactly once and in order and extracts the two complete marked resource blocks.
- [ ] 2.2 Assert the exact resource labels, complementary count expressions, one protected-only literal `prevent_destroy = true`, and no unprotected `prevent_destroy` declaration.
- [ ] 2.3 Normalize only the three permitted difference classes, preserve all other resource text, and fail with a unified diff when normalized bodies differ.
- [ ] 2.4 Add negative cases for missing/duplicate/misordered markers, invalid selectors, missing or extra protection declarations, and unrelated one-sided resource changes.

## 3. Validation

- [ ] 3.1 Run the focused parity tests and confirm they pass for the current module and fail for controlled drift fixtures.
- [ ] 3.2 Run OpenTofu recursive format checking and module/root offline validation to confirm the marked HCL remains valid.
- [ ] 3.3 Run strict OpenSpec validation, the full root aggregate offline gate, and secret scanning.
- [ ] 3.4 Confirm no OpenTofu state, plan, resource address, generated input, or live PVE operation changed.
