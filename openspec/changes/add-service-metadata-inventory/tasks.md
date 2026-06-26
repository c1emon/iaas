## 1. Schema and Boundary Decisions

- [ ] 1.1 Confirm the first-version `inventory/services.yml` structure: services with required `name`, required `owner_vm`, optional `description`, and non-empty `endpoints`.
- [ ] 1.2 Confirm endpoint fields: optional `name`, optional `fqdn`, required `port`, required `protocol`, required `exposure`, required `auth`, and optional review hints.
- [ ] 1.3 Confirm allowed `exposure` values are `internal`, `lan`, `vpn`, and `public`.
- [ ] 1.4 Confirm allowed `auth` values are `none`, `app`, `basic`, `sso`, `client-cert`, `vpn`, and `unknown`.
- [ ] 1.5 Define the initial allowed protocol set for common protocols such as HTTP, HTTPS, TCP, UDP, gRPC, SSH, DNS, and common datastore/application protocols.
- [ ] 1.6 Confirm review hints are documentation-only and do not drive DNS, reverse proxy, OPNsense, firewall, guest, VM, or network automation.

## 2. Service Inventory Implementation

- [ ] 2.1 Add `inventory/services.yml` with schema version `1` and representative service/endpoint examples tied to existing VM declarations.
- [ ] 2.2 Add a separate `scripts/services_inventory/` package with path constants, YAML loading, validation, model assembly, Markdown rendering, and CLI entrypoint.
- [ ] 2.3 Validate service document shape, unknown keys, service name uniqueness, service name format, and required fields.
- [ ] 2.4 Validate `owner_vm` references against declared PVE VM names from `inventory/vms.yml` without writing or changing PVE inventory outputs.
- [ ] 2.5 Validate endpoint list shape, endpoint name format when present, port range, protocol values, exposure values, auth values, and optional hint field types.
- [ ] 2.6 Generate stable warning records for non-internal endpoints without FQDNs, public endpoints, public endpoints with `auth: none`, and endpoints with `auth: unknown`.

## 3. Generated Documentation and Command Surface

- [ ] 3.1 Generate `docs/generated/services.md` as a committed non-sensitive service catalog.
- [ ] 3.2 Include service rows with service name, owner VM, endpoint name if present, FQDN, protocol, port, exposure, auth, and review hints.
- [ ] 3.3 Include a generated warnings section when service metadata contains warning conditions.
- [ ] 3.4 Add dedicated root targets for service docs generation and stale-output checking.
- [ ] 3.5 Integrate service docs generation into root `make generate`.
- [ ] 3.6 Integrate service docs stale checking into root `make check-generated`, and therefore the existing `make check` path.
- [ ] 3.7 Ensure generated outputs and logs do not contain passwords, private keys, API token secrets, or other runtime secrets.

## 4. Documentation and Operational Boundaries

- [ ] 4.1 Document `inventory/services.yml` purpose, schema, examples, and review-hint semantics.
- [ ] 4.2 Document that service metadata is declared documentation, not live service health or DNS/firewall/proxy verification.
- [ ] 4.3 Document that this change does not create or modify DNS, OPNsense, reverse proxy, PVE, guest, VM, or network state.
- [ ] 4.4 Update generated/validation documentation to mention service docs as part of the offline generation/check flow.

## 5. Tests and Validation

- [ ] 5.1 Add unit tests for valid service metadata with multiple endpoints.
- [ ] 5.2 Add tests for duplicate service names, invalid owner VM references, invalid ports, invalid protocols, invalid exposures, invalid auth values, and empty endpoint lists.
- [ ] 5.3 Add tests for optional endpoint names and warning generation semantics.
- [ ] 5.4 Add tests for generated Markdown content and warnings section stability.
- [ ] 5.5 Add tests proving service docs stale checks are offline and participate in root generated-output checks.
- [ ] 5.6 Run `make check` locally.
- [ ] 5.7 Run the service inventory test subset locally.
- [ ] 5.8 Run `make secret-scan` locally.
- [ ] 5.9 Run `openspec validate add-service-metadata-inventory`.
