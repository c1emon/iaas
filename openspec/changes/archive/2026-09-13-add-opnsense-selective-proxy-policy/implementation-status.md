# Implementation status

Date: 2026-09-13. All 8 implementation tasks are complete in the local software scope. This change retains its historical name but supplies only generic OPNsense resource contracts.

## Ownership handoff

infra-ops commit `9ea3ea9` owns the dedicated generator, policy fixtures, policy tests and operating instructions. Its source uses standard files and the supported offline CLI rather than iaas private imports. The uncommitted dedicated iaas module, fixtures, tests and documentation have been removed after that handoff; the runtime no longer accepts the selective-proxy input. The real Ansible admission regression now lives in generic resource-context tests.

iaas accepts standard caller-authored Alias/Rules declarations via existing source paths. Gateway/VIP sources are unchanged. The Alias/Rules delta specs cover the neutral source contract; main-spec synchronization, including Alias Purpose, is complete as part of this archive.

## Generic implementation

- Source/destination inversion requires a single target.
- Optional interface-network and alias context supplies static ingress coverage evidence, separately for inet, inet6 and inet46. Dynamic/unknown members supply no evidence; sufficient static members can still prove coverage.
- Selected alias declarations must agree with duplicated context. External references remain unresolved rather than requiring complete appliance inventory. Interface networks have one supported declaration location, the context itself; no second interface resource schema was introduced.
- The direct playbook revalidates loaded data before credential preflight. The adapter strips primitive metadata while preserving strict boolean/integer semantics; strings are not coerced.
- Source omission still does not delete resources. Resource saving, activation and caller authorization retain their existing boundaries.

## Validation and version boundary

- Focused resource validation, alias dependencies, provider admission and runtime configuration: 117 tests passed; the added high-level-input rejection test and updated generated-group example also passed in the subsequent focused resource-context run.
- Alias lifecycle, runtime dispatch, credential inputs, architecture and review regressions: 38 tests passed.
- Scoped pyright: zero errors. Direct filter playbook syntax and strict OpenSpec validation passed. Git diff whitespace checks passed.
- GitNexus impact reported CRITICAL shared entrypoints. Graph change analysis covers affected validation/configuration flows; index process enumeration is bounded and is not exhaustive runtime evidence. Actual local Ansible tests cover the dynamically discovered filter call.
- Runtime environment schema remains version 1. This commit is the source-level generic contract revision; no release tag or published runtime image contains a claimed delivery from this stage. The consumer must pin and qualify a compatible published runtime separately.

No credentials, device inspection, writes, activation, release or push occurred in this stage. Software tests do not constitute appliance acceptance. The change is archived on 2026-09-13 after completion of the software tasks and main-spec synchronization.
