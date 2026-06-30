## Context

Roadmap information currently appears in multiple documentation files with different purposes:

```text
docs/decisions/iaas-automation-roadmap-research.md
  historical research, council guidance, and candidate roadmap direction

docs/review-remediation-roadmap.md
  detailed code-review remediation plan with completed and remaining phases

docs/architecture.md
  architecture facts plus inline documentation TODOs

openspec/changes/*
  actual active, completed, or archived implementation state
```

Readers need to know which document represents current planning. Older roadmap notes should remain available because they explain why work was prioritized, but they should not be mistaken for the live backlog when OpenSpec and implementation state have moved on.

## Goals / Non-Goals

**Goals:**

- Establish `docs/roadmap.md` as the current roadmap and backlog entrypoint.
- Preserve historical roadmap/research documents while labeling their status clearly.
- Summarize completed, complete-pending-archive, in-progress, planned, deferred, and superseded work at a high level.
- Make the source-of-truth precedence explicit when roadmap documents disagree.
- Keep roadmap status useful for humans without duplicating every OpenSpec task.

**Non-Goals:**

- Do not modify existing OpenSpec changes other than adding this new change.
- Do not archive active changes or update their task checkboxes.
- Do not implement any roadmap item.
- Do not reorganize the root `README.md` into an operator manual in this change; that belongs to a separate `reorganize-operator-documentation`-style change.
- Do not move large documentation files unless a later change scopes that explicitly.
- Do not change code, automation behavior, generated outputs, inventory, or live infrastructure workflows.

## Decisions

### Use one current roadmap index

Add `docs/roadmap.md` as the current planning entrypoint. It should not be a long-form research document. It should act as an index and status summary that points to detailed historical notes, active OpenSpec changes, runbooks, and docs.

Recommended sections:

```text
Status source and precedence
Status categories
Current priorities
In progress
Complete pending archive
Completed work
Planned backlog
Deferred / scale-triggered ideas
Historical roadmap references
```

### Treat OpenSpec as status evidence, not an edit target

Roadmap status should be derived from OpenSpec archived/active state and current repository behavior, but this change must not rewrite existing OpenSpec history or task state.

Recommended precedence:

```text
1. OpenSpec archived/active status and task completion
2. Current repository behavior and documented command surface
3. docs/roadmap.md current summary
4. historical roadmap/research documents
```

If older roadmap text says an item is "next" but the related change is already complete or archived, `docs/roadmap.md` should show the current state and the older document should be labeled historical or partially superseded.

### Keep historical detail, add status notes

Older roadmap and research documents should keep their original detail because they are useful as decision context. Add a short status note near the top instead of rewriting their historical narrative.

Example status-note pattern:

```text
Status: Historical research snapshot. Current execution status lives in docs/roadmap.md. Proposal queues and "next priority" notes below may be outdated.
```

For remediation plans that still contain useful open items:

```text
Status: Historical remediation plan with remaining backlog. Current planning status is summarized in docs/roadmap.md. Completed phases are retained for audit context.
```

### Separate current backlog from deferred ideas

The roadmap should not make scale-triggered ideas look like immediate work. Deferred ideas such as NetBox, Terragrunt, remote state, GitOps auto-apply, internal CI triggers, lightweight notifications, and high-privilege PVE hardware mapping bootstrap should be grouped separately with a "revisit when" condition.

### Keep status tables concise

Completed work should be summarized by outcome rather than copying every task checkbox from archived changes. Detailed task history remains in OpenSpec archives and historical roadmap files.

## Risks / Trade-offs

- **Risk: duplicated status drifts again.** Mitigation: document status-source precedence and keep `docs/roadmap.md` concise.
- **Risk: readers still use historical roadmap text.** Mitigation: add status notes and update `docs/README.md` to point to the current roadmap first.
- **Risk: scope expands into OpenSpec cleanup.** Mitigation: record complete-pending-archive items as backlog only; do not archive in this change.
- **Risk: this overlaps with root README reorganization.** Mitigation: keep operator manual restructuring as a separate future change.

## Open Questions

- Should old roadmap files eventually move under a `docs/planning/archive/` directory, or is status labeling sufficient for now?
- Should roadmap status tables be maintained manually, or should a future helper generate a partial status report from OpenSpec metadata?
