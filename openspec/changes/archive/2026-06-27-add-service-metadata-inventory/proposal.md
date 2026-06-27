## Why

P1 is shifting the repository from VM creation toward safe operation of a small PVE environment. The repository can already describe VMs, generate PVE/OpenTofu inputs, run online PVE preflight, and verify guests, but it does not yet have a reviewed source of truth for the services that run on those VMs.

Operators need a lightweight service catalog that answers: which service runs on which VM, which endpoint(s) it exposes, whether an FQDN is expected, how broadly it is exposed, and what DNS/reverse-proxy/OPNsense review hints apply. This should improve operational visibility without introducing DNS, firewall, or reverse-proxy mutation.

## What Changes

- Add `inventory/services.yml` as an operator-authored service metadata inventory.
- Model each service with an owner VM and one or more endpoint declarations.
- Validate service names, owner VM references, endpoint ports, endpoint protocols, exposure scopes, and auth modes offline.
- Support multiple endpoints per service and optional endpoint names.
- Treat review concerns such as public exposure, unknown auth, and non-internal endpoints without FQDNs as warnings rather than hard failures.
- Generate committed, non-sensitive service documentation at `docs/generated/services.md`.
- Add a separate `scripts/services_inventory/` implementation rather than widening `scripts/pve_inventory/`.
- Integrate service generation/checking into root `make generate`, `make check-generated`, and therefore `make check`.
- Keep the first version documentation-only: no DNS, OPNsense, reverse proxy, guest, VM, PVE, or network mutation.

## Capabilities

### New Capabilities
- `service-metadata-inventory`: Defines YAML service metadata, endpoint validation, warning semantics, generated documentation, and non-mutating boundaries.

### Modified Capabilities
- `iaas-validation-entrypoints`: Includes service metadata documentation generation and stale-output checking in the offline validation surface.

## Impact

- Affected areas:
  - New `inventory/services.yml` service metadata source file.
  - New `scripts/services_inventory/` validation, model, rendering, and CLI code.
  - New generated documentation at `docs/generated/services.md`.
  - Root `Makefile` generation/check target composition.
  - Tests for service validation, warnings, generated docs, stale-output detection, and offline boundary behavior.
- Operational impact:
  - Operators gain a reviewed service catalog tied to declared PVE VMs.
  - Default offline validation remains credential-free and CI-compatible.
  - Warnings appear in generated docs for operator review but do not block checks when generated output is up to date.
- Non-goals:
  - DNS record creation, reverse-proxy config generation, OPNsense aliases/rules/NAT, service health checks, Ansible deployment, NetBox integration, and any live infrastructure mutation.
