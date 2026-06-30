## 1. Roadmap Inventory

- [x] 1.1 Review active OpenSpec changes and classify them as `in progress` or `complete pending archive` without modifying those changes.
- [x] 1.2 Review archived OpenSpec changes and summarize completed work by outcome rather than copying every task.
- [x] 1.3 Review existing roadmap/research documents under `docs/` and identify current, historical, deferred, and superseded content.
- [x] 1.4 Identify documentation-only TODOs that belong in a roadmap/backlog summary rather than the operator manual.

## 2. Current Roadmap Document

- [x] 2.1 Add `docs/roadmap.md` as the current roadmap and backlog index.
- [x] 2.2 Define status-source precedence: OpenSpec/current behavior first, historical roadmap text last.
- [x] 2.3 Define status categories: done, complete pending archive, in progress, planned, deferred, and superseded.
- [x] 2.4 Add current priorities and in-progress work.
- [x] 2.5 Add complete-pending-archive work without archiving or editing existing changes.
- [x] 2.6 Add completed work summaries with links to relevant docs or OpenSpec archives where useful.
- [x] 2.7 Add planned backlog items such as OPNsense vars validation, OpenTofu consistency guards, documentation cleanup, and OpenSpec archive cleanup.
- [x] 2.8 Add deferred / scale-triggered ideas with revisit conditions.
- [x] 2.9 Add historical roadmap references so readers can find the detailed context.

## 3. Historical Document Labeling

- [x] 3.1 Add a status note to `docs/review-remediation-roadmap.md` explaining that it is a historical remediation plan with remaining backlog summarized in `docs/roadmap.md`.
- [x] 3.2 Add a status note to `docs/decisions/iaas-automation-roadmap-research.md` explaining that it is a historical research snapshot and not the current execution queue.
- [x] 3.3 Avoid rewriting historical detail except where wording would actively mislead readers after the status note.

## 4. Documentation Index

- [x] 4.1 Update `docs/README.md` with a Planning section.
- [x] 4.2 Link `docs/roadmap.md` as the current roadmap source.
- [x] 4.3 Keep older roadmap/research links, clearly labeled as historical or detailed context.

## 5. Validation

- [x] 5.1 Run `uv run openspec validate consolidate-documentation-roadmaps`.
- [x] 5.2 Review Markdown links touched by this change.
- [x] 5.3 Confirm the diff does not modify existing OpenSpec changes outside `openspec/changes/consolidate-documentation-roadmaps/`.
- [x] 5.4 Confirm the diff does not change application code, scripts, Make targets, Ansible playbooks, OpenTofu configuration, inventory, generated outputs, or live infrastructure behavior.
