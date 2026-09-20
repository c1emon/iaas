# python-common-primitives Specification

## Purpose
Define an explicit Python common primitive layer for domain-neutral helper code
shared across repository-owned inventory tooling without coupling domain packages
to each other.

## Requirements

### Requirement: Explicit common primitive package
The system SHALL provide an explicit Python common primitive package for helper code that is shared across repository-owned inventory tooling.

#### Scenario: Inventory tools use shared primitive helpers
- **WHEN** PVE inventory or service metadata code needs shared validation errors, assertion helpers, basic YAML/JSON/text I/O, CLI validation failure handling, generated-output content comparison, or Markdown table-cell escaping
- **THEN** those shared helpers SHALL be available from `iaas_automation.common`
- **AND** callers SHALL NOT need to import domain-neutral helpers through `iaas_automation.pve_inventory` or `iaas_automation.services_inventory`

#### Scenario: Common helpers remain domain-neutral
- **WHEN** helper code is added to the common primitive layer
- **THEN** it SHALL be limited to domain-neutral primitives such as errors, basic type/schema assertions, file I/O, CLI boundary helpers, or Markdown table-cell escaping
- **AND** it SHALL NOT encode PVE cluster policy, VM schema policy, service endpoint policy, OPNsense policy, OpenTofu resource shape, Ansible inventory domain rules, cloud-init artifact rules, or online runtime adapter behavior

### Requirement: Dependency direction remains acyclic and domain-safe
The system SHALL keep inventory domain packages dependent on common primitives rather than on each other for shared helper behavior.

#### Scenario: Services inventory no longer imports PVE internals
- **WHEN** service metadata validation, rendering, I/O, or CLI code uses shared helper behavior
- **THEN** it SHALL import that helper behavior from `iaas_automation.common`
- **AND** it SHALL NOT import PVE inventory internals for domain-neutral helper behavior

#### Scenario: Common primitives avoid domain imports
- **WHEN** Python imports for the common primitive layer are evaluated
- **THEN** `iaas_automation.common` SHALL NOT import from `iaas_automation.pve_inventory` or `iaas_automation.services_inventory`
- **AND** common primitive modules SHALL be reusable by both domains without creating import cycles

### Requirement: Refactor preserves inventory tool behavior
The system SHALL preserve existing operator-visible behavior while moving primitive helper ownership.

#### Scenario: Existing offline checks remain safe
- **WHEN** operators or CI run the repository's default offline validation path after the primitive extraction
- **THEN** it SHALL remain offline-safe
- **AND** it SHALL NOT require PVE API access, OPNsense API access, switch access, SSH access, 1Password access, runtime secrets, or mutation-capable infrastructure credentials

#### Scenario: Generated outputs remain stable
- **WHEN** source-of-truth inventory files are unchanged and generated-output checks are run after the primitive extraction
- **THEN** generated PVE outputs and generated service documentation SHALL remain unchanged except for explicitly documented intentional changes
- **AND** stale or missing generated outputs SHALL continue to be reported with actionable file paths

#### Scenario: CLI validation failures remain operator-readable
- **WHEN** PVE inventory or services inventory CLI commands fail due to expected validation errors after the primitive extraction
- **THEN** they SHALL exit with status `1`
- **AND** they SHALL print a concise validation failure to stderr with the existing `FAIL validation: ` prefix
- **AND** they SHALL NOT print a Python traceback for expected validation failures
- **AND** they SHALL NOT disclose runtime secrets or credential material

### Requirement: Deterministic shared boolean conversion
The common primitive layer SHALL provide side-effect-free boolean conversion for callers that explicitly opt into representation conversion. For JSON-compatible inputs it SHALL accept booleans, numeric zero and one including `0.0` and `1.0`, and case-insensitive strings `0`, `1`, `false`, `true`, `no`, `yes`, `off`, `on`, `n`, `y`, `f` and `t`, returning a real boolean. It SHALL reject unrecognized spellings, other numeric values, null, empty strings, surrounding whitespace and containers. It SHALL NOT use generic truthiness, silently correct spelling, choose defaults, or embed domain-specific empty-value policy. Strict declaration validation SHALL remain distinct from this opt-in conversion.

#### Scenario: Equivalent false representations
- **WHEN** callers convert `0`, `"0"`, `False`, `"false"`, `"False"` or `"No"`
- **THEN** every conversion returns boolean false
- **AND** equivalent true representations return boolean true

#### Scenario: Misspelling and ambiguous input
- **WHEN** callers convert `"fasle"`, `" false "`, `""`, null, `2` or an empty container
- **THEN** conversion fails explicitly without substituting false, true or a caller default

#### Scenario: Domain-specific empty value
- **WHEN** one device field defines an empty string as a neutral flag value
- **THEN** the device adapter supplies that explicit field policy outside the common boolean primitive
- **AND** empty strings remain invalid for other callers unless those callers separately declare a policy

### Requirement: Safe conversion failure boundary
Shared conversion failures SHALL expose a deterministic error category and safe field context without raw input values, credential material or backend exception content. Conversion SHALL NOT mutate caller input or perform I/O.

#### Scenario: Invalid value includes sensitive input
- **WHEN** a failed conversion contains a secret-like input value or a value embedded in a dynamic mapping key
- **THEN** caller-visible errors omit that value and unsafe dynamic path content
- **AND** callers can distinguish conversion failure from successful false or empty output

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
