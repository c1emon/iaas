## Purpose

Provide a reusable local image-construction tool with explicit executor requirements, final image identity cleanup, truthful check evidence and bounded task resource ownership, independently of CI and PVE publication.

## ADDED Requirements

### Requirement: Independent versioned image construction
The system SHALL provide an image tool backed by a pinned Packer QEMU profile independently of PVE, OpenTofu state, CI scheduling and artifact storage services.

#### Scenario: Build a selected Debian image
- **WHEN** a caller invokes image build with supported typed configuration on a qualified executor
- **THEN** the tool SHALL validate the base checksum, provision a QEMU guest using typed configuration, run declared checks, shut it down, clean identity offline and deliver a self-contained qcow2 with its descriptor/checksum
- **AND** apt mirrors, packages, timezone, locale and cloud-init/guest-agent setup SHALL reuse the existing customization semantics while excluding site credentials and instance-specific identity
- **AND** the tool SHALL NOT create a PVE object, upload to S3 or implicitly start a CI job
- **AND** it SHALL record the selected inputs, profile/runtime and task identity at invocation without requiring a prior plan, apply admission or build-preview schema

#### Scenario: Check without starting a guest
- **WHEN** image check validates configuration or passive executor checks inspect devices and permissions
- **THEN** those checks SHALL NOT start a guest or imply that KVM runtime usability has been tested
- **AND** image build or test SHALL verify actual KVM startup and fail unavailable KVM rather than silently fall back to TCG

### Requirement: Cleaned image and check evidence are distinct
The tool SHALL bind success to required checks and the final cleaned image bytes without presenting guest execution as a static check.

#### Scenario: Verify first boot after cleanup
- **WHEN** the selected build policy requires post-cleanup boot checks
- **THEN** image build SHALL boot a disposable copy or overlay and destroy that guest without modifying the delivered base
- **AND** UEFI checks SHALL use fresh firmware variable storage and SHALL NOT depend on build-time efivars or enrolled keys
- **AND** the final image SHALL contain no external backing/data file dependencies, build secrets, instance identity or temporary build network configuration

#### Scenario: Test an existing or external image independently
- **WHEN** a caller invokes image test with an existing image-artifact/v1 and explicit test policy and resources
- **THEN** the tool SHALL validate the selected disk identity and boot only a disposable copy or overlay without requiring a rebuild or publication plan
- **AND** its image-test-result/v1 SHALL bind the disk SHA-256, selected policy, runtime and task identity while preserving passed/failed/not_performed/unknown scope
- **AND** UEFI tests SHALL use fresh variable storage and the original disk and artifact descriptor SHALL remain unchanged
- **AND** tests SHALL clean only their owned guest, seed, credentials and working files

#### Scenario: Read or verify an existing artifact
- **WHEN** image read or verify is selected
- **THEN** it SHALL only observe the exact selected task/image and retained evidence without starting a guest or altering the image
- **AND** absent boot evidence SHALL remain not_performed or unknown rather than pass

### Requirement: Local executor lifecycle is bounded
The tool SHALL own only local resources of its selected execution and SHALL expose task status and direct task-scoped clean without managing executor infrastructure or a deployment approval ledger.

#### Scenario: Cancel or lose a build
- **WHEN** controlled cancellation occurs
- **THEN** the tool SHALL terminate and wait for task-owned processes and clean owned temporary guests, files and credentials
- **AND** abrupt executor loss or incomplete collection SHALL preserve unknown facts and remaining recovery material without treating a stale running record or PID as current activity

#### Scenario: Clean a stopped build
- **WHEN** image clean selects an original task and its recorded owned resources
- **THEN** it SHALL recheck process inactivity and ownership under the local resource lock and append the cleanup attempt and result to the task record
- **AND** it SHALL NOT require a separate cleanup request schema, preview, new execution identity or recovery_of
- **AND** shared caches, delivered caller-owned artifacts and unrelated paths SHALL NOT be deleted

#### Scenario: Reuse execution identity
- **WHEN** an existing build or test execution_id is submitted to start that operation again
- **THEN** equal fixed input SHALL only return observation and different input SHALL be rejected
- **AND** the tool SHALL NOT replay a completed, failed or unknown build
- **AND** a deliberate new build or test MAY use a new task identity after the selected work area is safe to use, without deployment-style reconciliation of a reproducible local failure
