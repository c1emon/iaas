# Prerequisite runtime repairs — 2026-09-10

The repository audit and three independent agent reviews identified the following
repair scope. These are planned requirements, not implemented fixes. All task
checkboxes remain open. Keep this phase separate from the dependency upgrade and
new OPNsense functionality, while retaining one change for coordinated review.

## Sequence and acceptance

1. Complete tasks 0.1–0.14 on the currently shipped dependency baseline.
2. Pass 0.15 and record the repaired caller paths and representative regression
   evidence in focused repair commits. A known blocking repair prevents feature work.
3. Refresh the reviewed dependencies in tasks 1.1–1.2 and verify the final image.
4. Implement URL tables, network groups and bounded diagnostics in tasks 2–5.

Implementation must use the implementation branch selected under AGENTS.md. Current
uncommitted design work must be preserved. No infrastructure access, external writes,
release publication or environment migration is required for software acceptance.

## Audit coverage

| ID | Confirmed issue | Task / capability | Representative acceptance |
| --- | --- | --- | --- |
| R01 | Recursive Make loses the selected Makefile outside the checkout | 0.1 / oci-runtime-delivery | Repository-external plan/apply/destroy orchestration finds its own targets |
| R02 | Parallel Make races cloud-init phases | 0.1 / pve-automation-foundation | Delayed command substitutes preserve render/upload/verify/apply order |
| R03 | Upload/verify ignore their tfvars input | 0.2 / pve-automation-foundation | Missing or different source fails before any SSH call |
| R04 | Storage resolution failure falls back to a guessed host path | 0.3 / pve-automation-foundation | Failing pvesm performs no mkdir/install |
| R05 | Upgrade and deployment re-entry use fresh-install-only admission | 0.4 / k3s-automation-operations | Installed and supported partial states pass the relevant gate; foreign state fails |
| R06 | Download failure occurs after service stop | 0.5 / k3s-automation-operations | Download/checksum failure leaves service and active binary unchanged |
| R07 | K3s facts and upgrade success do not prove actual state | 0.6 / k3s-automation-operations | Zero capability bits, wrong interface/IP, stale versions and stale Node registration fail |
| R08 | Handoff validates IP SAN as DNS and formats IPv6 incorrectly | 0.7 / platform-gitops-handoff | Correct DNS/IPv4/IPv6 identities pass; wrong SAN or CA fails |
| R09 | Saved OPNsense changes cannot reliably reactivate on a no-change retry | 0.8 / alias, gateway, VIP and filter-rule management | Failed activation followed by explicit no-change recovery actually reloads |
| R10 | Gateway bounds drift and inverted destinations are misclassified | 0.9 / opnsense-mutation-input-validation and filter-rule management | Invalid second item blocks the whole batch before writes; valid inversion is preserved |
| R11 | Switch plan details never reach an operator | 0.10 / xikeos-network-resources-primary | Sanitized object changes are visible; optional detailed file is protected |
| R12 | Multi-target OPNsense exports overwrite each other | 0.10 / opnsense-config-export | Two synthetic targets produce separate attributed artifacts |
| R13 | Recovery cycles and inverted restore order are accepted | 0.11 / foundation-recovery-checks | Self/cyclic/reverse-order dependencies fail before rendering |
| R14 | Generic schemas embed TrueNAS, fixed storage phases and a mirror provider | 0.12 / foundation-recovery-checks and k3s-automation-operations | Foundation data without storage/K3s policy and arbitrary pinned artifact hosts work |
| R15 | Foundation probes skip HTTPS identity, choose public DNS and incompletely/unboundedly parse DNS | 0.13 / foundation-recovery-checks | Wrong CA, absent resolver, TXT/SRV, malformed packets and pointer cycles have truthful bounded outcomes |
| R16 | Main CI tests a drifting stack and unrealistic lifecycle facts | 0.14 / oci-runtime-delivery | Gate uses shipped pins and exercises repaired orchestration with safe substitutes |

## PVE execution and artifacts

Keep the Make facade and existing Python/OpenTofu responsibilities. Carry the selected
absolute Makefile into recursive calls. Express render, upload, verification and apply
as an ordered workflow even when the caller enables parallel Make. Failed phases stop
dependent phases. Check generated-input freshness before lifecycle planning/apply;
do not silently regenerate authored inputs or read live devices during offline checks.

Use the existing manifest source hash to compare the explicit current tfvars bytes
before upload/verify. Keep per-file checksums; no second manifest/signature system.
This protects artifact continuity but does not make a workflow transactional or lock
caller-owned files against concurrent edits. Callers serialize runs sharing a working
root/output directory. Storage resolution must come from PVE, not a guessed path;
failure occurs before mkdir/install. Existing storage permissions remain separately
reviewed and must not be weakened as part of this repair.

## K3s lifecycle and observations

Reuse shared read-only probes with operation-aware evaluation. Standalone preflight
requires `K3S_PREFLIGHT_MODE=install|converge|upgrade`, mapped to the same
`k3s_preflight_mode` in direct Ansible use. Missing/unknown standalone modes fail
before credential or host access. Deploy selects convergence admission (which also
accepts fresh hosts); upgrade selects upgrade admission. These workflows must not
accept an override that bypasses their operation's policy. Expected
installed binaries/listeners are valid for upgrade and declared-state convergence.
Deployment may resume a supported state produced by this runtime, including an
acquired exact artifact before configuration/start; reject foreign, incompatible or
ambiguous state before mutation. Do not silently use deploy to bypass version upgrade
rules. Preserve whole-cluster scope, stable token checks and external-CNI boundaries.

| Observed state | Install | Converge/deploy | Upgrade |
| --- | --- | --- | --- |
| No K3s binary, managed unit/config or datastore | Allow with required ports free | Allow fresh deployment | Reject missing installation |
| Exact declared artifact only, no conflicting unit/config/datastore | Reject existing partial install | Allow supported re-entry | Reject incomplete installation |
| Declared managed installation at the intent version | Reject existing installation | Verify and converge, unchanged state is a no-op | Health-verify exact-target skip |
| Declared managed installation at a supported prior version | Reject | Reject and direct to upgrade | Apply existing prior/target transition rules |
| Foreign, ambiguous or incompatible unit/config/datastore | Reject | Reject | Reject |

The existing units/configuration, artifact checksum and readable cluster/node facts
establish these representative states; no new ownership database is introduced.
Presence of a binary alone never proves ownership or authorizes overwriting a datastore.

Parse capabilities and exact address/interface ownership rather than copying expected
values into observations. Missing/malformed/unreachable required facts cannot pass
mutation admission. Refresh actual node versions before the first upgrade mutation;
compare with supplied observations and reject drift before stopping a service. After
each node, require the exact node identity, target version and role-appropriate health,
including node readiness with only the existing explicit CNI-bootstrap exception.
Reuse staged verification at operation completion; old Node existence is insufficient.

Acquire to a node-local staging path and verify SHA-256 before stopping the service.
Check the staged binary's reported exact version before activation; a URL's path alone
does not prove version. Keep serial server-before-agent ordering and the existing
pre-upgrade snapshot. A download failure leaves active files/services unchanged. An
activation failure stops later nodes and reports node/phase plus the retained artifact
and manual recovery boundary. A stop failure must not replace the binary. Restoration
of the unchanged old service before binary activation may be bounded; never perform an
implicit version downgrade, etcd restore or datastore rollback after activating a new
version. Verify readiness with a finite retry budget, respecting systemd Type=notify.

Artifact hosts and path conventions are caller-owned. Accept a safe explicit HTTPS
URL plus exact version/checksum without a Rancher-specific URL exception. Preserve
existing secret/proxy and redirect safety; preflight cannot claim version proof from
URL syntax. This does not add artifact hosting, authentication schemes or OS support.

## Network admission, activation and output

For alias/gateway/VIP/filter-rule playbooks add an explicit boolean
`opnsense_force_reload`, default false. After successful admission and reconciliation,
reload the fixed resource target once when changes occurred or force was requested.
Disable automatic per-item/per-batch Collection reload explicitly. Validate the force
flag without permissive string truthiness; document JSON/YAML boolean extra-vars.
An ordinary no-op still does not reload. Check mode never activates configuration.
Failed CRUD never auto-activates a partial batch as success. Failed reload returns
nonzero, distinguishes saved changes from activation, and documents an explicit
same-target force retry; no automatic rollback or arbitrary reload target is added.
Diagnostics remain strictly read-only and cannot set this mutation option.

Validate each complete desired batch against current pinned Collection primitive
bounds before any write. Preserve non-default gateways and additive ownership.
Evaluate destination inversion semantically in both Python and Ansible paths; do not
remove existing management-access protections wholesale or choose routing policy.

Switch previews must expose a sanitized object-level difference summary rather than
only counts. Optional detailed reports use explicit protected output paths, 0700/0600
and existing path guards. OPNsense exports use a separate target subdirectory and
include target identity in artifact metadata, preserving read-only and non-applyable
export boundaries. Document the output-layout migration; multi-host operation is not
silently treated as single-host. No universal reporting framework is required.

## Foundation model and health

Add a neutral schema version 2 with required host/service declarations and optional
`storage_networks` and `storage_access` facts. Each declared storage network uses a
neutral `endpoint` field; access facts use explicit `node_classes` and referenced
`storage_networks`, without a fixed phase, VM-only policy or requirement to select all
networks. This records facts only and does not add bare-metal K3s deployment. Continue
reading schema version 1's field layout and storage scope through a small documented
adapter. New dependency correctness and probe-safety checks apply to both versions;
compatibility does not preserve accepted cycles, missing DNS resolvers or unverified
HTTPS. Document these validation changes as well as the schema migration. Do not
silently reinterpret legacy fields or rewrite caller files. Generated sections reflect only
declared facts. New generic fixtures/documentation use version 2.

Version 2 retains the existing host/service field shapes. Each optional storage-network
record has `name`, `subnet`, `endpoint`, optional `vlan_id` and `notes`; endpoint is an
IP address within the subnet and a provided VLAN ID is an integer in 1..4094. Optional
`storage_access` has `node_classes`, `storage_networks` and optional `notes`; node
classes are explicit `vm` and/or `bare-metal` values and network names resolve to
declared networks. Reject duplicates and unknown fields. No storage sections means no
storage policy, and no endpoint or VLAN is inferred. This does not expand service
deployment ownership beyond the existing runtime.

Reject unresolved references, self-dependencies, cycles and orders where a service
precedes its required dependency. Required-before-K3s services must include their
service dependency closure in that required set, or reference declared external
dependency hosts; external host references are leaves, not invented services. Where
both dependent services declare order values, a dependency must have a strictly lower
value. Keep required
restore order explicit, unique and dependency-consistent; YAML item order itself is
not policy. Reject ambiguous service/external-host reference collisions. Generate the
validated deterministic startup/recovery order and preserve accepted-risk metadata.

HTTPS probes use normal certificate/hostname validation and an optional caller-supplied
`health_check.ca_file` path, resolved from the selected inventory's directory when
relative and supplied by the caller; reject it on non-HTTPS probes. HTTPS may also be
the scheme of a generic API probe. No silent TLS skip; private CA failures are classified clearly. DNS requires
an explicit resolver and honors it; never choose a public service. Support the already
declared A/AAAA/CNAME/TXT/SRV/ANY records with documented value comparison, including
expected answers for TXT and SRV. Validate response identity/question and source;
bound name compression traversal and packet offsets, rejecting loops/truncation or
unsupported responses as failures without hanging. One service failure must not abort
classification of the remaining services. Preserve finite probe timeouts and safe
summaries; do not expose URL credentials or query secrets in error text.

## CI and minimal evidence

Update affected PVE, K3s, foundation, network, switch and OCI operator documentation,
help and synthetic fixtures in the repair phase, including changed inputs and export
layout. These cannot wait for the later OPNsense feature documentation task.

The main checkout gate uses the same OpenTofu/explicit Collection baseline as the
shipped image. A later exploratory upgrade job, if added separately, is not release
acceptance. Keep image dependency installs before repository source COPY. Run safe
substitutes through actual orchestration for the failure states above and existing
focused tests, then the normal offline gate and final-image smoke. No production
matrix, live deployment, checksum framework or complete rollback rehearsal is needed.

## Deferred improvements and corrected audit wording

- Saved OpenTofu plans are useful for future noninteractive approval integration, but
  current interactive apply still presents a new plan for confirmation. Optional
  saved-plan inputs are deferred and do not block the repair or feature phases.
- A single post-start probe is not proof of a startup race because server units use
  Type=notify. A bounded readiness check is a small reliability improvement, not a
  separately claimed reproduced outage.
- Keep known restore, off-node snapshot and live-qualification limitations explicit.
  None authorizes automated DR, workloads, new backends or application policy here.

## Evidence baseline

The audit used source review, temporary Make/SSH/API substitutes, installed-cluster
facts, IP-SAN certificates and pure metadata/parser examples. The two independent
K3s/network test groups passed 56 existing tests while the documented counterexamples
still failed. This is evidence for repair scope, not post-repair acceptance. Relevant
upstream semantics: [OpenSSL verification](https://docs.openssl.org/3.0/man1/openssl-verification-options/),
[OPNsense inversion](https://docs.opnsense.org/manual/firewall.html), and
[pinned gateway bounds](https://github.com/O-X-L/ansible-opnsense/blob/26.1.11/plugins/module_utils/main/gateway.py).
