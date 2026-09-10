## ADDED Requirements

### Requirement: Operator-reviewable switch preview
Switch planning SHALL expose a sanitized resource-change summary before mutation and MAY export protected detail to an explicit caller path.

#### Scenario: Operator runs plan only
- **WHEN** native resource modules return a preview
- **THEN** the operator SHALL be able to identify affected objects and proposed changes or an explicit no-change result
- **AND** counts alone SHALL NOT constitute the review artifact
- **AND** planning SHALL NOT mutate the device

#### Scenario: Operator requests a detailed plan file
- **WHEN** an explicit detail-output path is provided
- **THEN** the report SHALL use existing path guards and protected directory/file modes 0700/0600
- **AND** console output and exported content SHALL exclude credentials and sensitive raw device material
