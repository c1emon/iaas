# Implementation evidence

## PVE runtime repairs (0.1–0.3)

- `uv run pytest -q tests/python/test_pve_make_workflow.py tests/python/test_pve_snippet_wrapper.py tests/python/test_pve_inventory_phase3.py`: 109 passed (2026-09-10).
- Real Make recipes run outside the checkout with inherited `MAKEFLAGS=-j8` and inert command substitutes; plan/apply check freshness first, apply orders render/upload/verify, and destroy finds recursive backup targets.
- Upload/verify reject missing or mismatched current tfvars before SSH; existing matching manifest/checksum cases still pass.
- Failed PVE storage resolution exits before creating a directory or writing a snippet; no guessed destination remains.
- This is local software evidence, not live PVE deployment qualification. Remaining stage 0 repairs and its final offline/image gate are still pending.

## K3s observed identity repairs (0.7 and part of 0.6)

- Handoff: 20 tests passed across `test_platform_handoff_tls.py`, `test_platform_handoff_playbook.py`, and `test_platform_handoff.py`. Disposable local X.509 certificates confirm DNS/IPv4/IPv6 SAN selection and wrong-identity/wrong-CA rejection. Connection formatting follows [OpenSSL s_client](https://docs.openssl.org/3.0/man1/openssl-s_client/); authoritative guest CA and Make's same-scope verification remain in place.
- Preflight: 34 tests passed across `test_k3s_first_boot.py`, `test_k3s_preflight.py`, and `test_k3s_template_whitespace.py`. Actual Ansible fact-building tasks parse capability bits and exact address/interface pairs; zero bits, address prefixes and wrong interfaces cannot satisfy the expected observation.
- `ansible-lint` passed for the preflight role and handoff playbook (5 files). These are local synthetic observations and certificate checks; no appliance or cluster was contacted.
- Task 0.6 remains open: upgrade drift and exact post-upgrade version/readiness checks are still pending. Tasks 0.4–0.5 are also pending.

## OPNsense admission and activation recovery (0.8–0.9)

- `uv run pytest -q tests/python/test_opnsense_validation.py`: 30 passed. Current Collection primitive bounds are enforced before credentials/writes; a bad second gateway rejects the batch. Priority/data length zero and representative upper-bound failures are covered.
- `uv run pytest -q tests/ansible/test_opnsense_recovery.py`: 8 passed. Actual activation blocks run with inert command substitutes for all four managed resource kinds, covering no-op, failed reload then explicit no-change retry, check mode, invalid string flags and a preceding partial-CRUD failure. Direct Ansible destination inversion checks agree with Python cases.
- Ansible lint passed for all four managed playbooks plus imported credential preflight (5 files). No appliance API was contacted; saved/active behavior on real appliances is not qualified here.

## Foundation contracts, probes and generic artifact paths (0.11–0.13)

- Foundation inventory/probe and acquisition tests: 51 passed across `test_foundation_inventory.py`, `test_foundation_probes.py`, and `test_k3s_mirror_acquisition.py`. Cases include schema 1 compatibility, schema 2 with no storage, optional VLAN/node classes, dependency cycles/closure/order, relative CA paths, real loopback HTTPS trust/identity failures, all six DNS types, malformed packets and compression loops. Test servers are shut down and temporary certificate files are pytest-owned.
- K3s model, acquisition admission and template regressions: 89 passed before the three additional exact binary version cases were added; those three are included in the 51-test run above. No artifact host was contacted: real Ansible assertion/version tasks use local executable substitutes. Artifact URL path conventions are caller-owned, while pinned checksum acquisition and exact reported version remain required.
- Ansible lint passed for the acquisition role (3 files); pyright reports 0 errors (existing missing `scripts` include-path notice remains). Generic foundation fixture and generated documentation now use schema 2 with unambiguous external-host/service names.
- These results do not complete K3s lifecycle admission/staging repairs or the stage 0 final synthetic offline/image gate. No live infrastructure mutation or release publication occurred.
