# Design

Use `opnsense_validation.ports.rule_port` for check/plan and Python/Jinja conversion. Port alias content keeps its existing multi-member contract. Rules use explicit `start-end` ranges; lists with more than one selector require an explicit port alias even when numeric members are adjacent.

Reference: the upstream [Filter model](https://github.com/opnsense/core/blob/master/src/opnsense/mvc/app/models/OPNsense/Firewall/Filter.xml) defines source/destination ports as single PortField values with ranges and aliases enabled. The local pinned Collection's `helper/api.py` defines the protected Error/Response failure format.

Offline checks verify alias type when declaration/context facts are available; plan additionally verifies effective live references. A single document without alias facts validates reference syntax only. No alias is synthesized and no interval is inferred.

The fixed Collection emits validations in `API call failed | Error: ... | Response: ...`. Parse only the bounded Error literal (or structured validations), including failed loop items. Retain known field leaves and exact static model messages; discard values, UUIDs, response data, invocation, cookies and credentials. Unknown fields/reasons are explicitly redacted. `no_log` and mode 0600 remain mandatory. Forward safe details through Writer into result/recovery before stopping on failed save.

Execution `73a28250-7c43-4a30-813b-1dd4634a65c5` reportedly has partial writes and `pending_reconciliation`. This repair neither resolves nor replays it. Reconcile first, then produce and approve a fresh plan. No device evidence is claimed.

The authorized global logging follow-up uses one fixed public diagnostic catalog across the Ansible callback, protected subprocess capture, runtime JSON and Go launcher. Preserve ordinary task errors/warnings. For no_log tasks use Ansible's public outcome and warning-count metadata, never private uncensored callback results. Exact known static assertion gates can publish catalog reasons. OPNsense rescue tasks sanitize API validation/HTTP/connection details before publishing a diagnostic marker; their original protected evidence remains private.

Execution extracts only bounded, catalog-validated markers and emits a phase/exit fallback when a child fails without a recognized diagnostic. Runtime retains these summaries on success and failure; launcher reconstructs messages from its matching catalog and prints failed phases and warnings before collecting outputs. Unknown messages, arbitrary fields and credentials cannot cross this channel. Tests enforce both catalogs and cover grouped ordinary/protected, looped, API and subprocess paths; they do not qualify every external backend message or a live device.
