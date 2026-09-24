## Purpose

Define the versioned, credential-separated disk artifact and execution contracts that connect caller-managed image storage to reusable image construction and PVE template publication.

## ADDED Requirements

### Requirement: One authoritative image publication contract
The system SHALL define the build/publication handoff in contracts/image-publish-v1.md and expose equivalent stable schemas/documentation with the implementing release for caller pinning.

#### Scenario: A caller consumes the image tool
- **WHEN** infra-ops selects the new runtime and contract version
- **THEN** it SHALL be able to prepare supported requests, validate results, upload artifacts and invoke publication without duplicating iaas implementation or interpreting arbitrary logs
- **AND** unknown versions or legacy inputs SHALL fail without a compatibility adapter

### Requirement: Image identity is separate from transport
An image-artifact/v1 SHALL bind exact disk bytes, independent disk capacity, format, architecture/firmware, source build facts and declared check results; transfer credentials SHALL remain outside immutable artifacts and previews.

#### Scenario: Publish an uploaded artifact
- **WHEN** a caller hands off a fixed descriptor and stable object reference
- **THEN** publication SHALL validate the descriptor schema and canonical semantic digest, recheck streamed disk SHA-256/size and inspect actual format/self-containment before any PVE write
- **AND** relative disk/evidence paths SHALL stay within declared roots without traversal or symlink escape
- **AND** upload completion SHALL require successful transfer, expected object size and fixed object identity/version, with required evidence and descriptor available; it SHALL NOT require an additional full GET/hash by default
- **AND** an optional full upload readback MAY strengthen storage verification, while content-consumption SHA verification SHALL remain mandatory and upload completion SHALL NOT falsely claim that readback occurred

#### Scenario: Descriptor formatting changes without semantic changes
- **WHEN** equivalent valid descriptor JSON differs only in whitespace or object-key order
- **THEN** its canonical semantic digest SHALL remain identical and publication SHALL NOT require a new plan solely for formatting
- **AND** duplicate JSON keys SHALL be rejected before canonicalization, and changed meaningful values SHALL change the binding

#### Scenario: Refresh a private download locator
- **WHEN** a short-lived source locator expires
- **THEN** the caller MAY supply new authentication for the same fixed object/digest without changing build or publication intent
- **AND** the runtime SHALL NOT send credential-bearing URLs to PVE, persist them in previews or include them in ordinary logs/argv

#### Scenario: Consume an externally built image
- **WHEN** a conforming artifact was produced outside the iaas image tool
- **THEN** publication SHALL validate the same disk and required-check contract independently of builder origin
- **AND** missing build history SHALL remain unknown and SHALL NOT bypass mandatory compatibility or acceptance requirements

### Requirement: Each lifecycle result preserves its actual scope
Build, independent image test, artifact upload, PVE template configuration, guest acceptance and caller promotion SHALL be distinct outcomes.

#### Scenario: Independent test supplies previously missing evidence
- **WHEN** an artifact marks a required check not_performed or unknown and the caller explicitly selects a matching disk/policy/scope image-test-result/v1 with passed status
- **THEN** publication SHALL evaluate that selected result as current evidence for the check without rewriting the original descriptor or treating missing history as a conflict
- **AND** selected test_results SHALL be bound into the publication preview, while contradictory observations or mismatched disk/policy/scope SHALL NOT be silently resolved by choosing the latest result

#### Scenario: Required evidence is absent
- **WHEN** a required check remains failed, not_performed or unknown after resolving explicitly selected artifact and matching test evidence
- **THEN** the dependent success/admission SHALL be blocked while independent known facts remain available
- **AND** artifact presence, installed packages or a template flag SHALL NOT substitute for the missing evidence
