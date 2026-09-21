# bounded-http-read-transport Specification

## Purpose
Provide reusable bounded HTTP response reading for internally admitted read-only operations while preserving provider-specific authorization, observation status and failure semantics.

## Requirements

### Requirement: Transport does not expand operation admission
Shared transport SHALL execute only requests already admitted by provider adapters, SHALL disable redirects and SHALL preserve explicit TLS settings. It SHALL not create a public arbitrary endpoint interface, enable mutation operations or perform automatic retries. HTTP method alone SHALL not authorize an operation as read-only.

#### Scenario: Read-only provider query requires POST
- **WHEN** an existing fixed adapter admits a documented read-only POST query
- **THEN** transport sends that request once with its validated payload
- **AND** no write, retry or follow-up operation is inferred

#### Scenario: Provider fails or redirects
- **WHEN** a request returns a redirect, authentication failure, timeout or server error
- **THEN** transport reports a bounded failure without following the redirect or replaying the request

### Requirement: Response reading preserves bounded budgets and cleanup
Transport SHALL apply finite connection/read timeouts, response and cumulative byte limits, and any supplied observation budget at request and response-processing boundaries. Cumulative budgets SHALL span the caller's specified operation scope. Every acquired response SHALL be closed on success or failure. A detected bound violation SHALL not yield a successful partial or empty JSON result.

#### Scenario: Multiple pages exceed cumulative bytes
- **WHEN** individual pages fit their per-response limit but together exceed the shared limit
- **THEN** processing fails at the cumulative boundary without resetting the counter for each request
- **AND** the acquired response is closed

#### Scenario: Parsing or streaming fails
- **WHEN** JSON is malformed, the stream fails, a response block is invalid or a processing budget is exhausted
- **THEN** transport closes the response and emits a classified failure
- **AND** timing claims identify enforced checkpoints rather than promising preemption beyond the underlying transport

### Requirement: Provider failures remain safely classifiable
Shared failures SHALL expose controlled reason codes and optional numeric HTTP status without raw request or response material. Workflow and diagnostics adapters SHALL retain their existing public status and reason mappings and SHALL not infer complete absence from transport failure.

#### Scenario: Both adapters encounter an unavailable endpoint
- **WHEN** the workflow and diagnostics adapters receive the same unsupported endpoint response
- **THEN** each maps the common failure into its established capability result
- **AND** neither returns successful zero matches

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
