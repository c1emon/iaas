# Service Metadata Inventory

Declared service metadata only: this document is generated offline from inventory/services.yml and cross-checked against inventory/vms.yml owner_vm names.

It is not live verification and it does not create, update, or verify DNS, firewall, reverse proxy, PVE, guest, or network state.

| Service | Owner VM | Endpoint | FQDN | Protocol | Port | Exposure | Auth | Review hints |
|---|---|---|---|---|---:|---|---|---|
| dev-dashboard | dev-web-01 | web | dashboard.dev.example.invalid | http | 8080 | lan | app | dns: manual; reverse proxy: future; opnsense: review-before-public |
| dev-dashboard | dev-web-01 | metrics | - | http | 9090 | internal | none | - |
| prod-api | prod-app-01 | api | api.example.invalid | https | 443 | public | none | dns: manual; reverse proxy: future; opnsense: review-public |
| prod-api | prod-app-01 | grpc | grpc.example.invalid | grpc | 8443 | vpn | sso | reverse proxy: future |
| media-admin | media-lab-01 | admin | - | https | 8443 | vpn | unknown | dns: manual |
| media-admin | media-lab-01 | database | - | postgres | 5432 | internal | client-cert | - |

## Warnings

| Service | Endpoint | Code | Message |
|---|---|---|---|
| prod-api | api | public-exposure | public exposure requires operator review |
| prod-api | api | public-unauthenticated | public exposure with auth none |
| media-admin | admin | missing-fqdn | non-internal endpoint lacks fqdn |
| media-admin | admin | auth-unknown | auth unknown needs review |
