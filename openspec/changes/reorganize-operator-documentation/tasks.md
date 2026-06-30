## 1. Documentation Surface Inventory

- [ ] 1.1 Review root `README.md` and identify content that belongs in an operator manual versus detailed docs.
- [ ] 1.2 Review `docs/README.md` and identify missing navigation groups.
- [ ] 1.3 Review existing module README files for PVE OpenTofu, Packer, Ansible, OPNsense, switches, and scripts to avoid duplicating details unnecessarily.
- [ ] 1.4 Confirm `docs/roadmap.md` exists or is planned by `consolidate-documentation-roadmaps` before linking it as the current roadmap entrypoint.

## 2. Root Operator Manual

- [ ] 2.1 Rewrite root `README.md` as an operator manual.
- [ ] 2.2 Add a repository capability map with links to detailed docs.
- [ ] 2.3 Document source-of-truth files under `inventory/` and related operator-authored inputs.
- [ ] 2.4 Document committed generated outputs and their sensitivity expectations at a summary level.
- [ ] 2.5 Document safety classes: offline-safe, online read-only, and mutation-capable.
- [ ] 2.6 Add concise common workflows for validation, generation, PVE health/preflight, PVE VM lifecycle, PVE guest verification, PVE template build, OPNsense, switches, and service metadata.
- [ ] 2.7 Add runtime parameter and secret-injection summary tables.
- [ ] 2.8 Add a documentation map pointing to `docs/`, module README files, and generated references.
- [ ] 2.9 Remove or move excessive implementation history from root README by linking to detailed docs instead.

## 3. Documentation Index

- [ ] 3.1 Expand `docs/README.md` into a grouped documentation index.
- [ ] 3.2 Include sections for planning, architecture, operations/runbooks, PVE, OPNsense, switches, service metadata, generated references, decisions, and historical context.
- [ ] 3.3 Label current versus historical planning documents consistently with the roadmap consolidation change.
- [ ] 3.4 Ensure `docs/README.md` points readers back to the root operator manual as the start-here entrypoint.

## 4. Navigation Consistency

- [ ] 4.1 Add or adjust short navigation links in module README files only where needed to avoid orphaned detailed docs.
- [ ] 4.2 Avoid large documentation moves unless they are explicitly reviewed as a separate change.
- [ ] 4.3 Keep module README files focused on module-specific usage, parameters, and safety notes.

## 5. Validation

- [ ] 5.1 Run `uv run openspec validate reorganize-operator-documentation`.
- [ ] 5.2 Review Markdown links touched by this change.
- [ ] 5.3 Confirm the diff does not change application code, scripts, Make targets, Ansible playbooks, OpenTofu configuration, inventory, generated outputs, or live infrastructure behavior.
- [ ] 5.4 Confirm this change does not archive OpenSpec changes or implement roadmap items.
