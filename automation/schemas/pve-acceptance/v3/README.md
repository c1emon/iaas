# PVE acceptance v3 / snippet cleanup v2 schemas

The acceptance request/result/preview, snippet request/result and scoped execution-admission schemas are exported from
`iaas.pve_acceptance_contracts.contract_schemas()`. Shared accepted and rejected
examples live in `docs/examples/pve-acceptance/cases.json`; contract tests load
those exact files and check that these schema exports remain current.

Schemas establish structure, bounded values, and mutually exclusive origin and
retry branches. Python validators additionally enforce cross-field identities,
required-check completeness and result conclusions. Runtime evidence validation
is required before any mutation; JSON schema acceptance is not authorization.

Required fields are listed in each schema. General-template acceptance may also
select `temporary_vm.disk_size_gib` and `temporary_vm.nameservers`; these optional
fields enable root growth and actual guest network/DNS verification. Evidence references are
relative to the protected mapped evidence root. Schema validation cannot replace
filesystem confinement, digest verification or original-material comparisons.
