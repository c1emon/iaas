# Fix OPNsense rule port validation

## Why
Rule declarations such as `[8848, 9848]` pass check/plan but are converted to `8848,9848`, which the API rejects. Saved failure facts omit the validation field and reason. The original failure field was not captured, so this conversion defect is not proven to be the only cause.

## What Changes
- Share one filter-rule port constraint between offline admission and every provider mapping.
- Accept one port, an explicit ascending inclusive range within 1..65535, or a port alias. A singleton list remains equivalent to its scalar; multiple selectors and comma strings are rejected without widening or alias creation.
- Validate known alias types and preserve planning's effective dependency checks.
- Persist bounded, sanitized API validation fields and static reasons through the protected stage and workflow result/recovery files; unknown text is redacted.

## Authorized global logging extension
The follow-up request requires a repository-wide check of critical output. Extend the existing repair to the shared Ansible callback, protected subprocess summaries, runtime public JSON and launcher stderr. Preserve recognized static protected assertion gates in K3s/switch/baseline tasks, API failures in OPNsense, and warning presence without weakening no_log. Reuse existing private captures and summaries; no new evidence service or device acceptance stage.

## Impact
Filter-rule validation, Python writer, both Ansible mappings, save failure diagnostics, and local tests. No provider pin change, device mutation, recovery execution, release, or production qualification.
