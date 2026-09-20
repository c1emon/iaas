## ADDED Requirements

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
