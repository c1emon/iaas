## ADDED Requirements

### Requirement: Service metadata source of truth
The system SHALL support an operator-authored service metadata inventory at `inventory/services.yml`.

#### Scenario: Operator declares a service owned by a PVE VM
- **WHEN** an operator declares a service in `inventory/services.yml`
- **THEN** the declaration SHALL include a unique service name
- **AND** it SHALL include an `owner_vm` that references a VM declared in `inventory/vms.yml`
- **AND** it SHALL include one or more service endpoints
- **AND** it MAY include an operator-readable description

#### Scenario: Service metadata references an unknown VM
- **WHEN** a service declaration references an `owner_vm` that is not declared in the PVE VM inventory
- **THEN** service inventory validation SHALL fail before generated service documentation is accepted
- **AND** the failure SHALL identify the invalid service and missing VM reference

### Requirement: Endpoint metadata validation
The system SHALL validate endpoint metadata for each declared service.

#### Scenario: Operator declares multiple endpoints for one service
- **WHEN** a service has multiple endpoints such as web, API, metrics, or gRPC entrypoints
- **THEN** the service inventory SHALL allow multiple endpoint records under the same service
- **AND** each endpoint SHALL be represented independently in generated documentation

#### Scenario: Endpoint name is omitted
- **WHEN** an endpoint omits its optional `name`
- **THEN** validation SHALL accept the endpoint if all required endpoint fields are valid
- **AND** generated documentation SHALL still identify the endpoint by service, protocol, and port context

#### Scenario: Endpoint contains required access metadata
- **WHEN** an endpoint is declared
- **THEN** it SHALL include a port in the range `1-65535`
- **AND** it SHALL include a supported protocol value such as a common HTTP, transport, RPC, database, or service protocol
- **AND** it SHALL include an exposure value of `internal`, `lan`, `vpn`, or `public`
- **AND** it SHALL include an auth value of `none`, `app`, `basic`, `sso`, `client-cert`, `vpn`, or `unknown`
- **AND** it MAY include an FQDN

#### Scenario: Endpoint contains invalid access metadata
- **WHEN** an endpoint has an invalid port, unsupported protocol, unsupported exposure value, unsupported auth value, or malformed field type
- **THEN** service inventory validation SHALL fail
- **AND** it SHALL report the service and endpoint context for operator correction

### Requirement: Service exposure warnings
The system SHALL surface service metadata conditions that require operator review without treating documented current state as a hard validation failure.

#### Scenario: Non-internal endpoint lacks an FQDN
- **WHEN** an endpoint has exposure `lan`, `vpn`, or `public` and does not declare an FQDN
- **THEN** generated service documentation SHALL include a warning for that endpoint
- **AND** generation/checking SHALL still succeed if there are no hard validation failures

#### Scenario: Public endpoint is declared
- **WHEN** an endpoint has exposure `public`
- **THEN** generated service documentation SHALL include a warning that public exposure requires operator review
- **AND** generation/checking SHALL still succeed if there are no hard validation failures

#### Scenario: Public endpoint declares no auth
- **WHEN** an endpoint has exposure `public` and auth `none`
- **THEN** generated service documentation SHALL include a warning about unauthenticated public exposure
- **AND** generation/checking SHALL still succeed if there are no hard validation failures

#### Scenario: Endpoint auth is unknown
- **WHEN** an endpoint declares auth `unknown`
- **THEN** generated service documentation SHALL include a warning that authentication needs review
- **AND** generation/checking SHALL still succeed if there are no hard validation failures

### Requirement: Generated service documentation
The system SHALL generate committed, non-sensitive service documentation from service metadata.

#### Scenario: Operator regenerates service documentation
- **WHEN** an operator runs the repository generation workflow
- **THEN** the system SHALL generate `docs/generated/services.md` from `inventory/services.yml`
- **AND** the generated document SHALL include service names, owner VMs, endpoint details, exposure, auth, FQDNs when present, and review hints when present
- **AND** it SHALL include warning records when service metadata has warning conditions

#### Scenario: Generated service documentation is stale
- **WHEN** service metadata changes without regenerating committed service documentation
- **THEN** the generated-output check SHALL fail
- **AND** it SHALL report the stale service documentation artifact

#### Scenario: Generated service documentation remains non-sensitive
- **WHEN** service documentation is generated or checked
- **THEN** the generated output SHALL NOT contain passwords, private keys, API token secrets, password hashes, or other runtime secrets

### Requirement: Service metadata remains documentation-only
The system SHALL treat service metadata as declared documentation and review context in the first version.

#### Scenario: Service metadata contains DNS, reverse proxy, or OPNsense review hints
- **WHEN** endpoint metadata includes `dns_hint`, `reverse_proxy_hint`, or `opnsense_hint`
- **THEN** those hints SHALL be copied into generated documentation for operator review
- **AND** they SHALL NOT create, update, delete, or verify DNS records, reverse proxy configuration, OPNsense settings, firewall rules, NAT, or aliases

#### Scenario: Default offline validation runs
- **WHEN** an operator or CI runs the default offline validation path
- **THEN** service metadata checks SHALL run without PVE API, OPNsense API, switch access, reverse proxy access, SSH, 1Password, or infrastructure secrets
- **AND** they SHALL NOT mutate PVE, guests, DNS, OPNsense, reverse proxy, switch, or network state
