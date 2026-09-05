## Context

The IaaS repository owns VM and K3s lifecycle. The selected target architecture
places shared in-cluster components and day-to-day reconciliation in a separate
platform repository. The missing piece is a narrow handoff contract between
those ownership domains.

The handoff must distinguish three things:

1. non-secret cluster identity and trust metadata;
2. a reference to temporary cluster bootstrap access;
3. the platform repository location that will become the desired-state owner.

The handoff does not make the IaaS repository an orchestrator for another
repository and does not prove that the platform layer is operational.

## Goals / Non-Goals

**Goals:**

- Define one deterministic non-secret handoff bundle.
- Compose cluster fields from the validated K3s model rather than duplicating
  VM or cluster facts.
- Require existing K3s verification for the exact cluster and scope before an
  online bundle is emitted.
- Bind the bundle to an API CA fingerprint derived from the authoritative K3s
  server CA and an explicit platform repository URL, revision, and relative
  path.
- Keep bootstrap credentials in an external secret system and make temporary
  cluster-side credential invalidation part of the consumer contract.

**Non-Goals:**

- Installing or configuring Flux, Cilium, CSI, Gateway, certificates,
  observability, or applications.
- Triggering platform-repository CI or waiting for platform reconciliation.
- Creating, exporting, copying, rotating, or revoking a real kubeconfig or
  cluster-admin credential from this repository.
- Defining the platform repository's internal layout beyond one explicit
  revision and relative entry path.
- Deploying or qualifying a real Astra K3s or platform environment.

## Decisions

### Transfer a contract, not platform resources

The IaaS side produces a handoff bundle only after read-only K3s verification.
The platform side consumes that bundle and performs bootstrap using its own
workflow:

```text
validated K3s model + explicit platform handoff intent
  -> same-model/same-scope K3s verification
  -> read authoritative CA from the declared initial K3s server
  -> verify API endpoint TLS against that CA and derive its SHA-256 fingerprint
  -> render protected non-secret handoff bundle
  -> operator supplies bundle to the platform workflow
  -> platform repository CI resolves temporary bootstrap credential
  -> platform repository checks credential endpoint/CA against the bundle
  -> platform repository installs Flux and verifies first reconciliation
  -> bootstrap credential is revoked outside the IaaS repository
```

The IaaS repository SHALL NOT call the platform pipeline, apply the platform
repository, or infer that successful bundle generation means platform handoff
has completed.

### Keep handoff intent policy-only

The handoff intent declares only:

- an explicit external platform repository URL;
- an explicit revision with no implicit default branch;
- a normalized repository-relative entry path;
- an external reference for temporary cluster bootstrap access.

Cluster name, exact K3s version, API endpoint, and declared node scope are
derived from the validated K3s model and explicit operation scope. The API
endpoint is rendered as a normalized HTTPS URL on port 6443, with IPv6 literals
enclosed in brackets. Repository
URL schemes are limited to `https` and `ssh`; URLs contain no password, token,
query, or fragment, and HTTPS URLs contain no user information. The path is
normalized and repository-relative. The external bootstrap-access
reference uses the repository's recognized secret-reference syntax, but the
IaaS workflow never resolves it or contacts a secret provider. The intent
rejects copied node addresses, VM references, architecture, PVE facts, tokens,
kubeconfig content, repository credentials, private keys, and arbitrary
Kubernetes manifests.

### Anchor endpoint identity in the authoritative K3s server CA

The online action reads
`/var/lib/rancher/k3s/server/tls/server-ca.crt` from the single declared initial
server through the existing authenticated guest-access path. It accepts one
X.509 CA certificate, computes the SHA-256 fingerprint over its DER-encoded
bytes, renders it as `sha256:<lowercase-hex>`, and uses that certificate as the
trust anchor for the declared API endpoint, including endpoint-name validation.
A fingerprint
learned only from the API endpoint is insufficient and SHALL NOT be accepted as
proof of endpoint identity.

The platform consumer independently compares the CA identity carried by its
resolved temporary access with the handoff fingerprint before using that
access. The reference identifies an independently revocable temporary grant,
not a shared long-lived administrator identity. Consumer revocation must make
that grant unable to authenticate to the cluster; deleting only the
secret-provider value is insufficient. The IaaS side does not resolve, inspect,
create, or revoke that credential.

### Render a deterministic protected operator artifact

The rendered bundle contains:

- schema version and cluster name;
- exact K3s version and normalized HTTPS API endpoint on port 6443;
- an explicit `whole-cluster` scope class, without VM or node references;
- authoritative K3s server CA SHA-256 fingerprint;
- platform repository URL, revision, and path;
- the external bootstrap-credential reference;
- an explicit statement that platform reconciliation is not yet qualified.

The bundle is written only to an explicitly selected operator path with
restrictive permissions. It is not emitted under committed environment or
generated inventory paths, and ordinary output reports only its path and
non-sensitive identity. The IaaS workflow does not resolve the external
bootstrap credential, and tests prove no secret-provider lookup occurs.

### Keep safety classes explicit

`platform-handoff-check` requires explicit K3s intent, generated inventory,
platform handoff intent, and whole-cluster scope, then validates intent and
composition offline without requiring an output path. A separate
`platform-handoff-render` requires those same inputs plus an explicit output
path. It reuses K3s verification and performs only read operations against the
cluster plus a local protected artifact write. It is therefore
infrastructure-read-only with an explicit local artifact-write side effect.
Neither command is included in the aggregate offline gate as an implicit
online action.

Missing, partial, mismatched, unreachable, unverified, or CA-untrusted input
fails before bundle output. A pre-existing output is replaced atomically only
after all checks succeed.

### Move platform implementation ownership out of this repository

`platform/` remains only a boundary document and MAY contain schemas or
examples needed to explain the handoff contract. It SHALL NOT become an
in-cluster desired-state root. The external platform repository owns Flux and
shared cluster services; application repositories own ordinary application
release content.

The operator explicitly supplies the rendered bundle as an input to the
external platform workflow. Bundle transport, publication, signing, CI
triggering, and external workflow implementation are not defined or qualified
by this change.

Alternative considered: keep platform components under this repository's
`platform/` directory. Rejected because platform reconciliation and IaaS/cluster
lifecycle have different release cadence, access control, and rollback paths.

## Risks / Trade-offs

- [The bundle is mistaken for completed platform bootstrap] -> Render an
  explicit unqualified status and document that the platform repository must
  separately verify Flux reconciliation.
- [A stale bundle targets a rebuilt cluster] -> Bind it to the authoritative
  K3s server CA fingerprint and require a new handoff action after cluster
  identity changes.
- [Temporary cluster-admin access persists] -> Put only its external reference
  in the bundle, require an independently revocable grant, and require
  platform-side cluster authentication invalidation after bootstrap; automated
  credential lifecycle remains a separate change.
- [Repository coordinates drift] -> Require URL, revision, and path explicitly;
  do not default to a branch or directory.
- [Cross-repository automation expands scope] -> Do not invoke external CI or
  add platform manifests in this change.

## Migration Plan

1. Revise the repository ownership contract and synchronize `README.md`,
   `docs/README.md`, `docs/k3s-foundation-platform-design.md`, and
   `platform/README.md` with the three-way IaaS/platform/application ownership
   model. The existing `iaas-repository-layering` Purpose is updated directly
   to neutral platform-ownership wording that remains consistent before and
   after archive, as required by OpenSpec for an existing capability.
2. Add synthetic handoff intent and expected-bundle fixtures.
3. Add offline composition validation and deterministic redacted rendering.
4. Add the same-model/same-scope read-only verification and authoritative CA
   fingerprint boundary.
5. Add explicit command entrypoints and operator documentation for the external
   platform consumer.
6. Run offline validation and archive the capability without contacting a real
   cluster; a later environment change supplies actual repository coordinates
   and bootstrap credential references.
