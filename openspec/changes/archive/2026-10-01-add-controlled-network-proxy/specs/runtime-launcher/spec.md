## ADDED Requirements

### Requirement: Controlled proxy transport in both engines
The launcher SHALL implement the runtime-network-proxy contract through local Docker and DinD, separately from credential discovery. Effective network permission SHALL determine proxy injection. Docker client defaults and image ENV SHALL NOT implicitly select a different proxy policy for task containers.

#### Scenario: Online local or DinD operation
- **WHEN** a caller invokes a compatible runtime with supported proxy variables
- **THEN** the launcher SHALL inject normalized values into the execution container without putting proxy URLs in command-line arguments
- **AND** local mounts and DinD transfer SHALL retain the same proxy semantics and existing input/credential boundaries

#### Scenario: No caller proxy or offline discovery
- **WHEN** supported caller proxy settings are absent, or the container is for capabilities, discovery, transfer or an offline operation
- **THEN** the launcher SHALL explicitly neutralize automatic proxy variables from Docker defaults or image ENV
- **AND** execution without proxy settings SHALL retain direct behavior for permitted networking while offline and discovery containers retain network isolation
- **AND** Docker context, daemon networking and image-pull policy SHALL NOT be changed by this task proxy configuration

### Requirement: Proxy capability admission
Runtime capabilities SHALL advertise network_proxy_version=1 when the controlled proxy contract, including Basic authentication protection and its explicit supported-path boundary, is implemented. For effective network-enabled operations, a launcher with any non-empty supported proxy item, including NO_PROXY alone, SHALL require that support before execution rather than silently passing configuration to an image that filters it out. Offline operations SHALL NOT require the proxy capability or parse authentication values merely because host proxy settings exist.

#### Scenario: Proxy with an incompatible image
- **WHEN** the effective operation permits networking and a supported proxy item is configured but the selected image lacks the supported proxy capability
- **THEN** the launcher SHALL fail with compatibility guidance without running the online operation
- **AND** it SHALL NOT silently drop the proxy, switch images or select a direct fallback

### Requirement: Real locked dependency consumption through the launcher
Acceptance SHALL demonstrate PVE prepare-dependencies through fixed-version launcher/runtime in local and real DinD under task-scoped direct-egress restrictions, with a reachable proxy and no facility credentials or state authority.

#### Scenario: Direct path unavailable and proxy succeeds
- **WHEN** a fresh workspace requires a locked provider package not satisfied by preinstalled or cached dependencies
- **THEN** an unproxied invocation SHALL fail in the restricted environment and a proxied invocation SHALL succeed with actual proxy/download evidence
- **AND** the archive SHALL satisfy lockfile, checksum and existing restore checks
- **AND** the operation SHALL not discover, receive or access facility credential/backend/state decoys

#### Scenario: Authenticated proxy consumption
- **WHEN** formal local and real DinD launcher invocations use a test-scoped proxy requiring Basic authentication
- **THEN** valid authentication SHALL allow actual locked dependency downloads and invalid authentication SHALL produce non-zero failure without direct fallback
- **AND** ordinary logs, error output, plans, archives and summaries SHALL contain no configured authentication material
- **AND** authentication or proxy request headers SHALL NOT be included in ordinary acceptance evidence

#### Scenario: Bypass, failure and isolation controls
- **WHEN** the same formal invocation path exercises NO_PROXY matching, an unavailable proxy and an offline operation
- **THEN** request evidence SHALL distinguish bypass and proxy routing, the unavailable proxy SHALL yield diagnosable non-zero failure without fallback, and the offline operation SHALL remain isolated
- **AND** simulated transfer tests or cached package success SHALL NOT replace real container/network consumption evidence
