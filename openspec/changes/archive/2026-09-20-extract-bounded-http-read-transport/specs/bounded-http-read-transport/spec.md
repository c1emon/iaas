## Purpose

Provide reusable bounded HTTP response reading for internally admitted read-only operations while preserving provider-specific authorization, observation status and failure semantics.

## ADDED Requirements

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
