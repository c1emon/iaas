## ADDED Requirements

### Requirement: Executor memory is checked before guest dispatch
Image build and test SHALL perform a simple memory observation before guest startup, alongside existing platform, KVM and disk checks. It SHALL read host available memory and any directly observable memory limit/current usage for the executor's actual container scope. An observed finite headroom smaller than the requested guest memory SHALL prevent startup with measured and requested values retained. Unavailable measurements, unsupported layouts or hidden ancestor constraints SHALL be reported as unknown with their observation scope and SHALL NOT alone prevent guest startup or be treated as unlimited/sufficient capacity. This check SHALL NOT require complete ancestor traversal, support qualification across cgroup generations, a separate overhead-policy contract, resource reservation or guaranteed freedom from later OOM.

#### Scenario: Host has insufficient memory
- **WHEN** observed host available memory is below the configured guest memory
- **THEN** build/test SHALL refuse before QEMU/Packer guest startup and retain required versus observed memory evidence

#### Scenario: Container is tighter than the host
- **WHEN** observed host memory is sufficient but the executor's directly observed finite container limit minus current use is below configured guest memory
- **THEN** build/test SHALL refuse before guest startup and identify the effective limiting scope
- **AND** it SHALL NOT substitute host capacity for container headroom

#### Scenario: Direct scope has no finite limit
- **WHEN** a successfully read current container scope reports no finite memory limit
- **THEN** the observed host memory SHALL still be checked and the container observation scope SHALL be retained
- **AND** this SHALL NOT claim complete knowledge of hidden ancestor limits

#### Scenario: Memory measurements are unavailable
- **WHEN** host or current container measurements cannot be read or the actual layout is unsupported
- **THEN** the missing observations SHALL remain unknown with a bounded reason and scope, without blocking startup solely for that missing information
- **AND** any independently observed insufficient headroom SHALL still block startup; a successful actual build SHALL NOT turn unknown memory observations into passed capacity proof

### Requirement: Fixed downloads use finite read-only transfer retry
Image and existing dependency-download paths SHALL permit only narrowly classified temporary transport retries under the original bounded operation deadline when version/source identity and checksum verification are fixed. Download retries SHALL discard only execution-owned partial output, preserve locked dependency selection and verify final bytes before use. Checksum mismatch, unsafe/unfixed source, authorization or TLS trust failure SHALL stop without automatic retry. Dependency retry SHALL NOT replay provider apply, backend mutation or whole facility operations.

#### Scenario: A fixed image transfer is interrupted
- **WHEN** a checksummed fixed image GET fails with an admitted temporary transport error
- **THEN** another read-only transfer MAY occur within remaining original time after owned partial output is safely removed
- **AND** only complete checksum-verified bytes SHALL reach guest construction or publication

#### Scenario: Retry cannot preserve pinned dependencies
- **WHEN** a dependency source lacks required fixed version/checksum association or retry would modify the lock selection or repeat a facility operation
- **THEN** automatic retry SHALL be refused with the relevant reason rather than silently weakening reproducibility
