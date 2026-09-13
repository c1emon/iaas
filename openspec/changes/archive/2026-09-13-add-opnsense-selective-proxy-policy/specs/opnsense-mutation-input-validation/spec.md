## MODIFIED Requirements

### Requirement: Provider-compatible existing resource admission

Before writes, the runtime SHALL validate every desired resource against locally provable field semantics and the pinned Collection's basic primitive constraints. Supported native source/destination inversion SHALL require exactly one target. Offline and Ansible-loaded admission SHALL agree on primitive type and inversion semantics without introducing caller-specific routing rules.

#### Scenario: A later gateway record violates a known numeric bound
- **WHEN** a desired batch includes a record such as latency_low 0, loss_high 100 or interval 10000 that the pinned 26.1.11 Collection rejects
- **THEN** the entire batch SHALL fail local validation before credentials, API access or earlier-record mutation
- **AND** Python and Ansible admission SHALL agree on supported numeric and inversion semantics

#### Scenario: Dependency constraints are refreshed
- **WHEN** the explicitly installed Collection baseline changes
- **THEN** representative boundary tests SHALL compare the accepted primitive ranges with that baseline
- **AND** the runtime SHALL NOT copy the entire server validation model or relax default-gateway ownership

#### Scenario: Inversion contains multiple targets
- **WHEN** source or destination inversion specifies more than one target
- **THEN** offline and direct-playbook validation SHALL reject the declaration before credential access or mutation
- **AND** one valid alias target SHALL remain eligible for the normal resource and safety checks

#### Scenario: Ansible preserves a valid primitive with metadata
- **WHEN** Ansible loads a valid resource whose primitive values carry engine metadata
- **THEN** the execution adapter SHALL preserve their primitive meaning and apply the same domain checks as offline validation
- **AND** string-to-number or string-to-boolean coercion and acceptance of a boolean as an integer SHALL remain prohibited

## ADDED Requirements

### Requirement: Generic filter resource validation context

The filter-rule document SHALL support optional `opnsense_filter_rule_context` containing only `interface_networks`, an interface-to-CIDR-list mapping, and `aliases`, standard alias declarations. The context SHALL be independent of policy or generator identity and SHALL contain no admission-bypass flag. Context shape, types, address families and local alias dependencies SHALL be validated before credentials or mutation. When corresponding declarations are also supplied in the selected input set, inconsistent context SHALL be rejected.

#### Scenario: Consistent caller-derived context
- **WHEN** the caller supplies context derived from its selected alias declarations and reviewed interface-network facts
- **THEN** validation SHALL use only statically provable address coverage for the relevant rule families
- **AND** it SHALL NOT resolve DNS, download URL tables, access the appliance or claim that the supplied facts are current on the appliance

#### Scenario: Context conflicts with selected declarations
- **WHEN** supplied context disagrees with corresponding alias or interface-network declarations available in the selected inputs
- **THEN** validation SHALL fail rather than selecting one copy by load order

#### Scenario: Context is malformed or requests a bypass
- **WHEN** context contains unknown fields, invalid CIDRs, invalid alias declarations or a flag asserting that a rule is safe
- **THEN** validation SHALL reject the document before credentials and writes

#### Scenario: An external reference is not locally declared
- **WHEN** a syntactically valid alias reference is absent from the local input set
- **THEN** the existing unresolved-external-reference and explicit online-resolution contract SHALL remain in force
- **AND** the unknown reference SHALL NOT itself count as static coverage evidence or require complete appliance inventory
