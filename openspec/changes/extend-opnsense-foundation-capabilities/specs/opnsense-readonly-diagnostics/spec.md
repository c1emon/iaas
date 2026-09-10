## ADDED Requirements

### Requirement: Explicit scoped diagnostic entrypoints
The runtime SHALL expose `opnsense-diagnose` and a direct Ansible diagnostic playbook for alias loading, rule logs and connection states using caller-owned target selection and a validated request.

#### Scenario: A valid diagnostic request is supplied
- **WHEN** the caller selects one target and a schema-version-1 request with an alias name, rule/log selector or source/destination state selector
- **THEN** the runtime SHALL execute only that explicit diagnostic kind and scope using caller-injected API credentials
- **AND** the Make and direct playbook paths SHALL validate an exact selected inventory host and reject expansion to zero or multiple hosts before API access
- **AND** the OCI entrypoint SHALL explicitly allow the new operation
- **AND** it SHALL require no default environment, application, gateway or list provider

#### Scenario: A request is invalid or unscoped
- **WHEN** the target or selector is missing, fields conflict, types/addresses are invalid, or the record limit is outside integer 1..1000
- **THEN** the runtime SHALL fail before credential or API access
- **AND** an omitted record limit SHALL default to 100 for otherwise valid requests

### Requirement: Diagnostics cannot mutate appliance state
Diagnostic entrypoints SHALL use only documented read-only operations and SHALL remain outside the aggregate offline gate.

#### Scenario: A diagnostic is executed
- **WHEN** any supported diagnostic kind runs
- **THEN** it SHALL NOT write configuration, reload rules, refresh or flush aliases, enable logs, reset counters, kill states, start packet capture or generate test traffic
- **AND** it SHALL NOT accept arbitrary endpoints, HTTP methods or shell commands from request data

#### Scenario: A read-only query uses POST
- **WHEN** an upstream API requires POST for a query
- **THEN** the adapter SHALL use a fixed verified read-only operation and validated query parameters
- **AND** tests SHALL demonstrate the absence of mutation calls

### Requirement: Observations preserve evidence boundaries
The runtime SHALL report versioned, timestamped diagnostic results with scope, counts, available metadata and explicit coverage limits.

#### Scenario: Alias loading is inspected
- **WHEN** an alias diagnostic succeeds
- **THEN** it SHALL distinguish configured alias metadata from loaded table observations
- **AND** it SHALL expose available entry count and update time without inventing missing values or interpreting an empty table as successful refresh

#### Scenario: Rule logs are inspected
- **WHEN** a log diagnostic succeeds
- **THEN** it SHALL report matches for the selected criteria within the available bounded records
- **AND** it SHALL correlate managed rule identity only when API evidence provides an unambiguous mapping
- **AND** a rule-selected query without the necessary identity correlation SHALL be unsupported with null counts, never ok with zero matches
- **AND** an IP-selected query MAY succeed with optional rule correlation explicitly unavailable
- **AND** supplied selectors SHALL be combined with AND semantics and never silently omitted
- **AND** missing logging or correlation SHALL NOT be represented as proof that a rule never matched

#### Scenario: Connection states are inspected
- **WHEN** a state diagnostic succeeds
- **THEN** it SHALL expose available matching connection tuple, translation, interface and route observations
- **AND** unavailable fields SHALL have explicit availability information
- **AND** observations SHALL NOT be represented as complete end-to-end routing proof or proof that an existing connection used the latest rule configuration

### Requirement: Bounded queries and explicit failures
The runtime SHALL bound rows, response size, pagination and timeouts and distinguish successful empty results from unavailable or failed observations.

#### Scenario: A query returns no matches or exceeds its bounds
- **WHEN** the required query capabilities are available and the API provides a valid successful observation without matching records
- **THEN** the result SHALL be `ok` with zero matches
- **AND** a bounded or incomplete result SHALL explicitly report truncation and SHALL NOT claim complete coverage

#### Scenario: The appliance cannot provide the requested capability
- **WHEN** a required endpoint or response capability is unsupported
- **THEN** the result SHALL be `unsupported` and exit nonzero
- **AND** authentication, permission, transport and malformed-response failures SHALL instead be `error` with a nonzero exit
- **AND** neither outcome SHALL become an empty successful result; their match counts SHALL be null
- **AND** a missing field needed to evaluate a supplied selector SHALL be unsupported, while a missing optional observation field MAY be unavailable in an otherwise successful result
- **AND** a missing selected alias/rule or ambiguous rule identity SHALL be an error

### Requirement: Diagnostic detail is protected and opt-in
Default output SHALL contain safe summaries only; raw alias entries, logs and state details SHALL require explicit opt-in to protected caller-owned output.

#### Scenario: Detailed output is requested
- **WHEN** the caller opts into row details
- **THEN** the runtime SHALL require an absolute `OPNSENSE_DIAGNOSTICS_OUTPUT` path, or equivalent `opnsense_diagnostics_output` for direct Ansible use
- **AND** it SHALL validate the destination before API access and write beneath `OUTPUT_DIR/runtime/opnsense-diagnostics/` with directory mode 0700 and file mode 0600
- **AND** it SHALL reject unsafe path/link destinations and avoid raw details in console output, tracked files and unprotected temporary files
- **AND** it SHALL reject overlap with the request, inventory, authored inputs or implementation files even beneath the allowed output root
- **AND** API secrets and authentication headers SHALL never appear in result files or errors

#### Scenario: Detail output is not enabled
- **WHEN** `include_details` is false or omitted
- **THEN** the runtime SHALL create no detailed result file
- **AND** an explicitly supplied detail output path SHALL be rejected before API access rather than implicitly enabling details

### Requirement: Supported diagnostics are backed by implementation evidence
All three diagnostic kinds SHALL have implemented adapters and representative API fixture coverage, with documented upstream method/schema and permission requirements.

#### Scenario: Software acceptance is reported
- **WHEN** mocked APIs and offline checks pass
- **THEN** the result SHALL be described as software-only validation
- **AND** an unsupported stub SHALL NOT count as implementing a diagnostic kind
- **AND** appliance/version qualification and real traffic evidence SHALL require separate authorized validation

### Requirement: Diagnostic coverage is explicit
Results SHALL distinguish the bounded data actually inspected from complete history or appliance-internal success that cannot be established from upstream responses.

#### Scenario: Only a bounded recent log sample is available
- **WHEN** selectors are evaluated locally over a limited recent log response
- **THEN** the result SHALL expose examined record count, available time coverage and truncation
- **AND** zero matches SHALL apply only to that sample, not the complete requested history

#### Scenario: Upstream masks backend failure as empty data
- **WHEN** the supported API response cannot distinguish an empty dataset from a backend failure
- **THEN** the adapter SHALL report observation availability as unknown and observational counts as null rather than claim a verified empty observation
- **AND** when this affects a required observation the result SHALL be `unsupported` with a nonzero exit and an observation-unavailable reason, retaining independently verified configuration metadata when available
- **AND** detectable invalid query-state fallback pages SHALL be errors
