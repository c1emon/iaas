# Pinned interfaces and regression scope

Source baseline: OPNsense core tag **26.1.11**, Collection **26.1.11**. These are source contracts and synthetic fixtures, not observations from an appliance.

| Observation | Fixed operation | Shape and boundary |
| --- | --- | --- |
| Alias configuration | POST `/api/firewall/alias/search_item` | Bootgrid `rows/current/rowCount/total`; name/type/content describe configuration. Alternatively the Collection uses GET `alias/get` and normalizes enum/content fields. |
| Loaded alias table | POST `/api/firewall/alias_util/list/<name>` | Bootgrid rows contain `ip` and optional traffic counters. The controller accepts search pagination but the backend reads the table before paging. Empty output can also represent unavailable backend data; configuration is not loading proof. |
| Rule configuration | POST `/api/firewall/filter/search_rule` | Match UUID or the exact generated `iaas:opnsense:filter:<scope>:<slug>` description; reject duplicate identities. |
| Running rule correlation | GET `/api/diagnostics/firewall/list_rule_ids` | `items` of `id/descr`; absent or ambiguous required mapping is unsupported, not zero matches. |
| Recent firewall logs | GET `/api/diagnostics/firewall/log?limit=<bounded>` | Array of records; `rid`, `src/dst`, `srcport/dstport`, `protoname`, `interface`. Backend supports limit/digest, not IP/rule/time predicates. Filter a finite recent sample locally. An empty array does not distinguish missing log storage. |
| Connection states | POST `/api/diagnostics/firewall/query_states` | `rowCount/current/searchPhrase/ruleid` request; `rows/rowCount/total/current` response. Match exact returned `src_addr/dst_addr/src_port/dst_port/proto`, separately retain optional `nat_addr/nat_port/gateway/interface`. `current: 0` is the unavailable fallback, not page 1. |

The log backend may remove timezone information from `__timestamp__`; it cannot be assumed UTC. A time-filtered request needs an evaluable timestamp, otherwise returns unsupported. Optional missing counters/timestamps/translation do not invalidate an independently evaluable selector. No stream, refresh, flush, reload, state deletion, traffic generation or packet capture is a diagnostic operation.

## Permissions

The Core ACL defines `Firewall: Aliases` for alias get/search, `Diagnostics: PF Table IP addresses` for alias_util, `Diagnostics: Logs: Firewall: Live View` for logs, `Diagnostics: Firewall sessions` for list_rule_ids, and `Diagnostics: Show States` for query_states. Rule configuration uses `Firewall: Rules [new]` in the Firewall ACL. Some appliance privileges also permit mutation operations: this adapter's fixed operation allowlist does not turn the upstream credential into a read-only credential. Callers select credentials and TLS trust; no credentials are bundled or printed.

## Shared request/result contract

Request version 1 requires `schema_version` and one `kind`: alias, rule_logs, or states. Alias requires `alias_name`; logs require rule identity or source/destination literal IP; states require source/destination literal IP. TCP/UDP is required with port selectors. Unknown fields and selectors inappropriate for the kind are rejected before credentials. Rule scope/slug is a pair and cannot be mixed with UUID. A provided UTC RFC3339 time window must be ordered. Limit is an integer 1..1000 (default 100), detail opt-in defaults false.

Results carry version, target, observation time, kind, selector, status, counts and coverage/truncation. Error and unsupported counts are null, exits nonzero. Available optional metadata is separate from required observation availability. Details require an explicit protected output path beneath the diagnostics output root, disjoint from request/inventory/authored/implementation inputs; default output contains no observed rows or full URLs. Direct and Make entrypoints must share validation and reject missing/ambiguous/zero-host selection before network access.

## Alias ownership and regression boundary

Offline admission retains the six-field record and adds only URL table frequency and network groups. Frequency is checked against the pinned Collection's actual float/round conversion. Names follow the pinned AliasNameField syntax (at most 31 characters, a letter or single underscore prefix; no double underscore prefix). External DNS host leaves and literal addresses are not adopted; unsupported external dependency syntax is explicit. Effective desired definitions replace stale live ones before reachability checks. The server retains the final external-consumer deletion guard. API rule scope/slug, non-default gateways and caller-selected routing behavior are unchanged.

Synthetic response shapes are in `tests/fixtures/opnsense-capabilities/diagnostic-responses.json`; resource composition examples are adjacent. Tests use stateful inert API substitutes and pinned Collection helpers. They do not prove live list loading or traffic paths.

## Source references

- [Alias controller](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/AliasController.php), [alias table controller](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/AliasUtilController.php), [name field](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/mvc/app/models/OPNsense/Firewall/FieldTypes/AliasNameField.php).
- [Firewall diagnostics controller](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/mvc/app/controllers/OPNsense/Diagnostics/Api/FirewallController.php), [filter controller](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/FilterController.php).
- [Log reader](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/scripts/filter/read_log.py), [table reader](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/scripts/filter/list_table.py), [state parser](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/scripts/filter/lib/states.py), [state pagination](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/scripts/filter/list_states.py), [rule labels](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/scripts/filter/list_rule_ids.py).
- [Core ACL](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/mvc/app/models/OPNsense/Core/ACL/ACL.xml), [Firewall ACL](https://github.com/opnsense/core/blob/26.1.11/src/opnsense/mvc/app/models/OPNsense/Firewall/ACL/ACL.xml).
- [Collection alias helper](https://github.com/O-X-L/ansible-opnsense/blob/26.1.11/plugins/module_utils/helper/alias.py), [Collection alias module](https://github.com/O-X-L/ansible-opnsense/blob/26.1.11/plugins/module_utils/main/alias.py).
