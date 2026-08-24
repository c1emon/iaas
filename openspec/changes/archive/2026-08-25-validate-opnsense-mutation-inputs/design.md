## Context

The four supported OPNsense mutation playbooks load separate hand-written YAML files and implement different Ansible assertions. Those assertions cover some required fields and safety rules, but do not consistently reject unknown keys, strict type errors, malformed ports/networks, or duplicate module identities. They also currently run after API credential preflight.

The DNAT playbook is different: it is a deliberate placeholder that validates only its top-level list and then always fails before any API write. It is not a mutation path for this design.

GitNexus does not derive a useful call graph from these Ansible task files, so the authoritative flow was confirmed from source: `include_vars` → credential preflight → resource assertions → mutation module → conditional reload.

## Goals / Non-Goals

**Goals:**

- Give all supported OPNsense mutation inputs one consistent offline validation boundary.
- Reuse the same validator from the root command and direct playbook paths.
- Reject ambiguous or unsupported local input without coercion and before secrets/network access.
- Preserve existing accepted repository data and resource-specific safety constraints.
- Keep validation errors stable, field-oriented, and safe for CI logs.

**Non-Goals:**

- Do not query OPNsense to prove that interfaces, aliases, gateways, or other references exist.
- Do not normalize exports into apply input or generate desired state.
- Do not enable DNAT, purge unmanaged objects, expand resource ownership, or change apply identity.
- Do not replace collection-side argument validation or claim that offline success proves a safe live apply.

## Decisions

### Use a small Python validation package as the canonical implementation

Add a package under `scripts/opnsense_validation/` with a CLI, document loader, resource validators, and shared error model. Reuse the existing uv/PyYAML environment and common repository error conventions. Unit tests should call the validation functions directly; CLI tests should cover exit and redaction behavior.

Alternative considered: expand each playbook's Jinja assertions. This avoids a Python entrypoint but duplicates shape logic, makes strict type and IP/port validation awkward, and leaves aggregate offline validation without a reusable interface.

Alternative considered: add JSON Schema. Schema handles shape well but custom Python is still needed for module match identities, IP-family agreement, threshold ordering, port ranges, and the filter-rule self-interface deny guard. A second schema layer would increase drift for this small repository.

### Keep an explicit resource registry and exact key sets

The validator should map each supported resource kind to its source file, top-level variable, required keys, optional keys, and validation function. Unknown top-level and record keys fail closed. Collection argument aliases are not accepted in repository YAML unless the repository contract explicitly declares them.

The first version validates the repository-owned subset, not every field supported by `oxlorg.opnsense`:

| Resource | Local identity | Key validation focus |
|---|---|---|
| Alias | `name` | managed alias type/state, list content, strict enabled boolean, type-aware host/network/port values |
| IP Alias VIP | collection match tuple `(address, interface)` | IP-with-prefix, interface token syntax, bind/expand booleans, present/absent |
| PBR gateway | collection match tuple `(name, gateway)` | inet/inet6 address agreement, strict flags, numeric bounds/order, `default_gw: false` |
| New filter rule | generated `iaas:opnsense:filter:<scope>:<slug>` | exact fields, enums, interfaces, net/port scalar-or-list tokens, booleans, sequence, existing deny/self-interface guard |

IP/network parsing should use the standard library `ipaddress` module. Port validation should accept the contracted scalar-or-list forms and distinguish numbers, inclusive ranges, and symbolic aliases; numeric endpoints must be within 1–65535 and range start must not exceed range end. Symbolic tokens receive syntax validation only.

Interface, alias, and gateway names receive conservative local syntax checks. The validator must not reject a syntactically valid custom object merely because it is absent from another local file: OPNsense built-ins and externally managed objects can be legitimate references.

### Add one offline target and make it part of the aggregate gate

`make opnsense-validate` should run the CLI in all-resources mode. The root `check` target should depend on it so developer and cloud-CI behavior stays identical and credential-free.

The CLI supports a resource/file-scoped mode for playbooks but must use the same validation functions and rules as all-resources mode. It reads only the explicit repository-owned source path; it does not scan exports, environment files, or credentials.

### Enforce validation inside every supported mutation playbook

Each playbook should invoke the resource-scoped CLI on the controller immediately before loading/using desired variables and before credential preflight. The task must run in Ansible check mode, report `changed: false`, and stop the play on non-zero exit. Existing Ansible assertions may remain as defense in depth until they become demonstrably redundant.

The initial ordering is:

```text
shared local validation
  -> load desired variables
  -> API credential preflight
  -> existing resource safety assertions/normalization
  -> mutation module
  -> conditional reload
```

Alternative considered: validate only in `make check`. That would allow operators invoking a playbook directly to bypass the gate, so it is rejected.

There is a narrow local file time-of-check/time-of-use window between CLI validation and `include_vars`. The playbooks are single-operator, local-control workflows and do not support concurrent desired-state edits during execution. The implementation should document that assumption and keep the steps adjacent; content digest binding would add complexity disproportionate to this local workflow.

### Fail with paths, not payload dumps

Expected validation errors should use a stable shape such as `opnsense validation failed: filter_rules[2].destination_port: port 70000 is outside 1..65535`. Errors may include a non-sensitive identity when available but must not dump the entire record or any environment value. Expected errors exit `1` without traceback; unexpected internal errors may retain a distinct non-zero exit for diagnosis while still avoiding secret output.

## Risks / Trade-offs

- [Repository schema drifts from the pinned collection] → Test the repository-owned field subset and review validator changes together with collection-version changes.
- [Offline syntax accepts a reference missing on the appliance] → State this boundary explicitly and rely on the credentialed module/apply path for live resolution.
- [Validation becomes stricter than current data] → Add acceptance tests for every committed desired-state file before wiring the aggregate gate.
- [Direct playbook invocation uses a modified file after validation] → Keep validation and `include_vars` adjacent and document that concurrent source edits during a run are unsupported.
- [Duplicate assertions drift] → Treat Python as canonical, retain only high-value in-play guards, and test that every mutation playbook invokes the canonical gate before credentials.

## Migration Plan

1. Implement validators and unit/CLI tests while leaving mutation playbooks unchanged.
2. Prove all committed supported desired-state files pass.
3. Add `make opnsense-validate`, then include it in `make check`.
4. Wire the resource-scoped validator into all four mutation playbooks before credential preflight and add ordering tests.
5. Update operator documentation and run the full offline gate.

Rollback removes the playbook calls and Make dependency together with the validator. It does not require infrastructure rollback because this change performs no OPNsense mutation by itself.
