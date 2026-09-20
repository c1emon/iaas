## ADDED Requirements

### Requirement: Explicit provider conversion boundary
The workflow SHALL convert supported native API and fixed Collection representations through a reusable pure-data boundary for the existing seven resource classes. Known boolean fields SHALL use the common deterministic conversion contract, with resource-field-specific exceptions for established native empty or inverted representations. Conversion SHALL NOT perform device operations, infer write authorization, relax standard declaration admission or determine live reference existence.

#### Scenario: Provider boolean differs from declaration syntax
- **WHEN** a supported provider field contains `"No"`, `"off"` or `"0"`
- **THEN** the field is converted to boolean false for readback
- **AND** a desired declaration that violates the existing strict boolean contract remains invalid before writes

#### Scenario: Native inverted empty flag
- **WHEN** an interface group returns `nogroup=""` under the established native field contract
- **THEN** its canonical `gui_group` value is true
- **AND** the same empty string is not accepted for an unrelated boolean or selector flag

#### Scenario: Gateway read and requested inspection agree on boolean semantics
- **WHEN** an explicitly requested existing gateway monitor-route check observes equivalent native monitor flags `0`, `"0"`, `False`, `"No"` or `"off"`
- **THEN** configuration readback and monitor-route observation apply the same boolean meaning and route-retrieval eligibility
- **AND** missing or invalid monitor flags such as `"fasle"` or `" false "` leave the relevant observation unknown rather than silently making the check not applicable
- **AND** conversion does not add optional inspection to the default workflow

### Requirement: Field-aware conversion preserves values and ambiguity
Conversion SHALL apply only the rules declared for the resource and field. It SHALL preserve identifier and descriptive strings, field absence and unsupported configuration information. It SHALL distinguish missing, null, empty and false/zero values rather than using truthiness. Multiple representations of one field SHALL be accepted together only when their converted semantics agree; conflicting sources SHALL fail explicitly. Unknown fields SHALL NOT disappear through model parsing, and resource-specific metadata exceptions SHALL NOT become global exclusions.

#### Scenario: Numeric-looking description
- **WHEN** a provider returns description or a string identifier `"001"`
- **THEN** the value remains the string `"001"`
- **AND** conversion to a number occurs only for an explicitly numeric target field

#### Scenario: Equivalent and conflicting aliases
- **WHEN** native and canonical forms of the same boolean field are both present
- **THEN** equivalent values after field conversion and any defined inversion are accepted once
- **AND** conflicting values produce an incomplete observation instead of selecting one by priority

#### Scenario: Native and canonical values are not inverted twice
- **WHEN** a provider row supplies only `disabled="0"`, only `enabled=True`, or both equivalent forms
- **THEN** each case produces canonical `enabled=True`
- **AND** all recognized source forms are consumed without leaving an extra value that can override the exported boolean

#### Scenario: Unknown zero is configuration information
- **WHEN** an identified object contains an unknown configuration field with `0` or `False`
- **THEN** the value is retained for expressibility assessment and prevents an unsupported standard reconstruction
- **AND** known metadata is excluded only under that resource's established metadata policy

#### Scenario: Absent and explicit null differ
- **WHEN** a provider field is omitted, explicitly null, or explicitly false
- **THEN** the adapter applies that field's declared policy separately to each representation
- **AND** it does not substitute a missing-field default for an invalid explicit value

### Requirement: Selector and collection shapes are decoded without guessing
Dictionary selectors SHALL use selected keys as identifiers. List selectors SHALL prefer an explicit key and use a value only when the key is absent. Selection flags SHALL use deterministic boolean conversion; malformed flags, malformed items, duplicate selected identifiers and multiple selections for a single-valued field SHALL fail. CSV, newline and member-map forms SHALL be accepted only for fields declaring those shapes. Sorting SHALL be limited to established set-like fields, and conversion SHALL NOT silently deduplicate malformed input.

#### Scenario: Selector has separate identifier and label
- **WHEN** a selected option has key `wan` and display value `WAN display`
- **THEN** the canonical identifier is `wan`
- **AND** an invalid explicit key is not replaced with the display value

#### Scenario: Invalid single selection
- **WHEN** a single-valued field has two selected options, a missing selected flag or a selected flag of `"fasle"`
- **THEN** the observation remains incomplete and cannot establish absence or unchanged state

#### Scenario: Resource-specific list shapes
- **WHEN** a filter network or port field returns supported CSV, or an Alias returns its supported content member map
- **THEN** each becomes the existing resource-specific standard representation
- **AND** descriptions and unrelated scalar fields are not split, and Alias member maps are not treated as selector options

### Requirement: Conversion preserves observation and execution contracts
Conversion SHALL preserve the existing public observation, candidate, comparison and recovery structures. A complete enumeration SHALL retain identifiable built-in and unsupported native objects even when their configuration is not expressible; those objects SHALL remain unknown/manual-required rather than absent. Malformed enumeration, selectors or identity ambiguity SHALL retain incomplete status. Configured defaults and canonical ordering SHALL remain consistent across readback, validated desired state, verification and recovery. Conversion errors SHALL follow the safe common error boundary.

#### Scenario: Native object cannot be managed
- **WHEN** a complete list contains an internal Alias, a gateway with a usable native identity but no expressible address, or an identifiable group with unsupported empty members
- **THEN** the object remains observed with its identity and an unavailable standard configuration
- **AND** it is not filtered out or converted into a deletion candidate

#### Scenario: Invalid configuration preserves usable identity and references
- **WHEN** a completely enumerated rule lacks action or has an invalid ordinary boolean such as `enabled="fasle"`, while its identity and reference to Alias `NETS` remain reliably decodable
- **THEN** the enumeration remains complete and the object retains its identity and reference with configuration null and manual-required recovery
- **AND** the reference continues to prevent deletion of `NETS`, while that configuration failure alone does not block a plan for unrelated objects

#### Scenario: Readback normalization does not reapply desired admission
- **WHEN** an existing block or reject rule passes readback structure and expressibility checks without the declaration context required to authorize creating that rule
- **THEN** canonical normalization preserves its observed action without running creation or desired-state safety admission
- **AND** a newly supplied desired declaration still requires the existing full admission checks

#### Scenario: Equivalent inputs across workflow paths
- **WHEN** supported native and Collection forms represent the same valid standard configuration
- **THEN** they produce equal existing canonical configuration for diff and verify
- **AND** recovery retains actual before-state semantics without newly invented fields or lossy values

#### Scenario: Minimal deletion declaration
- **WHEN** a valid `state=absent` declaration contains only the existing required identity fields
- **THEN** normalization preserves that deletion declaration without requiring present-only fields or adding present-state defaults

#### Scenario: Safe readback failure
- **WHEN** model conversion fails on a sensitive provider payload
- **THEN** public reports contain only a controlled error category and safe field context
- **AND** no raw value, validation input, dynamic sensitive key or exception chain is included
