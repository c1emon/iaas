## ADDED Requirements

### Requirement: OPNsense workflow bytes are bounded per complete observation
The fixed OPNsense workflow transport SHALL apply its 8 MiB cumulative byte limit to one complete configuration observation, one active-state observation, or one correlated completion polling attempt. All resource, interface, page, detail and nested requests within that observation SHALL share the limit. A subsequent independent observation SHALL start with a fresh byte counter, including failure recovery readback. Starting a fresh byte scope SHALL NOT renew an enclosing time deadline, reset wait attempts, retry writes, or convert incomplete evidence into a confirmed state.

#### Scenario: Repeated observations exceed a reader lifetime total
- **WHEN** an apply reuses one reader for multiple observations that each fit the cumulative limit but together exceed it
- **THEN** each observation receives its own cumulative budget
- **AND** the reader session remains reusable across stages and recovery readback

#### Scenario: A single observation exceeds its shared limit
- **WHEN** individually bounded responses across resources, pages or details exceed the cumulative limit within one observation
- **THEN** the observation reports a bound failure rather than complete empty configuration
- **AND** nested reads do not reset that observation's byte counter

#### Scenario: Failure recovery follows exhausted observation
- **WHEN** an execution stops after an observation exhausts its byte budget
- **THEN** recovery readback starts a new observation budget
- **AND** after-state is confirmed only from that complete readback; another incomplete readback leaves after-state unknown

#### Scenario: Completion polling retains the shared deadline
- **WHEN** a correlated completion wait performs multiple polling attempts
- **THEN** each attempt shares one byte budget across its boundary and completion reads
- **AND** later attempts receive fresh byte counters while retaining the original wait deadline and attempt limit
