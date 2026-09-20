## ADDED Requirements

### Requirement: Safe structured failure descriptions
Common primitives SHALL provide an immutable diagnostic description with a controlled component, stable reason code and optional safe field context or numeric HTTP status. Its serialized form SHALL omit arbitrary input, backend messages, exception chains and dynamic sensitive keys. Adoption SHALL preserve existing exception compatibility and SHALL not impose a shared domain status machine or retry policy.

#### Scenario: Caller handles failure without parsing prose
- **WHEN** an adopted adapter emits a classified failure
- **THEN** internal callers can inspect its component and stable code independently of the human message
- **AND** existing callers catching the original exception type continue to work

#### Scenario: Backend payload contains secret-like values
- **WHEN** an error originates from a payload containing credentials or dynamic private keys
- **THEN** the diagnostic export contains only approved fields and no payload values or exception context

#### Scenario: CLI remains compatible
- **WHEN** an existing validation CLI receives an error carrying a diagnostic description
- **THEN** its established prefix, failure exit code and safe formatting remain compatible
- **AND** it does not automatically print a traceback or diagnostic JSON
