## Why

The `docs/` tree contains roadmap-style documents that now mix current planning, historical research, completed work, deferred ideas, and remaining backlog. Some items that older roadmap notes describe as next priorities have since been implemented, archived, or superseded by later OpenSpec changes. Operators need a single current planning entrypoint that makes status clear without rewriting or deleting the historical context that explains earlier decisions.

This change is documentation-only. It should organize roadmap information for readers, not implement any roadmap item or mutate existing OpenSpec change state.

## What Changes

- Add `docs/roadmap.md` as the current roadmap and backlog index.
- Update `docs/README.md` so readers find the current roadmap first and understand which roadmap/research documents are historical references.
- Add status notes to older roadmap/research documents that are historical or partially superseded.
- Classify roadmap items into clear statuses such as done, complete pending archive, in progress, planned, deferred, and superseded.
- Record that OpenSpec archived/active status and current repository behavior take precedence over older roadmap text.
- Keep completed active OpenSpec changes as documentation status only; do not archive, edit, or retask them in this change.

## Capabilities

### New Capabilities

- `documentation-roadmap-index`: Provides a current documentation roadmap index and status model for planning documents under `docs/`.

### Modified Capabilities

- None.

## Impact

- Planned repository areas:
  - `docs/roadmap.md`
  - `docs/README.md`
  - status notes in existing roadmap/research documents under `docs/`
- Explicit non-impact:
  - No application code, scripts, Make targets, Ansible playbooks, OpenTofu configuration, inventory, generated outputs, or live infrastructure behavior changes.
  - No modifications to existing OpenSpec change tasks, proposal/design/spec content, archive state, or active change status.
  - No implementation of any roadmap item.
