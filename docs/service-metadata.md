# Service Metadata Inventory

`environments/astra/inventory/services.yml` is an operator-authored service catalog.

## Schema

- `schema_version: 1`
- `services`: list of service records

Each service record includes:

- `name` (required, slug)
- `owner_vm` (required, must match a VM name from `environments/astra/inventory/vms.yml`)
- `description` (optional)
- `endpoints` (required, non-empty)

Each endpoint includes:

- `name` (optional, slug)
- `fqdn` (optional)
- `port` (required, 1-65535)
- `protocol` (required, lower-case)
- `exposure` (required: `internal`, `lan`, `vpn`, `public`)
- `auth` (required: `none`, `app`, `basic`, `sso`, `client-cert`, `vpn`, `unknown`)
- `dns_hint`, `reverse_proxy_hint`, `opnsense_hint` (optional review hints)

## Review hints

Hints are documentation only. They are copied into generated docs for operator review and do not drive DNS, reverse proxy, OPNsense, firewall, guest, VM, or network automation.

## Boundaries

This catalog is declared metadata, not live verification. It does not mutate or verify DNS, firewall, reverse proxy, PVE, guests, or network state.

## Example

```yaml
schema_version: 1
services:
  - name: example-service
    owner_vm: prod-app-01
    endpoints:
      - name: web
        fqdn: example.invalid
        port: 443
        protocol: https
        exposure: public
        auth: sso
```
