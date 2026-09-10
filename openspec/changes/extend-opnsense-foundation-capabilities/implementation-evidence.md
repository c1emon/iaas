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
