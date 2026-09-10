## Context

The repository audit expands this change with a prerequisite repair phase. The
repair decisions, concrete regression cases and deferred improvements are specified
in [repair-plan.md](repair-plan.md). That phase must pass before dependency refresh
or implementation of the new OPNsense capabilities described below.

`_validate_alias` currently permits only `host/network/port` and six required fields.
`manage-aliases.yml` runs this validator before credential preflight and delegates to
`oxlorg.opnsense.alias_multi`. The installed Collection supports `urltable`,
`networkgroup` and `updatefreq_days`, but that does not make them supported runtime inputs.
The validator is called through the `VALIDATORS` dispatch table; GitNexus reports
UNKNOWN for its incoming callers, corroborated by this direct source path.

Existing gateways require `default_gw: false`. Existing PBR uses API-backed new rules,
`scope/slug` identity, source/destination fields, optional gateway and logging.
`readonly.yml` and `export.yml` query configured aliases; neither proves live table
contents, a rule hit or a connection's complete network path.

## Goals and non-goals

Deliver reusable resource primitives and observation, independent of any application.
Names, URLs, addresses, gateway choices, ordering, routing exceptions and behavior on
next-hop failure come from caller-owned configuration. Do not infer policy from alias
names, countries or installed applications. Do not modify `ciop` or any live device.

Retain the current mutation entrypoints, secret injection boundary, OPNsense TLS settings
and unlisted-object preservation. Foundation HTTPS verification defaults and handoff
address verification are repaired explicitly. No global reconciliation, provider abstraction framework,
continuous monitoring service, complete audit trail or new qualification system.

## Dependency refresh

Use the dated candidate set and separate implementation commit described in
[dependency-review.md](dependency-review.md). Upgrade Ansible/core together and align
shared Collection manifests. Preserve the pinned OPNsense Collection and validate the
rebuilt dependency layer before layering the feature code; no new image publication.
The repair phase first aligns the main CI gate with the currently shipped tool and
Collection baseline; the later dependency refresh updates that baseline coherently.

## Alias schema and lifecycle

Retain required `name/type/content/description/enabled/state` fields and exact type
checking. No silently coerced booleans, discarded keys or automatic source rewrites.

| Type | Content | Additional fields |
| --- | --- | --- |
| host/network/port | Existing supported values unchanged | None |
| urltable | Nonempty list of absolute HTTP(S) URLs | `updatefreq_days`: required for present aliases; optional for absent aliases |
| networkgroup | Nonempty list of alias names | None |

`updatefreq_days` is a quoted decimal number of days: an integer or at most one
fractional digit, minimum 0.1 (for example `"1"`, `"1.0"`, `"0.5"`). Reject whitespace,
signs, exponent notation, NaN/infinity and parsed numeric/boolean values. The numeric
value must survive the pinned Collection's float conversion and one-decimal rounding
unchanged and finite; validate using Decimal comparison before any API access. Reject,
rather than round, `"0.01"` or `"0.15"`. The Collection's `build_updatefreq` actually
maps these to 0.0 and 0.1, respectively. Reject this field on other types. Preserve the existing complete-record shape for `state: absent`.
Validate names against both the existing length limit and the pinned provider's accepted
alias syntax before API access; do not broaden the existing type set beyond these five.

URL sources are caller-selected. Reject embedded userinfo and fragments; v1 does not
add URL authentication fields, arbitrary headers, JSON extraction or another alias type.
URLs are non-secret configuration; credentials must not be embedded in query parameters.
Offline validation checks syntax, not reachability or contents. OPNsense owns periodic
fetch/refresh. IaaS does not download, curate, merge, cache or re-host the lists.
Changing alias configuration does not prove successful URL refresh or table loading.

For every record, validate declared field shape and syntax, including member names.
Validate references against the desired graph of surviving (`present`) groups: reject
duplicate members, self-reference, cycles, local absent members and local non-address
members (ports). Existence/type/cycle requirements do not apply to obsolete content of
an absent group. An already absent object is an idempotent no-op, not a missing-reference
error. Retain the existing complete-record shape, but do not require deleting callers
to reconstruct a live dependency from obsolete YAML content.

Present local references may target present host/network/urltable/networkgroup aliases.
Unknown names are unresolved external references. Read live alias definitions before
writes; overlay local desired present definitions and planned removals onto live
externally owned definitions, then traverse only dependencies reachable from surviving
managed groups. Resolve existence, address-compatible types and cycles in that effective
graph, rather than mixing stale live definitions with desired replacements. Missing,
incompatible or unreadable external dependencies fail before writes. Do not adopt or
modify external aliases. Unsupported external dependency syntax must fail explicitly.

Apply present dependencies before dependent groups, irrespective of YAML order. Apply
updates which release old references before removals. Order absent groups/members using
the existing live dependency graph, dependents first; absent YAML content is not an
ordering authority. Thus a group and its member can both be deleted, and a surviving
group can switch members before the old member is deleted. Reject a deletion still
referenced in the effective graph of surviving managed groups.

Do not promise a complete preflight of all external consumers. The pinned Collection
and OPNsense deletion API retain the final in-use guard (including API error responses); a server refusal fails the
operation without deleting consumers, purging unrelated objects or disabling that guard.
`alias_util/findReferences` looks up IP use in rules and is not a complete alias
consumer graph. External changes between read and write can still cause refusal.

Reuse the Collection and use dependency batches when its bulk module cannot create and
reference a new alias in one call. Explicitly disable per-batch reload and reload alias
tables once after successful actual changes; ordinary no-op runs do not reload. An
explicit `opnsense_force_reload=true` recovery invocation may activate the fixed alias
target after successful admission/reconciliation even when no CRUD changes occur,
using the repair phase's activation contract. Check mode never activates. Type changes for
an existing name fail before writes and require a caller-planned migration: never
silently delete/recreate to change a type. Preserve unrelated objects.
This workflow is not transactional: report partial configuration changes on failure and
require explicit operator recovery, without claiming rollback or reloading as a success.

## Gateway and PBR integration

No new application routing model or second gateway/rule implementation is needed.
Callers reference aliases in existing rule fields and supply a gateway if appropriate.
Regression examples exercise a generic source alias, a destination group, optional
inversion, explicit sequence, gateway and log settings. Existing `scope/slug` identity,
non-default gateway restriction and unlisted-object preservation remain unchanged.
Cross-domain application policy (including default behavior on failures) is not inferred.

## Read-only diagnostic interface

Add `make opnsense-diagnose` and a direct `diagnostics.yml` playbook, sharing request
validation. Use the selected environment Ansible inventory and existing caller-injected
API credentials. Require an explicit target host and `OPNSENSE_DIAGNOSTICS_REQUEST`
absolute path; use `OPNSENSE_TARGET` as an exact inventory host name, not an Ansible
pattern. The Make target passes the same host as `opnsense_diagnostics_target` to the
direct playbook. Assert exactly one selected host in the `opnsense` group before API
access; an omitted or wildcard limit must not silently expand scope. The direct playbook
uses `opnsense_diagnostics_request` for the same request file. Extend the runtime
entrypoint's exact operation allowlist and Make help; adding a Make target alone does
not expose it through the OCI entrypoint. The direct playbook must validate selection
in a controller-local admission play before device plays: an assertion inside a device
play alone cannot reject zero matches, because that play would be skipped.

Request schema version 1 contains one operation. Required keys are `schema_version: 1`
and `kind`; selectors use `alias_name`, a `rule` mapping (`scope` plus `slug`, or `uuid`),
`source_ip`, `destination_ip`, and optional `protocol`, `source_port`, `destination_port`,
`interface`, `since`, `until`. `limit` and `include_details` are common optional fields.
`include_details` defaults to false. Rule identity and IP selectors can be combined with
AND semantics; require both scope and slug and forbid mixing those with UUID. Address
selectors are literal IPv4/IPv6 addresses, not hostnames or CIDRs. Require TCP/UDP for port
selectors; bounded UTC RFC3339 time selectors apply only to logs and must be ordered.
Alias requests accept only alias_name and common fields; state requests do not accept
rule, interface or time selectors in v1. Reject unknown or kind-inappropriate fields.

The operation requirements are:

| `kind` | Required selector | Optional selectors |
| --- | --- | --- |
| alias | Exact alias name | Entry details |
| rule_logs | Managed `scope/slug`, API rule UUID, or source/destination IP | Protocol/ports, interface, bounded time window where supported |
| states | Source or destination IP | Protocol and ports |

Reject conflicting rule identifiers, invalid addresses/ports, unknown keys and unscoped
requests before credentials or network access. `limit` defaults to 100 and must be an
integer in 1..1000. Bound response bytes, API timeouts and pagination as well as returned
rows; report truncation rather than silently claiming complete results. A finite query
is required: no unbounded log streaming. If the API cannot apply a selector, bounded
local filtering is allowed with explicit coverage/truncation metadata.

Return a versioned JSON result with target, observation time, operation, selector,
status, counts, truncation and available observation metadata. Distinguish:

- `ok`: query succeeded, including zero matching log/state records;
- `unsupported`: required endpoint/response capability is unavailable;
- `error`: authentication, permission, transport or malformed-response failure.
Unsupported/error exits nonzero; neither becomes an empty successful response.
Classify required capabilities by the actual selectors, not by every possible result
field. A rule-filtered request requires an unambiguous identity-to-log mapping; missing
mapping returns unsupported with no match count, not ok/zero. A nonexistent selected
alias/rule is an error; duplicate identity matches are an error. IP-filtered requests
can succeed without rule correlation, exposing it as unavailable. Missing fields needed
to evaluate any supplied selector make the result unsupported, not a silent filter drop.
Invalid JSON/response shape remains error rather than unsupported.

Counts on unsupported/error results are null, not zero. Optional timestamps, counters,
translation and route metadata may be null with a reason in otherwise successful
results; missing them does not invalidate an independently evaluable selector. Report
observation availability separately from API success when the upstream API cannot
distinguish a backend failure from an empty result. No adapter can promise distinctions
that the upstream response does not encode. When the required observation is ambiguous,
return `unsupported` with nonzero exit, an observation-unavailable reason, observation
availability unknown and match/count observations null; retain independently verified
configuration metadata without claiming observed-empty tables or absence of traffic.
For the pinned baseline, query_states fallback
`current: 0` is not a successful requested page (pages start at 1).

Alias observation separates configured entries from loaded table entries and exposes
available entry counts/update time. An empty loaded table is an observation, not proof
of refresh success. Rule logs identify matched records when the API supplies an
unambiguous rule mapping; otherwise explicitly report unavailable correlation. Do not
enable logging, generate traffic or reset counters to obtain evidence. State observation
shows available tuple/interface/translation/route information without inferring absent
fields or claiming a complete end-to-end path. Existing state may predate a rule change.

Default console output is a safe summary, without raw logs, state rows, table contents,
credentials or full URLs. Detailed rows require explicit opt-in and a file beneath
`OUTPUT_DIR/runtime/opnsense-diagnostics/`, directory mode 0700 and file mode 0600,
using existing path-safety helpers and refusing unsafe links/paths before API access.
When `include_details` is true, require the absolute `OPNSENSE_DIAGNOSTICS_OUTPUT`
Make input, mapped to `opnsense_diagnostics_output` for direct Ansible. Missing or
out-of-root paths fail before API access. The output must not overlap the request,
inventory, authored inputs or implementation, even if those inputs happen to be beneath
the allowed output root. With details disabled no detail file is written; an explicit
detail-output path without opt-in is rejected. This parameter is not a request field
and cannot enable details by itself.
No tracked artifacts, global temp dump, arbitrary endpoint/HTTP method or shell fallback.
POST may be used for a documented read-only query; HTTP method alone does not prove
read-only semantics. Never flush/update an alias, reload rules, kill states or capture
packets from a diagnostic entrypoint. Keep diagnostics outside `make check`.

## Adapter and compatibility evidence

Reuse Collection APIs where their output matches the contract. Otherwise add a narrow
read-only adapter with fixed endpoint operations and existing credential/TLS conventions.
Candidate official resources are alias configuration/alias_util list, rule identity
lookup, diagnostics firewall log and query_states. Before implementation is called
complete, verify method, request shape, response fields, permissions and boundedness
against a documented pinned upstream version and representative response fixtures.
Do not infer API availability solely from documentation for a newer appliance.
Use OPNsense core tag `26.1.11` as the initial source/fixture baseline (not an installed
appliance claim). Its log endpoint supports `limit/digest`, not server-side IP/rule/time
filters: fetch a bounded recent sample and filter locally, reporting examined records
and sample/time coverage; do not promise a historical log search. Its query_states uses
`rowCount/current/searchPhrase/ruleid`; local exact tuple filtering must avoid substring
or translated/original-address confusion. Define source/destination selectors over the
API's returned src_addr/dst_addr fields; expose translation as separate optional metadata.
Consult the pinned controller and backend schemas before finalizing fixtures/ACL docs.

All three diagnostic kinds must be implemented and covered; an unsupported response is
a compatibility outcome, not a substitute for implementing that kind.

## Validation and rollout

Use synthetic fixtures and standard grouped tests: accepted types, type-specific bad
inputs, local/external dependencies and cycles, ordering and unlisted preservation;
mock APIs prove that invalid input has no network access and read-only diagnostics never
call mutations. Cover empty, paginated/truncated, unavailable metadata, 401/403, missing
endpoint, timeout, malformed payload and ambiguous rule correlation with representative
cases, not an exhaustive version/object matrix.

Complete tasks 0.1–0.15 and record the repair gate before tasks 1–5. Repair tests must
exercise real orchestration with safe command/API substitutes and realistic installed,
partial and failed-activation states; all-green fabricated facts are not sufficient.
Run targeted Python tests, Ansible syntax/lint and the existing synthetic offline gate;
ensure the new entrypoint is available in the image without changing dependency layers
for source-only edits. Update current operator docs and examples. Software-only evidence
is sufficient for implementation acceptance, but cannot claim a real appliance was
configured, lists loaded or traffic followed a chosen path. Live validation is separately
authorized for a specific appliance/version when an environment adopts the capability.

## Sources

Inspected 2026-09-10: repository validator/playbooks and pinned Collection sources;
[alias types and native refresh](https://docs.opnsense.org/manual/aliases.html),
[firewall API resources](https://docs.opnsense.org/development/api/core/firewall.html),
[diagnostics API resources](https://docs.opnsense.org/development/api/core/diagnostics.html).
These describe candidate primitives, not qualification of the user's appliance.

Pinned source references used during design review:
- [Collection frequency conversion](https://github.com/O-X-L/ansible-opnsense/blob/26.1.11/plugins/module_utils/helper/alias.py)
- [Alias deletion and metadata](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/AliasController.php)
- [Alias table query and IP reference lookup](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/AliasUtilController.php)
- [Log/state queries and fallback shapes](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/mvc/app/controllers/OPNsense/Diagnostics/Api/FirewallController.php)
