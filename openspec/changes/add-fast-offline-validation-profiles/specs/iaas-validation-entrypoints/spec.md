## ADDED Requirements

### Requirement: Explicit fast and domain validation profiles
The repository SHALL expose environment-independent fast checks and named domain test profiles alongside the full offline test and check commands. Fast checks SHALL use an explicit bounded set of pure offline tests, SHALL report subset coverage and SHALL fail for an empty selected set. They SHALL not require inventory selection, runtime credentials, image builds or external infrastructure tools.

#### Scenario: Developer runs fast validation
- **WHEN** a developer requests the fast profile without environment inventory, Docker, Ansible execution or device credentials
- **THEN** the selected pure Python tests and configured static checks can execute
- **AND** the report does not claim full repository or appliance acceptance

#### Scenario: Domain profile is selected
- **WHEN** a developer selects the OPNsense, PVE or K3s test profile
- **THEN** the repository-owned command runs the documented offline domain set and propagates failure
- **AND** it does not implicitly invoke a device operation

### Requirement: Fast profiles preserve complete validation
Adding profiles SHALL preserve collection of all existing tests by the full test command and preserve the aggregate offline gate used by CI. External-tool integration and image smoke checks SHALL remain explicit and SHALL not be mistaken for pure fast tests.

#### Scenario: Test has no profile marker
- **WHEN** an existing or new test has no fast or integration marker
- **THEN** the full test command still collects it
- **AND** the fast profile does not silently treat it as a verified fast test

#### Scenario: Full CI validation runs
- **WHEN** PR or main CI invokes the aggregate offline gate
- **THEN** existing required validation remains present regardless of fast-profile results

### Requirement: Validation performance claims are measured
Performance reports SHALL identify the executed test set, runtime environment and measured timings. Parallel execution SHALL be opt-in for tested isolated offline groups and SHALL not enable concurrent device operations.

#### Scenario: Faster feedback is reported
- **WHEN** an implementation reports a speed improvement
- **THEN** it provides comparable measurements and discloses omitted checks
- **AND** absence of a measured parallelism benefit does not cause parallel execution to be enabled by default
