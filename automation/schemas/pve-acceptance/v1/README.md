# PVE acceptance / snippet cleanup v1 schemas

The four independent kind/version contracts are exported from
`iaas.pve_acceptance_contracts.contract_schemas()`. Shared accepted and rejected
examples live in `docs/examples/pve-acceptance/cases.json`; contract tests load
those exact files and check that these schema exports remain current.

Schemas establish structure, bounded values, and mutually exclusive origin and
retry branches. Python validators additionally enforce cross-field identities,
required-check completeness and result conclusions. Runtime evidence validation
is required before any mutation; JSON schema acceptance is not authorization.

All fields are required unless explicitly nullable. Evidence references are
relative to the protected mapped evidence root. Schema validation cannot replace
filesystem confinement, digest verification or original-material comparisons.
