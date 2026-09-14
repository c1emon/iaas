# opnsense-one-to-one-nat-management Specification

## Purpose
Provide explicit caller-owned one-to-one IPv4 NAT and BINAT address mappings using native semantics and per-rule reflection, isolated from port forwarding, global reflection settings and IPv6 prefix translation.

## Requirements

### Requirement: Native one-to-one mapping contract
The system SHALL accept opnsense_one_to_one_nat_rules in one-to-one-nat.yml with the common NAT identity/lifecycle and single interface, type nat/binat, external address/network, source/destination networks, optional inversion/logging and explicit enable/disable nat_reflection. It SHALL reject port fields, DNAT reflection values and unsupported IPv6/NPTv6 semantics. Literal address families and BINAT explicit network sizes SHALL be validated locally; unresolved legal aliases SHALL NOT be declared equivalent without evidence.

#### Scenario: Equal-sized BINAT networks
- **WHEN** a caller supplies a valid pair of equal-sized IPv4 networks with binat
- **THEN** the system preserves the bidirectional mapping type rather than converting it to DNAT plus SNAT records

#### Scenario: Invalid BINAT range
- **WHEN** explicit BINAT networks have unequal sizes
- **THEN** admission fails before writes; nat type is not subject to a fabricated equal-size requirement

### Requirement: Independent reflection and ownership
One-to-one NAT SHALL manage only its own declared objects, retain the chosen native nat/binat behavior, and not create global reflection, VIP or filtering declarations implicitly.

#### Scenario: Reflection enabled on a mapping
- **WHEN** a mapping explicitly enables its supported per-rule reflection option
- **THEN** only that declared option is requested and the appliance-wide reflection settings remain unchanged
