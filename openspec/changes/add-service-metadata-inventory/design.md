## Context

The current repository source-of-truth model is intentionally small and YAML-based:

```text
inventory/pve-cluster.yml
inventory/vms.yml
        │
        ▼
scripts/pve_inventory
        │
        ├── infra/tofu/pve/generated.auto.tfvars.json
        ├── ansible/inventories/generated/pve.yml
        ├── docs/generated/pve-vms.md
        └── infra/packer/.../template-build.env
```

That model describes infrastructure resources and guest targets. It does not describe user-facing or operator-facing services. P1 needs a service catalog before later work such as cluster health checks, rolling maintenance runbooks, DNS planning, reverse proxy planning, or OPNsense review can reason about exposed services.

This change should add service metadata as a separate documentation-oriented lane:

```text
inventory/services.yml ───────┐
                              ▼
inventory/vms.yml ──▶ scripts/services_inventory ──▶ docs/generated/services.md
                    owner_vm cross-check
```

The service lane may read the VM inventory to validate `owner_vm`, but it should not become part of the PVE provisioning renderer.

## Goals / Non-Goals

**Goals:**

- Add an operator-authored `inventory/services.yml` file.
- Represent services with one or more endpoints.
- Validate service metadata offline and deterministically.
- Cross-check `owner_vm` against declared PVE VM names from `inventory/vms.yml`.
- Generate committed non-sensitive Markdown documentation at `docs/generated/services.md`.
- Surface review warnings for service metadata that needs operator attention.
- Integrate service generation and stale-output checks into the existing offline command surface.
- Keep implementation isolated under `scripts/services_inventory/`.

**Non-Goals:**

- Do not generate or mutate DNS records.
- Do not generate or mutate reverse proxy configuration.
- Do not generate or mutate OPNsense aliases, firewall rules, NAT, or DNS settings.
- Do not perform service health checks.
- Do not deploy or configure guest services through Ansible.
- Do not add NetBox or another external source-of-truth system.
- Do not add online checks, runtime secrets, SSH, PVE API calls, or infrastructure mutation to `make check`.

## Decisions

### Keep service inventory separate from PVE inventory implementation

Service metadata is related to VMs but is not VM lifecycle input. The first implementation should use a new `scripts/services_inventory/` package rather than adding service parsing to `scripts/pve_inventory/`.

This keeps ownership clear:

```text
scripts/pve_inventory       owns PVE VM lifecycle inputs and generated VM docs
scripts/services_inventory  owns service catalog validation and generated service docs
```

The service generator may read `inventory/vms.yml` and reuse only stable, read-only VM validation behavior to build the set of allowed VM names. It should not write PVE outputs or alter the PVE model.

Alternative considered: fold service docs into `scripts/pve_inventory`. Rejected because services are a different layer and future service metadata may evolve toward DNS, reverse proxy, or app exposure planning independently of VM provisioning.

### Use a service plus endpoint schema

Each service should include:

- `name`: required unique service slug.
- `owner_vm`: required VM name that must exist in `inventory/vms.yml`.
- `description`: optional operator-readable text.
- `endpoints`: required non-empty list.

Each endpoint should include:

- `name`: optional endpoint slug for readability when a service has multiple endpoints.
- `fqdn`: optional FQDN string or null.
- `port`: required integer from 1 through 65535.
- `protocol`: required common protocol value.
- `exposure`: required one of `internal`, `lan`, `vpn`, or `public`.
- `auth`: required one of `none`, `app`, `basic`, `sso`, `client-cert`, `vpn`, or `unknown`.
- `dns_hint`, `reverse_proxy_hint`, `opnsense_hint`: optional operator review hint strings.

Multiple endpoints are supported from the start so a service can document web UI, API, metrics, or gRPC entrypoints without inventing duplicate service records.

### Keep review hints documentation-only

The optional hint fields are operator review hints, not desired-state automation inputs:

```yaml
dns_hint: manual
reverse_proxy_hint: future
opnsense_hint: no-public-exposure
```

They should be copied into generated documentation to guide manual review. They must not trigger DNS, reverse proxy, OPNsense, or firewall generation in this change. If a later change wants to generate configuration from these concepts, it must define stricter semantics separately.

### Use warnings for review concerns without blocking offline validation

Some service metadata should be visible but not fail the repository when intentionally documented. The generator should produce warnings for operator review and include them in `docs/generated/services.md`, while exiting successfully when there are no schema failures.

Initial warning cases:

```text
WARN  exposure is lan/vpn/public and fqdn is missing
WARN  exposure is public
WARN  exposure is public and auth is none
WARN  auth is unknown
```

Hard failures remain reserved for invalid or inconsistent source data, such as duplicate service names, missing owner VMs, invalid protocol/exposure/auth values, invalid ports, empty endpoint lists, or malformed document roots.

This makes public exposure visible in committed generated docs without preventing operators from documenting current reality.

### Integrate with offline generation and stale checks

Service docs are generated committed artifacts and should participate in the normal offline workflow:

```text
make generate          -> regenerate PVE outputs and service docs
make check-generated  -> fail when either PVE outputs or service docs are stale
make check            -> includes check-generated as today
```

Dedicated service targets are useful for local iteration, for example `make services-generate` and `make services-check`, but the aggregate root targets should include them so CI catches stale service documentation.

Because the workflow is offline and documentation-only, it remains safe for cloud CI and disconnected developer workstations.

## Risks / Trade-offs

- Service metadata can drift from live reality because v1 does not perform health or DNS checks → Make generated docs explicit that this is declared metadata, not verified runtime state.
- Free-form hint strings may be interpreted as automation inputs later → Document them as review hints only and require a future OpenSpec change before generating config from them.
- Warnings could be ignored → Render a clear warning section in generated docs and keep warning text stable enough for review.
- Separate implementation duplicates some helper patterns from `pve_inventory` → Keep the package small and only reuse generic behavior where it does not couple service metadata to PVE rendering.
- `owner_vm` only supports declared PVE VMs → Accept this as a first-version boundary; non-PVE or external services can be modeled in a later change if needed.
