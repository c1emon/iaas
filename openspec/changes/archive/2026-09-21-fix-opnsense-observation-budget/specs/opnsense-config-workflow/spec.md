## ADDED Requirements

### Requirement: Native activation status tolerates protocol whitespace
The fixed activation adapter SHALL trim surrounding whitespace and normalize case before comparing a native response status to `ok`. It SHALL continue rejecting missing, empty and other statuses, SHALL NOT infer success from arbitrary nonempty output, and SHALL NOT automatically retry activation.

#### Scenario: Configd returns success with trailing newlines
- **WHEN** a native activation returns `OK` followed by two newlines
- **THEN** the adapter recognizes the native success response
- **AND** configuration and business evidence retain their existing separate scope

#### Scenario: Native activation does not report success
- **WHEN** status is missing, blank, or an error message
- **THEN** activation remains failed rather than being accepted after normalization
