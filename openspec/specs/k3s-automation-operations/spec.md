# k3s-automation-operations Specification

## Purpose
Define a reusable and fail-closed operator capability for composing K3s intent
with prepared Debian VM facts, then validating, deploying, verifying, backing
up, and upgrading K3s without coupling it to a particular live environment.

## Requirements

### Requirement: Composed K3s intent and VM facts
The system SHALL require an explicit K3s intent document and an explicit
generated Ansible inventory for every operator workflow, and SHALL treat the
inventory as the source of VM-owned host and network facts.

Every online workflow SHALL additionally require an explicit non-empty scope
containing only nodes declared by the composed cluster model.

#### Scenario: Operator validates a cluster definition
- **WHEN** an operator provides K3s intent and a generated Ansible inventory
- **THEN** the system SHALL resolve every declared VM reference to exactly one inventory host
- **AND** it SHALL derive CPU architecture and SSH address from generated host facts, and derive node IP, prefix, and NIC network from the unique `pve_nics` entry matching the cluster-wide node-network role
- **AND** it SHALL reject unknown or duplicate host references and missing, ambiguous, or unusable node-network-role NIC facts

#### Scenario: K3s intent duplicates a VM fact
- **WHEN** K3s intent supplies a per-node IP address, interface, NIC-role override, architecture, SSH setting, VM resource, template, placement, gateway, DNS, or another VM-owned fact instead of referencing the generated inventory
- **THEN** validation SHALL fail rather than create a second source of truth

#### Scenario: No environment is selected
- **WHEN** an operator does not provide the required K3s intent or inventory
- **THEN** the system SHALL fail before contacting any host
- **AND** it SHALL NOT silently select the Astra environment or an ad-hoc host list

### Requirement: Offline K3s contract validation
The system SHALL validate composed K3s deployment intent without infrastructure
access or runtime credentials.

#### Scenario: Valid intent is checked offline
- **WHEN** the offline K3s check runs with synthetic or operator-provided non-secret inputs
- **THEN** it SHALL validate an exact K3s version, an architecture-keyed artifact source/checksum map covering every architecture derived from selected VMs, embedded-etcd mode, unique node identities, server and agent roles, exactly one initial bootstrap server, a supported server count, bootstrap ordering, endpoint policy, Pod and Service CIDRs, component policy, registry and service-proxy policy, snapshot source, stable server-token reference, and external secret references
- **AND** it SHALL accept either one server or an odd number of at least three servers
- **AND** it SHALL produce no infrastructure side effects

#### Scenario: Cluster and VM networking are composed
- **WHEN** node networking is resolved from the generated inventory
- **THEN** derived node IPs SHALL be unique and each selected node-network-role NIC SHALL have a usable static address
- **AND** the role SHALL be selected once for the cluster, SHALL NOT fall back automatically, and SHALL reject storage or ingress roles; an early lab MAY explicitly select the management role
- **AND** Pod and Service CIDRs SHALL be valid, mutually non-overlapping, and non-overlapping with the selected hosts' VM subnets
- **AND** a bootstrap-derived registration address SHALL use the initial server's derived node IP
- **AND** a fixed registration address SHALL be one valid stable external DNS/VIP, SHALL NOT repeat a selected VM node address, and SHALL be added to required TLS SANs automatically

#### Scenario: Unsafe or incomplete intent is supplied
- **WHEN** the configuration uses an unpinned version or artifact, a missing/unsupported VM architecture or missing artifact mapping for a derived architecture, unsupported datastore, invalid server count, missing or ambiguous node-network-role NIC, forbidden node-network role, plaintext secret, invalid role combination, ambiguous bootstrap server, invalid network range, implicit or version-unsupported registry fallback policy, insecure registry TLS, unsafe proxy bypass override, invalid snapshot source, uncontrolled server-token reference, or inconsistent endpoint policy
- **THEN** validation SHALL fail closed with operator-readable context
- **AND** it SHALL NOT render an executable deployment plan

### Requirement: Read-only host preflight
The system SHALL provide an explicit online read-only preflight before K3s
deployment or upgrade.

#### Scenario: Prepared Debian hosts pass preflight
- **WHEN** preflight runs against an explicit non-empty scope of selected nodes
- **THEN** it SHALL inspect operating-system support, normalize guest `x86_64` to `amd64` while preserving canonical `amd64`, require an exact match with generated `pve_architecture`, inspect cgroups, required kernel capabilities, time synchronization, discover the runtime interface owning the derived node IP, and inspect required ports, disk capacity, configured APT-source reachability, the selected architecture-bound artifact's reachability through the declared acquisition path, authenticated registry reachability when declared, registry TLS material, and conflicting prior installation state
- **AND** it SHALL report per-node pass, warning, and failure results without changing host state
- **AND** it SHALL NOT run `apt update` or configure APT, shell, or Git proxy state

#### Scenario: A blocking prerequisite fails
- **WHEN** any selected node fails a required preflight condition
- **THEN** deployment and upgrade SHALL be blocked for that scope

#### Scenario: Read-only access requires credentials
- **WHEN** standalone preflight declares authenticated artifact or registry access
- **THEN** it SHALL require the action-scoped read-only runtime secret and use the same resolved endpoint and proxy/authentication path as deployment
- **AND** missing credentials SHALL fail before host mutation without changing global shell, APT, or Git proxy state

### Requirement: Controlled K3s deployment
The system SHALL provide an explicit mutation-capable workflow that installs a
pinned K3s release and converges declared server and agent configuration.

#### Scenario: Operator selects a mutation scope
- **WHEN** an operator requests deployment
- **THEN** the operator SHALL provide a non-empty scope containing declared K3s nodes or explicitly select all declared K3s nodes
- **AND** the workflow SHALL NOT default to all inventory hosts or silently expand a partial scope
- **AND** omitted prerequisite nodes SHALL pass live read-only verification in the same invocation or deployment SHALL fail before mutation

#### Scenario: A new cluster is bootstrapped
- **WHEN** an operator explicitly runs deployment with required runtime secrets
- **THEN** the workflow SHALL rerun preflight in the same invocation against the same resolved intent, inventory, and scope
- **AND** it SHALL configure the initial server with embedded-etcd cluster initialization before joining additional servers and agents
- **AND** each node SHALL use its inventory-derived identity and node IP, and each server SHALL use the derived advertise address
- **AND** a fixed external registration address SHALL be rendered into required TLS SANs automatically
- **AND** downloaded executable artifacts SHALL be version-pinned and integrity-verified before execution

#### Scenario: Later nodes join the initial server
- **WHEN** the initial self-signed-CA server was bootstrapped with an externally referenced short token
- **THEN** the workflow SHALL read the initial server's active secure token through a protected redacted ephemeral channel after bootstrap
- **AND** it SHALL compare the credential portion with the referenced short token and validate the CA hash when the external token is already secure
- **AND** additional servers and agents SHALL join with the active secure token rather than the short token
- **AND** the secure token SHALL NOT enter CLI arguments, inventory, Ansible facts/fact cache, controller files, or ordinary output and SHALL be discarded after the invocation

#### Scenario: Pinned K3s artifact is acquired
- **WHEN** deployment acquires the declared K3s executable
- **THEN** it SHALL select the entry for the node's generated `pve_architecture` and use the same exact source URL, action-scoped proxy/authentication references, version, and checksum validated by preflight
- **AND** it SHALL NOT execute an unpinned remote installer or promote acquisition credentials to global host proxy settings

#### Scenario: External platform components are selected
- **WHEN** the cluster contract selects the repository's external-CNI direction
- **THEN** deployment SHALL disable Flannel and the packaged network-policy controller through explicit CNI policy
- **AND** it SHALL separately disable conflicting packaged Traefik and ServiceLB components
- **AND** it SHALL report only bootstrap readiness until the later platform layer makes nodes ready

#### Scenario: Deployment is repeated
- **WHEN** deployment is run against nodes already matching the declared K3s version and configuration
- **THEN** the workflow SHALL be idempotent for managed state
- **AND** it SHALL avoid unnecessary reinstallation or service restart

#### Scenario: Bootstrap or join fails
- **WHEN** the initial server or a subsequent join step fails
- **THEN** the workflow SHALL stop dependent steps and identify the failed node and phase
- **AND** it SHALL NOT continue with a partially qualified node set

### Requirement: K3s runtime registry and service-proxy policy
The system SHALL manage container-registry and service-proxy policy only where
it is consumed by K3s and its embedded containerd runtime.

#### Scenario: Runtime egress policy is rendered
- **WHEN** deployment prepares a declared server or agent
- **THEN** it SHALL render `/etc/rancher/k3s/registries.yaml` from validated mirror, rewrite, TLS-path, and explicit upstream-fallback policy
- **AND** fallback denial SHALL render a version-supported `disable-default-registry-endpoint` K3s setting and SHALL prevent mirror failure from contacting the default upstream endpoint
- **AND** registry endpoints SHALL use verified HTTPS; declared CA and client-certificate files SHALL match their expected identity and permissions before service mutation, and insecure or TLS-skip settings SHALL be rejected
- **AND** it SHALL render K3s or K3s-agent systemd proxy environment from runtime-injected proxy values
- **AND** it SHALL derive `NO_PROXY` from localhost/loopback, declared node subnets, Pod and Service CIDRs, configured cluster domain, the API endpoint, and internal registry endpoint before adding bounded validated explicit extras
- **AND** it SHALL reject global bypass values such as `/0`
- **AND** these files SHALL exist before the K3s service first starts

#### Scenario: Registry or proxy policy contains credentials
- **WHEN** registry authentication, client TLS material, or an authenticated proxy is required
- **THEN** committed intent SHALL contain only runtime secret references
- **AND** resolved values SHALL NOT enter CLI arguments, generated/cached state, Ansible facts/fact cache, diffs, or ordinary controller temporary files
- **AND** rendered node-side files and task output SHALL use restrictive permissions, redaction, and no-diff behavior, and protected temporary material SHALL be removed after the action

#### Scenario: Runtime egress policy changes
- **WHEN** the declared registry or K3s service-proxy policy changes on an installed node
- **THEN** affected nodes SHALL restart through the controlled serial deployment path
- **AND** each affected node SHALL pass role-appropriate service and cluster health verification before the next node is changed
- **AND** explicit retirement SHALL remove only role-owned registry/proxy settings and files before the controlled restart
- **AND** unchanged policy SHALL NOT restart K3s

#### Scenario: Generic host proxy is requested
- **WHEN** an operator needs Debian APT configuration or global shell or Git proxy settings
- **THEN** this capability SHALL NOT configure them
- **AND** documentation SHALL direct them to the separately reviewed VM baseline policy

### Requirement: Runtime secret and snapshot protection
The system SHALL keep K3s tokens, snapshots, and other sensitive runtime
material outside committed configuration and ordinary command output.

#### Scenario: Deployment resolves cluster credentials
- **WHEN** deployment or upgrade requires sensitive material
- **THEN** it SHALL accept the material through documented protected runtime injection using external references
- **AND** it SHALL NOT place resolved values in CLI arguments, generated or cached state, Ansible facts/fact cache, diffs, or ordinary controller temporary files
- **AND** any managed secret file on a node SHALL use restrictive ownership and permissions

#### Scenario: Workflow output is recorded
- **WHEN** validation, preflight, deployment, verification, snapshot, or upgrade emits logs or artifacts
- **THEN** it SHALL redact tokens, credentials, kubeconfig client material, and private keys

#### Scenario: Embedded-etcd snapshot is stored
- **WHEN** a snapshot is created
- **THEN** the snapshot SHALL remain in a root-only node-side location by default
- **AND** the workflow SHALL require the selected server and embedded etcd to be healthy without making snapshot creation depend on resolving or comparing the external server-token reference
- **AND** it SHALL NOT be copied to the controller, repository, or ordinary generated artifacts
- **AND** ordinary output SHALL expose only non-sensitive snapshot metadata

### Requirement: Staged verification
The system SHALL separate K3s bootstrap verification from complete cluster and
platform qualification.

#### Scenario: Core K3s bootstrap is verified
- **WHEN** the server and agent deployment workflow completes
- **THEN** a read-only verification workflow SHALL check the API endpoint, declared node registration, role, version, embedded-etcd health, and core service state
- **AND** it SHALL label the result as software or environment evidence for the actual scope tested

#### Scenario: External CNI is not installed
- **WHEN** K3s is configured for an external CNI but the later platform layer is absent
- **THEN** verification MAY classify only the expected CNI-not-initialized condition as bootstrap-ready
- **AND** disk pressure, kubelet failure, unexpected service failure, and other readiness causes SHALL remain blocking failures
- **AND** verification SHALL NOT claim complete node readiness, workload networking, ingress, storage, production readiness, or high availability

### Requirement: Bounded day-two operations
The system SHALL provide explicit embedded-etcd snapshot and controlled-upgrade
workflows while keeping destructive recovery operations outside the first
capability.

#### Scenario: Operator creates an embedded-etcd snapshot
- **WHEN** an operator explicitly runs the snapshot command against the single configured snapshot-source server
- **THEN** the workflow SHALL confirm that the target is an eligible declared server and create an embedded-etcd snapshot
- **AND** it SHALL use the declared root-only node-side location and deterministic snapshot naming
- **AND** it SHALL NOT delete existing snapshots automatically in the first version
- **AND** it SHALL report non-sensitive snapshot identity and outcome without claiming restore readiness

#### Scenario: Operator upgrades K3s
- **WHEN** an operator selects an exact target version and explicitly selects all declared cluster nodes
- **THEN** the target SHALL be no lower than any observed node version, and each node below the target SHALL remain in its current Kubernetes minor or advance by exactly one minor
- **AND** the workflow SHALL reject downgrade and skipped-minor transitions before mutation
- **AND** it SHALL reject partial or implicit upgrade scopes before mutation
- **AND** it SHALL rerun preflight and create a completed pre-upgrade snapshot in the same invocation for the same resolved cluster, inventory, and whole-cluster scope
- **AND** it SHALL upgrade one server at a time before upgrading agents one at a time
- **AND** it SHALL verify API and embedded-etcd health after each server and node registration and service state after each agent
- **AND** it SHALL stop on a failed stage

#### Scenario: Operator resumes an interrupted upgrade
- **WHEN** observed nodes contain only a supported mixture of the prior version and the same exact target version
- **THEN** the workflow SHALL health-verify and skip nodes already at the target
- **AND** it SHALL continue eligible lower-version servers and then agents one at a time with the same verification and stop-on-failure rules
- **AND** any node above the target or outside the supported prior/target transition SHALL fail before mutation

#### Scenario: Destructive operation is considered
- **WHEN** an operator reviews the first-version command surface
- **THEN** it SHALL expose no automatic restore, uninstall, datastore replacement, or destructive node-removal entrypoint
- **AND** documentation SHALL direct those operations to a separately designed recovery procedure

### Requirement: Capability-only acceptance boundary
The system SHALL allow the K3s automation capability to be implemented and
validated without creating a real environment deployment.

#### Scenario: Capability implementation is accepted
- **WHEN** the change is validated without a declared Astra K3s cluster
- **THEN** acceptance SHALL use synthetic VM inventory and K3s overlay fixtures, unit tests, Ansible syntax and lint checks, configuration rendering checks, and explicit safety-boundary tests
- **AND** it SHALL NOT require PVE apply, guest mutation, K3s installation, or live cluster access

#### Scenario: No live evidence exists
- **WHEN** only offline or synthetic validation has run
- **THEN** documentation and status reporting SHALL describe the capability as implemented but not deployed or live-qualified
