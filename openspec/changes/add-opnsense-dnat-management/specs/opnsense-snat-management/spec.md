## Purpose

Provide caller-selected source NAT declarations for predictable source translation and static-port behavior, without assuming ownership of global outbound NAT mode or automatically generated appliance rules.

## ADDED Requirements

### Requirement: Native source NAT contract
The system SHALL accept opnsense_snat_rules in snat.yml with the common NAT identity/lifecycle and SNAT-specific single interface, family, protocol, source/destination matching, target, optional ports and static_port fields. target_port SHALL be an integer port, not a DNAT local_port string. Unknown fields, incompatible address families and simultaneous static_port plus target_port SHALL fail locally. The initial contract SHALL reject no_nat rather than supply a fictitious target to satisfy the provider.

#### Scenario: Preserve original source port
- **WHEN** a valid SNAT record requests static_port true without target_port
- **THEN** the native static-port option is passed without inventing a translation port

#### Scenario: Unsupported translation request
- **WHEN** a record supplies a port alias where the fixed SNAT contract does not support one, conflicting port options, or no_nat
- **THEN** the complete selected batch fails before credentials or writes

### Requirement: Preserve outbound mode and external NAT
SNAT management SHALL reconcile declared manual resources only, preserve existing global outbound NAT mode and undeclared automatic/manual rules, and report software validation separately from live rule precedence and forwarding evidence.

#### Scenario: Automatic NAT already exists
- **WHEN** a valid caller-defined SNAT rule is applied on an appliance with automatic NAT
- **THEN** the workflow does not switch mode, remove automatic entries or claim that the declared rule necessarily takes precedence
