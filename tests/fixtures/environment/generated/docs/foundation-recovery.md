# Foundation Recovery Reference

Declared foundation recovery metadata only. This document is generated offline from the selected environment inventory/foundation.yml.

Offline checks (`make foundation-check`) validate schema, references, restore order, storage facts, and generated-doc freshness without contacting internal infrastructure. `make foundation-health` is a separate explicit online read-only probe mode.

## Minimum startup set

1. opnsense
2. truenas
3. internal-dns
4. sing-box
5. harbor
6. external-databases

## Recovery order

1. opnsense
2. truenas
3. internal-dns
4. sing-box
5. harbor
6. external-databases

## Foundation hosts

| Name | Kind | Management identity | Extra addresses | Accepted SPOF | Notes |
|---|---|---|---|---|---|
| opnsense | appliance | https://192.0.2.254 | - | no | Core router and firewall. |
| truenas | appliance | 192.0.2.210 | 198.18.0.210, 203.0.113.210 | no | TrueNAS SCALE storage and data services. |
| foundation-a | bare-metal | 192.0.2.15 | 203.0.113.15 | yes | Docker host for Authentik, Harbor, SmartDNS, Postfix, and Traefik. |
| rk3588 | bare-metal | 192.0.2.253 | 198.19.0.253 | no | sing-box proxy gateway node. |
| external-database-hosts | external-dependency | external dedicated database hosts / provider | - | no | External database hosts outside repository control. |

## Foundation services

| Service | Host | Runtime | Tier | Required before K3s | Restore order | External dependency | Dependencies | Health check | Backup / restore | Break-glass | Notes |
|---|---|---|---|---|---:|---|---|---|---|---|---|
| opnsense | opnsense | appliance | critical | yes | 1 | no | - | http https://192.0.2.254 [200, 302, 401] | opnsense-config; runbook: docs/operations/02-opnsense.md | local-console; access: UI + physical console; secret_ref: op://foundation/opnsense/local-admin | - |
| truenas | truenas | appliance | critical | yes | 2 | no | opnsense | api https://192.0.2.210/api/v2.0.0/system/info [200] | truenas-config; runbook: docs/operations/06-acceptance-and-recovery.md | local-console; access: UI + physical console; secret_ref: op://foundation/truenas/local-admin | - |
| internal-dns | foundation-a | compose | critical | yes | 3 | no | opnsense | dns internal.example.invalid (A) via 203.0.113.15 -> 203.0.113.15 | smartdns-config; runbook: docs/operations/06-acceptance-and-recovery.md | local-admin; access: SSH + console; secret_ref: op://foundation/smartdns/admin | - |
| sing-box | rk3588 | systemd | critical | yes | 4 | no | opnsense, internal-dns | tcp 198.19.0.253:1080 | sing-box-config; runbook: docs/operations/06-acceptance-and-recovery.md | local-admin; access: SSH + console; secret_ref: op://foundation/sing-box/admin | - |
| harbor | foundation-a | compose | critical | yes | 5 | no | internal-dns, truenas | https https://203.0.113.15 [200, 302, 401] | harbor-data; runbook: docs/operations/06-acceptance-and-recovery.md | local-admin; access: UI + SSH; secret_ref: op://foundation/harbor/admin | - |
| external-databases | external-database-hosts | external | critical | yes | 6 | yes | opnsense, internal-dns | tcp external-db.example.invalid:5432 | external-database; runbook: docs/operations/06-acceptance-and-recovery.md | provider-console; access: ticketed support / local admin; secret_ref: ref:provider-managed | - |
| authentik | foundation-a | compose | important | no | - | no | internal-dns | https https://203.0.113.15 [200, 302, 401] | authentik-config; runbook: docs/operations/06-acceptance-and-recovery.md | local-admin; access: UI + console; secret_ref: op://foundation/authentik/admin | - |

## Dependencies

| Service | Depends on |
|---|---|
| opnsense | - |
| truenas | opnsense |
| internal-dns | opnsense |
| sing-box | opnsense, internal-dns |
| harbor | internal-dns, truenas |
| external-databases | opnsense, internal-dns |
| authentik | internal-dns |

## Health checks

| Service | Probe | Expected |
|---|---|---|
| opnsense | http https://192.0.2.254 [200, 302, 401] | 200, 302, 401 |
| truenas | api https://192.0.2.210/api/v2.0.0/system/info [200] | 200 |
| internal-dns | dns internal.example.invalid (A) via 203.0.113.15 -> 203.0.113.15 | - |
| sing-box | tcp 198.19.0.253:1080 | - |
| harbor | https https://203.0.113.15 [200, 302, 401] | 200, 302, 401 |
| external-databases | tcp external-db.example.invalid:5432 | - |
| authentik | https https://203.0.113.15 [200, 302, 401] | 200, 302, 401 |

## Backup / restore metadata

| Service | Profile | Runbook | Location | Tested |
|---|---|---|---|---|
| opnsense | opnsense-config | docs/operations/02-opnsense.md | - | - |
| truenas | truenas-config | docs/operations/06-acceptance-and-recovery.md | - | - |
| internal-dns | smartdns-config | docs/operations/06-acceptance-and-recovery.md | - | - |
| sing-box | sing-box-config | docs/operations/06-acceptance-and-recovery.md | - | - |
| harbor | harbor-data | docs/operations/06-acceptance-and-recovery.md | - | - |
| external-databases | external-database | docs/operations/06-acceptance-and-recovery.md | - | - |
| authentik | authentik-config | docs/operations/06-acceptance-and-recovery.md | - | - |

## Break-glass metadata

| Service | Method | Access path | Secret ref | Notes |
|---|---|---|---|---|
| opnsense | local-console | UI + physical console | op://foundation/opnsense/local-admin | - |
| truenas | local-console | UI + physical console | op://foundation/truenas/local-admin | - |
| internal-dns | local-admin | SSH + console | op://foundation/smartdns/admin | - |
| sing-box | local-admin | SSH + console | op://foundation/sing-box/admin | - |
| harbor | local-admin | UI + SSH | op://foundation/harbor/admin | - |
| external-databases | provider-console | ticketed support / local admin | ref:provider-managed | - |
| authentik | local-admin | UI + console | op://foundation/authentik/admin | - |

## Storage-network facts

| Name | VLAN | Subnet | Endpoint | Notes |
|---|---:|---|---|---|
| storage-vlan | 33 | 198.18.0.0/24 | 198.18.0.210 | PVE ↔ TrueNAS storage network. |

### Storage access

- node classes: vm
- storage networks: storage-vlan
- Notes: Declared storage access for this example's VM nodes.

## Warnings and known risks

- foundation-a: accepted single point of failure
- opnsense: accepted single point of failure for gateway and firewall.
