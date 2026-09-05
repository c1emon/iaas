## Purpose

Define the verified, non-secret contract by which this IaaS repository hands a
bootstrap-ready K3s cluster to an independently operated platform repository.

## ADDED Requirements

### Requirement: Explicit non-secret platform handoff contract

The system SHALL compose an explicit platform-handoff intent with one validated
K3s model without duplicating VM, PVE, or K3s-owned facts.

#### Scenario: Operator defines a platform consumer

- **WHEN** an operator supplies a platform-handoff intent
- **THEN** it SHALL declare an explicit external repository URL, revision, repository-relative entry path, and external bootstrap-credential reference
- **AND** the repository URL scheme SHALL be `https` or `ssh`, SHALL contain no password, token, query, or fragment, and an HTTPS URL SHALL contain no user information
- **AND** the path SHALL be normalized and repository-relative, and the bootstrap-credential reference SHALL use recognized external-reference syntax
- **AND** cluster name, exact K3s version, normalized HTTPS API endpoint on port 6443, and whole-cluster scope SHALL derive from the validated K3s model and explicit whole-cluster operation scope
- **AND** an IPv6 literal in the normalized API endpoint SHALL be enclosed in brackets
- **AND** no repository URL, revision, path, cluster, environment, or scope SHALL be selected implicitly
- **AND** validation SHALL NOT contact a secret provider or resolve the bootstrap credential

#### Scenario: Handoff intent crosses an ownership boundary

- **WHEN** handoff intent contains a copied node address, VM reference, interface, architecture, PVE fact, K3s token, kubeconfig, private key, repository credential, resolved secret, or Kubernetes resource
- **THEN** validation SHALL fail before host access or bundle rendering
- **AND** the system SHALL NOT reinterpret that value as platform policy

### Requirement: Verified handoff readiness

The system SHALL produce an online handoff bundle only after read-only
verification of the same K3s model and explicit whole-cluster scope.

#### Scenario: Bootstrap-ready cluster is prepared for handoff

- **WHEN** the operator invokes online handoff rendering with all explicit inputs
- **THEN** the workflow SHALL rerun existing K3s API, node, role, version, embedded-etcd, and service verification for the same model and scope
- **AND** it SHALL read `/var/lib/rancher/k3s/server/tls/server-ca.crt` from the single declared initial server through the existing authenticated guest-access path and require exactly one valid X.509 CA certificate
- **AND** it SHALL validate the declared API endpoint TLS chain and endpoint identity against that CA, then render the SHA-256 of the DER-encoded CA certificate as `sha256:<lowercase-hex>`
- **AND** a fingerprint learned only from the API endpoint SHALL NOT be accepted as the identity trust anchor
- **AND** the expected external-CNI-not-initialized bootstrap state MAY remain explicitly unqualified while other readiness failures remain blocking
- **AND** these checks SHALL NOT change cluster, host, PVE, repository, or secret-provider state

#### Scenario: Handoff identity or readiness cannot be proven

- **WHEN** the scope is missing or partial, a host is unreachable, K3s verification fails, the endpoint identity differs, or the authoritative K3s server CA cannot be read and validated
- **THEN** the workflow SHALL fail before creating or replacing a handoff bundle
- **AND** it SHALL NOT claim that the platform repository can safely bootstrap

### Requirement: Deterministic protected handoff bundle

The system SHALL render a deterministic handoff bundle containing only the
minimum non-secret inputs required by the platform-repository consumer.

#### Scenario: Handoff bundle is rendered

- **WHEN** all handoff readiness gates succeed
- **THEN** the bundle SHALL contain its schema version, cluster name, exact K3s version, API endpoint, `whole-cluster` scope class, authoritative K3s server CA SHA-256 fingerprint, explicit platform repository URL/revision/path, and external bootstrap-credential reference
- **AND** it SHALL NOT contain VM references, node references, node addresses, architecture, or PVE facts
- **AND** it SHALL mark platform reconciliation as not yet qualified
- **AND** it SHALL be written atomically to an explicit operator path with restrictive permissions
- **AND** ordinary output SHALL contain only non-sensitive identity and path information

#### Scenario: Bootstrap credential reference is considered

- **WHEN** handoff validation or rendering encounters a bootstrap-credential reference
- **THEN** committed and rendered data SHALL contain only the validated external reference
- **AND** the IaaS workflow SHALL NOT contact a secret provider, resolve the reference, or inspect credential content
- **AND** credential values SHALL NOT enter CLI arguments, handoff output, inventory, Ansible facts/fact cache, generated environment state, diffs, temporary files, or logs

### Requirement: Handoff declares external platform ownership

The system SHALL stop the IaaS workflow at the verified handoff boundary and
SHALL declare that shared in-cluster platform desired-state ownership belongs
to the external platform repository while ordinary application release content
remains application-repository owned.

#### Scenario: Platform repository consumes the bundle

- **WHEN** the external platform workflow accepts a handoff bundle
- **THEN** an operator SHALL have supplied the bundle explicitly as an input to that external workflow
- **AND** the external reference SHALL identify an independently revocable temporary grant rather than a shared long-lived administrator identity
- **AND** the handoff contract SHALL identify independent temporary-access resolution, comparison of its normalized API endpoint and CA identity with the bundle, Flux installation, first-reconciliation verification, and invalidation of that grant's cluster-side authentication as platform-side obligations
- **AND** deleting only the secret-provider value SHALL NOT satisfy the revocation obligation
- **AND** success of the IaaS handoff-render command SHALL NOT be treated as evidence that those external steps completed
- **AND** bundle transport, publication, signing, cross-repository CI triggering, and the consumer workflow SHALL remain outside this capability

#### Scenario: IaaS command surface is reviewed

- **WHEN** an operator reviews this repository after the handoff capability is implemented
- **THEN** it SHALL expose no executable Flux, Cilium, CSI, Gateway, certificate, observability, application deployment, cross-repository CI trigger, bootstrap-credential creation, or credential-revocation path
- **AND** `platform/` SHALL remain a boundary document rather than an in-cluster desired-state root

### Requirement: Software-only handoff acceptance

The system SHALL allow the handoff capability to be accepted without a real
cluster or external platform repository.

#### Scenario: Handoff capability is validated synthetically

- **WHEN** the change is validated with synthetic K3s model, readiness results, CA identity, repository coordinates, and external secret references
- **THEN** acceptance SHALL use offline composition, deterministic rendering, safety-boundary tests, and synthetic read-only workflow tests
- **AND** it SHALL NOT require PVE access, guest access, K3s mutation, Git-provider access, secret-provider access, Flux installation, or platform reconciliation

### Requirement: Explicit handoff command safety classes

The system SHALL keep offline validation distinct from online readiness and the
local handoff artifact write.

#### Scenario: Operator validates handoff composition offline

- **WHEN** the operator invokes `platform-handoff-check`
- **THEN** the command SHALL require explicit K3s intent, generated inventory, platform-handoff intent, and whole-cluster scope
- **AND** it SHALL NOT require an output path, host access, or runtime credentials

#### Scenario: Operator renders a handoff bundle

- **WHEN** the operator invokes `platform-handoff-render`
- **THEN** the command SHALL require every offline-check input plus an explicit output path
- **AND** it SHALL be classified as infrastructure-read-only with an explicit local protected-artifact write
- **AND** it SHALL remain outside the aggregate offline gate
