## ADDED Requirements

### Requirement: Actionable offline template and clone configuration checks
Existing check entrypoints SHALL validate current build, publication and clone input fields, parameter relationships and supported capabilities without network, credentials, provider/state initialization or facility effects. Unknown parameters SHALL fail explicitly. Diagnostics SHALL identify the safe logical input file, field and reason without echoing sensitive source values.

#### Scenario: Supported general template and clone inputs
- **WHEN** offline check selects an 8 GiB Debian build, no-NIC publication or a full clone with independent NIC/network and 128 GiB disk
- **THEN** it SHALL validate the selected current input and declared relationships and return only an offline configuration conclusion

#### Scenario: Unsupported or conflicting configuration
- **WHEN** an input has an unknown field, unsupported version/capability, invalid capacity, invalid upgrade type or conflicting network/disk settings
- **THEN** check SHALL fail with file/field/reason and SHALL NOT ignore the parameter or access credentials/facilities

#### Scenario: External facts are not established offline
- **WHEN** check accepts a structurally valid input
- **THEN** current pool/bridge/IP/storage availability, actual downloaded base capacity, build success and real guest acceptance SHALL remain separate observations
