## ADDED Requirements

### Requirement: Current roadmap entrypoint
The documentation SHALL provide a single current roadmap entrypoint for repository planning status.

#### Scenario: Reader looks for the current roadmap
- **WHEN** a reader opens the documentation index or planning documentation
- **THEN** the reader SHALL be directed to `docs/roadmap.md` as the current roadmap and backlog index
- **AND** older roadmap or research documents SHALL NOT be presented as the current execution queue

#### Scenario: Roadmap summarizes status
- **WHEN** `docs/roadmap.md` describes repository planning work
- **THEN** it SHALL classify work into clear status categories such as done, complete pending archive, in progress, planned, deferred, and superseded
- **AND** it SHALL summarize completed work by outcome rather than duplicating every historical task checkbox

### Requirement: Roadmap status precedence
The documentation SHALL state how roadmap status is determined when historical notes disagree with current repository state.

#### Scenario: Historical roadmap text conflicts with current state
- **WHEN** older roadmap text says an item is a next priority or future candidate
- **AND** OpenSpec or current repository behavior shows the item is complete, active, deferred, or superseded
- **THEN** `docs/roadmap.md` SHALL represent the current state
- **AND** the older roadmap text SHALL be treated as historical context

#### Scenario: Status sources are listed
- **WHEN** `docs/roadmap.md` explains status determination
- **THEN** it SHALL prefer OpenSpec archived/active state and current repository behavior over historical roadmap or research prose
- **AND** it SHALL make clear that this documentation change does not edit existing OpenSpec change state

### Requirement: Historical roadmap labeling
The documentation SHALL label older roadmap and roadmap-research documents whose planning queues are no longer current.

#### Scenario: Reader opens an older roadmap document
- **WHEN** a reader opens an older roadmap or remediation plan that contains completed, deferred, or superseded items
- **THEN** the document SHALL include a status note near the top
- **AND** the note SHALL point to `docs/roadmap.md` for current status

#### Scenario: Historical detail remains useful
- **WHEN** older roadmap documents contain decision context, research, or detailed remediation notes
- **THEN** that detail SHALL remain available unless a separate change explicitly moves or archives it
- **AND** this change SHALL avoid rewriting historical detail merely to restate current status

### Requirement: Deferred ideas separated from current backlog
The current roadmap SHALL distinguish immediate/planned work from scale-triggered or intentionally deferred ideas.

#### Scenario: Roadmap lists future platform ideas
- **WHEN** ideas such as NetBox, Terragrunt, remote state, GitOps auto-apply, internal CI trigger paths, notification helpers, or high-privilege PVE hardware mapping bootstrap are listed
- **THEN** they SHALL appear as deferred or scale-triggered ideas unless they have an active OpenSpec change
- **AND** the roadmap SHALL include a short reason or revisit condition where practical

### Requirement: Roadmap consolidation is documentation-only
The roadmap consolidation SHALL NOT change infrastructure behavior or existing OpenSpec history.

#### Scenario: Change is implemented
- **WHEN** this change is implemented
- **THEN** it SHALL limit repository modifications to the new change artifacts and documentation under `docs/`
- **AND** it SHALL NOT modify application code, scripts, Make targets, Ansible playbooks, OpenTofu configuration, inventory, generated outputs, or live infrastructure behavior
- **AND** it SHALL NOT archive, retask, or edit existing OpenSpec changes outside the new change directory

#### Scenario: Active completed changes are identified
- **WHEN** active OpenSpec changes appear implementation-complete
- **THEN** the roadmap MAY list them as complete pending archive
- **AND** this change SHALL NOT archive those changes or update their task checkboxes
