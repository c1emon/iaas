# Dependency review — 2026-09-10

This review covers the Ansible/OPNsense execution stack used by this change. It is
not a repository-wide toolchain upgrade or an appliance OS upgrade.

| Dependency | Current lock/pin | Reviewed target | Decision |
| --- | --- | --- | --- |
| oxlorg.opnsense | 26.1.11 | 26.1.11 | Keep; GitHub latest stable and Galaxy published versions agree |
| ansible | 14.3.1 | 14.4.0 | Upgrade dev package together with core |
| ansible-core | 2.21.3 | 2.21.4 | Upgrade exact runtime pin and lock together |
| community.general | runtime 13.3.0; dev unpinned | 13.4.0 | Align both Collection manifests |
| ansible.netcommon | runtime 8.6.1; dev unpinned | 8.6.2 | Align both manifests; retain switch regression checks |
| ansible.utils | 6.1.0 in runtime | 6.1.0 | Retain Ansible 14.4 dependency alignment |
| community.library_inventory_filtering_v1 | 1.1.5 in runtime | 1.1.5 | Retain Ansible 14.4 dependency alignment |
| ansible-lint | 26.8.0 | 26.8.0 | PyPI latest stable unchanged |
| httpx | 0.28.1 | 0.28.1 | PyPI latest stable unchanged |
| requests | 2.34.2 | 2.34.2 | PyPI latest stable unchanged |
| PyYAML | 6.0.3 | 6.0.3 | PyPI latest stable unchanged |
| paramiko | 5.0.0 | 5.0.0 | PyPI latest stable unchanged |

Ansible 14.4.0 declares `ansible-core~=2.21.4`; upgrading the dev package alone
conflicts with the current exact runtime core pin. Both require Python >=3.12,
consistent with the repository and image interpreter. The 2.21.4 changelog includes
URL authentication masking in URI/download-related operations and rejection of path
components in tempfile prefixes/suffixes. These improvements do not replace this
change's own safe-output and path validation contracts.

A temporary copy of pyproject.toml/uv.lock with only the proposed Ansible/core edits
resolved successfully using `uv lock --upgrade-package ansible --upgrade-package
ansible-core`. The resulting lock changed only those two package versions. No current
workspace dependency file or Python environment was upgraded. This proves dependency
resolution, not runtime or appliance compatibility.

The selected Collection targets match the official Ansible 14.4.0 build manifest;
they are an aligned candidate set, not a claim that every Collection was exhaustively
checked for its newest release. Pin explicitly installed shared Collections consistently
in developer and image manifests to avoid shadowing/drift. Reuse the existing locked
transitive dependencies; do not update all packages opportunistically.

After the repair phase passes on the currently pinned baseline, upgrade as a separate
implementation commit before the new capability code. The repair phase first pins the
main checkout CI to the shipped OpenTofu and Collection versions, eliminating its
`latest`/unpinned divergence without advancing versions. Run existing
synthetic offline validation, OPNsense tests and representative XikeOS/Ansible entrypoint
checks. Rebuild the final runtime image and smoke-test it with the updated dependency layer because its inputs
changed, then verify source-only capability edits reuse that layer. Do not claim image
compatibility from a host uv resolution. No release publication is implied.

Keep c1emon.xikeos, PVE/OpenTofu/Packer, uv, Python base image and system packages outside
this focused upgrade unless a concrete compatibility failure requires a new decision.
Do not track the OPNsense Collection development branch to obtain unrelated features.
The existing stable Collection already supports URL tables and network groups; neither
this dependency refresh nor the Collection release proves diagnostic API compatibility
with a particular appliance.

## Sources

- [OPNsense Collection release](https://github.com/O-X-L/ansible-opnsense/releases/tag/26.1.11) and the public Galaxy published-version API were checked directly.
- [Ansible 14.4.0](https://pypi.org/project/ansible/14.4.0/) and PyPI JSON metadata establish release, Python and core requirements.
- [Ansible 14.4.0 build manifest](https://raw.githubusercontent.com/ansible-community/ansible-build-data/main/14/ansible-14.4.0.deps) establishes the aligned Collection versions.
- [ansible-core 2.21.4 release notes](https://github.com/ansible/ansible/blob/v2.21.4/changelogs/CHANGELOG-v2.21.rst) describe the patch behavior.
- Stable versions of ansible-lint/httpx/requests/PyYAML/paramiko were checked through each project's public PyPI JSON metadata.
