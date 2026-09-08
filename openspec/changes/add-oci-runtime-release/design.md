## Context

Source review baseline: `ffa4f70` on 2026-09-08. This document proposes phase 3
of the delivery decision; it is not evidence of a built or published image.

| Current source | Consequence for this change |
| --- | --- |
| `Makefile` sets `ASTRA`, `PVE_DIR`, inventory/generated paths and several `ROOT/.cache` paths | Separate implementation, authored inputs, generated outputs, and sensitive runtime work paths |
| PVE/services/foundation Python CLIs accept explicit input/output files | Reuse these contracts; do not invent a second model or generator |
| `automation/ansible/ansible.cfg` defaults to Astra inventory and relative resource paths | Supply explicit external inventory and absolute image-local role/Collection/plugin paths |
| Lookup plugins find `automation/src` relative to themselves | Preserve the packaged `automation/` layout and verify plugin loading |
| Astra OpenTofu root references `../../../../automation/opentofu/modules/pve-cloudinit-vm` | External roots need a documented module source that exists inside the image |
| `pyproject.toml` has no distributable package build configuration; Ansible is in the dev group | Build a uv-managed runtime environment containing required execution dependencies; do not assume `uv sync --no-dev` installs Ansible |
| Collection requirements include unpinned/ranged versions; CI installs OpenTofu `latest` | Introduce committed exact execution-tool/Collection resolution for image builds |
| CI currently runs `make check` and `make secret-scan` on PR/main | Reuse those checks at the release revision, with publication in a separate job |

GitNexus was refreshed with `gitnexus analyze --index-only`. PVE `parse_args`
has one direct caller (`main`), nine upstream results, two affected process
summaries, and LOW risk. The shared CLI dispatcher introduces indirect graph
results; these are not a reason to rewrite other domains. Makefile impact is
UNKNOWN because the graph resolves no callers; direct review confirms callers
in CI, tests, and operator commands. Implementation must rerun impact analysis
for the functions it actually edits.

## Goals / Non-Goals

The deliverable is one reusable runtime with an executable external-input
contract and a release workflow. The minimum supported execution architecture
is `linux/amd64`, suitable for a Linux infra runner. This says nothing new about
guest architecture support; native Apple Silicon/arm64 images are deferred.

Keep operation names and schemas while replacing environment-specific invocation
defaults with explicit generic inputs. Do not move or delete `environments/astra`,
weaken secret-file/SSH/scope protections, change resource addresses, provision a
backend, or add platform-side tools and reconciliation. Live execution remains
the later Forgejo/cluster stages' responsibility.

## Decisions

### 1. Ship one image with a stable implementation layout

Use `/opt/iaas` for immutable implementation resources, preserving
`automation/src`, `automation/ansible`, and `automation/opentofu/modules` beneath
it. Ship the repository-owned Make entrypoints and their required reusable
resources, including existing template-build mechanisms where their commands
are exposed. Do not publish separate package products.

The published image contains only resources required by supported runtime
operations: executable code and entrypoints, required Ansible playbooks/roles/
plugins/templates, OpenTofu modules, required template-build assets, installed
execution dependencies, and metadata needed to locate or run them. Preserve
only the project/lock metadata actually needed by the uv runtime invocation.
Required LICENSE/NOTICE material is retained separately from user documentation.

Exclude `docs/`, repository and module READMEs, `openspec/`, `tests/`, test
fixtures, examples, review reports, `AGENTS.md`, `.github/`, other CI/editor
configuration, build recipes, and build-only compilers/lint/test tools from
every layer of the published runtime. Do not copy whole automation or dependency
source trees merely for convenience. Keep build/test tools and synthetic inputs
in separate stages/jobs or temporary mounts and copy only runtime artifacts into
the final stage. Exclude separable dependency manuals/examples/tests through
supported packaging controls; do not delete runtime metadata or embedded plugin
code indiscriminately by filename extension. Verify packaged operations after
pruning. No byte-size target or custom per-file manifest system is required.

Build with an explicit copy allowlist and an exclusion file. Never use an
unfiltered `COPY . .` followed by deletion: deleted data survives in prior image
layers. Exclude all real `environments/` data, Git history, developer virtual
environments, installed local Collections, caches, state, plans, kubeconfig,
runtime secrets and observations from every build stage. Build-time tests can
mount synthetic fixtures separately; fixtures SHALL NOT ship in the final image.

Keeping documentation generators executable does not require packaging their
generated documents: `services-generate` and `foundation-generate` still write
their requested output to the caller's output directory at runtime.

Use a digest-pinned Linux base and exact releases for uv, Python, Ansible,
OpenTofu, and required execution CLIs (including SSH and Packer
where existing exposed operations need them). Reuse `uv.lock`, resolve the
runtime dependency group explicitly, and pin required Collections and their
dependency closure. Verify downloaded tools using upstream checksums. Preserve
upstream license notices and check redistribution terms for bundled tools;
do not silently omit a tool required by an advertised command.

Install the environment using uv during build; runtime Python commands use
`uv run --no-sync` against that installed environment. Neither ordinary startup
nor offline operations install dependencies. This is version locking, not a
claim that rebuilding at a later date produces identical bytes. No new signature,
per-object evidence, or supply-chain qualification system is required.

### 2. Extend existing Make orchestration with external directories

Use `ENVIRONMENT_DIR` and `OUTPUT_DIR` as the new explicit directory inputs.
The image entrypoint takes an existing operation name, such as `pve-generate`,
and delegates to the shipped Makefile at `/opt/iaas/Makefile`; existing explicit
operation variables remain available. With no operation, show help and exit
without reading an environment, generating data, or contacting anything.

| Directory/input | Container contract |
| --- | --- |
| `ENVIRONMENT_DIR=/environment` | Authored inventory, Ansible data and policy; can be a read-only bind mount |
| `OUTPUT_DIR=/output` | Caller-owned writable output root |
| Generated artifacts | `/output/generated/{ansible,opentofu,docs,packer}/...` |
| Runtime work | `/output/runtime/` for review files, cloud-init, caches, temporary tool data and local backups; protect sensitive contents |
| `PVE_DIR=/work/pve` | Explicit external OpenTofu working root for commands needing one; independent from generated tfvars and image resources |
| Secret files / SSH material | Explicit protected mounts or existing environment injection mechanisms; never command-line secret values |

The conventional relative input structure under `/environment` matches the
current `inventory/` and `ansible/` layout. Only inputs needed by the selected
operation are required. PVE source validation and generation must not demand a
K3s intent, platform locator, live token, or OpenTofu backend.

For a checkout with committed generated artifacts, the existing explicit
`GENERATED_DIR`/per-file overrides can select that generated-only subtree for
generation and freshness checks; it must remain separate from authored
inventory/Ansible input subtrees. `OUTPUT_DIR` still owns runtime work. This
allows validation of existing committed outputs without moving real environment
data merely to adopt the runtime. Container defaults use the table above.

In container mode, missing directory inputs or an input/output-file overlap fail
before execution; paths must not resolve into `/opt/iaas` or overwrite authored
inputs. This is a configuration correctness check, not a sandbox against a
privileged operator. Outputs must remain usable by the invoking UID/GID; the
documented Linux invocation supports an explicit UID/GID, writable home/cache,
and the existing owner/mode checks for sensitive material. Do not weaken
host-key checking or protected-file validation to make container tests pass.

Apply the same generic directory contract in local checkout and container modes.
Remove the `ASTRA` variable and all implicit `environments/astra` input/output
fallbacks from supported execution paths, including Ansible's default inventory.
Reject a supplied legacy `ASTRA` selector with a migration message instead of
silently ignoring it. Existing per-file inputs remain available for domain
commands, but a selected environment must never be silently mixed with another
environment's defaults. Invoke scripts and Ansible resources independently of
the caller's current directory. Repository-only tests/build/lint/help do not need
an environment when they consume none; environment operations require the
relevant explicit directories or documented complete file inputs.

`environments/astra/` may remain as the authored data of the environment named
`astra`; it is no longer a privileged runtime location. Another environment can
use any external directory with the same schema. Update local callers and CI to
select their environment explicitly. Examples use `<environment-dir>` and
`<output-dir>`, with Astra-specific examples limited to its operator context.
Also generalize OPNsense playbook variable-file defaults and generated document
source descriptions. Generation describes the selected logical input rather
than claiming it read `environments/astra`; avoid recording host absolute paths.
Use `IAAS_PVE_SSH_TIMEOUT_SECONDS` and generic `iaas-pve-*` helper command,
sudoers, temporary-file and lock-file names. Update their callers, source files,
bootstrap declarations and tests together; legacy environment variable names
fail with a migration message instead of being silently ignored.

Do not mass-rename historical documents, real host identities, inventory values,
or independently reviewed host-wrapper protection limits merely because they
contain `astra`. Those are data/domain contracts. Existing hosts need a separately
authorized helper cutover before using the new online caller paths: stop helper
jobs, confirm no old process/lock owner, install and validate the generic helper
and matching sudoers, remove the old execution permission/entrypoint, then
resume. Old and new helper names must not permit concurrent executions protected
by different locks. No host installation or removal occurs in this change's
software-only implementation acceptance; the runbook makes this prerequisite
explicit and must not recommend broad sudo or a silent fallback to old helpers.

Use the existing explicit K3s inventory/intent/scope and runtime-secret inputs.
Path relocation does not repair or qualify the handoff workflow. Existing
domain validation semantics and scope requirements remain unchanged.

Credential acquisition belongs to the caller, not the IaaS runtime. IaaS accepts
resolved credentials through documented environment variables or explicitly
supplied protected files (including SSH keys and K3s runtime secrets). It does
not authenticate to 1Password, resolve `op://` references, invoke `op`, or require
`OP_SERVICE_ACCOUNT_TOKEN`. Do not bundle the 1Password CLI in the runtime image.

The caller can use either `op run` with environment-owned reference templates,
or traditional CI Secrets, host environment injection and protected Secret file
mounts. Both routes supply the same operation inputs; no provider selector or
provider abstraction is added inside IaaS. Reference-only environment metadata
may retain its schema and be checked offline, but is not a resolved credential.
Missing required values fail before the credentialed operation; there is no
implicit provider lookup or fallback. Password hashing uses caller-supplied
plaintext in memory and retains existing protected output rules.

For CI using 1Password, the private caller owns a noninteractive service account,
its vault permissions, the CI Secret containing its token, and CLI installation.
It resolves secrets before invoking IaaS and passes only the operation's required
values/files into the container, not its 1Password bootstrap token or desktop
session. Traditional Secret callers need no 1Password account, login or binary.
Astra item/vault naming remains environment-specific, not a runtime restriction.
This change does not provision service identities or a private deployment pipeline.

Offline generation, validation and image smoke tests need no credential provider
or real secrets. Public image build/release jobs need no infrastructure secrets;
GHCR publication retains its separate ephemeral `GITHUB_TOKEN`. Neither input
route may embed credentials in the image, committed files, command-line values
or logs, or weaken sensitive-file owner/mode and SSH host-key checks.

Illustrative planned invocation (the image/entrypoint does not exist yet):

```sh
docker run --rm --network none \
  -v /path/to/environment:/environment:ro \
  -v /path/to/output:/output \
  -e ENVIRONMENT_DIR=/environment -e OUTPUT_DIR=/output \
  ghcr.io/<owner>/iaas-runtime@sha256:<digest> pve-generate
```

The corresponding checkout operation is `make pve-generate
ENVIRONMENT_DIR=<environment-dir> OUTPUT_DIR=<output-dir>` on one command line.
Non-default paths containing spaces must be passed as quoted arguments. UID/GID
and protected runtime mounts are documented and tested before advertising
credentialed operations, rather than weakening their existing checks.

### 3. External OpenTofu roots consume modules from the image

Document the literal source
`/opt/iaas/automation/opentofu/modules/pve-cloudinit-vm` in a synthetic external
root. Selecting the runtime by digest selects that module's content. The private
root owns backend configuration and `.terraform.lock.hcl`; init uses the supplied
provider lock without silently upgrading it. Do not rewrite a private root,
interpolate its HCL at runtime, or rely on the GitHub checkout's relative path.

Use a separately mounted working root and writable tool data directory. Existing
`tofu` and Make commands remain explicit. This change does not establish saved
plan approval, backend locking or environment serialization: these belong to
phase 5. Document that ephemeral container-local state is unsuitable for that
future deployment pipeline and that no backend/state migration is performed
here. A backend-disabled init/validate using synthetic inputs is sufficient to
check the packaged module/provider interface; it may download the locked
provider and is not an air-gap or live deployment test.

### 4. Build on Release publication and publish to GHCR

Create a dedicated workflow under `.github/workflows/`, triggered by
`release: { types: [published] }`. Publish both stable `vX.Y.Z` and prerelease
`vX.Y.Z-<suffix>` versions; restrict accepted tags to a documented OCI-compatible
subset of SemVer (no build metadata), rejecting invalid tags before publication.
Draft creation, release-body edits, PRs, main pushes, and tag-only pushes do not
publish an image. No mutable `latest` alias is required in this phase.

Resolve and record the event's tagged commit, validate that exact revision, and
build the release image from it rather than main. Run existing offline checks,
secret scanning and the image checks before a dependent publish job. The job
publishes the tested image artifact without rebuilding it; preserve image config
and layers during transfer. Pin new third-party Actions to full commit SHAs.
The build/test job has read-only repository access and no publishing credentials.
Only the publish job receives `contents: read` and `packages: write`; it logs in
using its ephemeral `GITHUB_TOKEN` with no PAT, developer 1Password session,
infrastructure credentials, or management-network access.

The canonical repository is `ghcr.io/<lowercase repository owner>/iaas-runtime`.
Use the release tag as image tag and standard OCI source/revision/version
metadata. After pushing, report release tag, exact source commit, canonical image
reference and registry digest in the job summary. Check an anonymous digest pull
and a minimal invocation on a clean runner before reporting distribution success.
The first package must be configured public by its authorized owner; repository
visibility alone is insufficient. No public configuration or credential upload
is part of this workflow.

Serialize publication per image release tag without cancelling an active push.
On rerun, an already published version is not overwritten: verify its recorded
source revision, obtain its existing digest, and recheck pullability. A different
source for the same version fails and requires a new release version. If no image
exists after a failed build/push, the same release run can be retried. This policy
does not claim a transactional registry write or prevent an administrator from
manually changing tags.

Release publication occurs before the workflow finishes. Therefore a visible
Release does not prove the image is available: consumers use only a successfully
reported digest. If a future workflow creates the Release using `GITHUB_TOKEN`,
GitHub suppresses the follow-on release workflow; that automation must explicitly
call the publication workflow or use an appropriately scoped GitHub App token.
Automating Release creation itself is outside this change.

These trigger/authentication choices follow [GitHub release events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#release),
[workflow triggering](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow),
and [GHCR authentication and visibility](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
The uv installation approach follows [uv's container guidance](https://docs.astral.sh/uv/guides/integration/docker/).

### 5. Verify representative caller paths

Keep `make check` as the checkout gate with explicit environment/output inputs;
do not make an image without tests and
Astra data pretend to run that checkout-only command. Add distinct repository
commands for image build/smoke checks, reused by PR and Release workflows.
PR/main can build/test without logging into GHCR; publication is Release-only.

The container check uses a synthetic environment outside the source checkout,
read-only authored inputs, a writable output mount, an arbitrary working
directory, and no infrastructure credentials. Group PVE/services/foundation
generation and freshness checks, K3s intent composition/rendering, and Ansible
resource/plugin discovery in representative tests. Disable container networking
for these offline checks. Check bad input, missing directories, unsafe output
placement, and stale generated output without adding a test per inventory object.

Run the synthetic external OpenTofu root through backend-disabled init/validate
with its committed provider lock, allowing dependency downloads only. Inspect
build context and image layers for excluded data classes using representative
sentinels and standard image tools. Reuse existing tests for domain safety;
container publication is not real VM, K3s, or handoff acceptance.

## Risks / Trade-offs

- A single image is larger than a Python-only image → keep only execution
  dependencies/resources in the final stage and defer package splitting.
- Relative resource paths may survive superficial CLI tests → exercise Ansible
  plugins and the actual external-root module path inside the image.
- Real environment data can leak through a build context → explicit allowlist,
  exclusions, secret scan and representative layer checks before publishing.
- Noninteractive secret adapters and persistent state require private setup →
  document existing injection inputs; later phase 5 owns the service identity,
  backend, locking and authorization. Do not claim these are delivered here.
- GHCR reachability and public visibility can block consumption → report push
  and clean anonymous pull results separately; a later internal mirror is optional.

## Migration Plan

1. After separate implementation authorization, confirm the implementation
   branch under the repository rules and rerun impact analysis before code edits.
2. Add the directory contract and regression coverage while keeping local
   operation names and current schemas compatible, and migrate local/CI callers
   to explicit generic directory selection.
3. Build the runtime and verify synthetic paths locally/PR without publication.
4. Add the Release workflow and documentation. When a real Release is authorized,
   publish and verify the GHCR digest; leave release acceptance incomplete until
   that evidence exists.
5. Private repositories may then explicitly select that digest. Returning to an
   older runtime means selecting a previous known digest; it does not roll back
   infrastructure or state, and schema/tool compatibility must still be checked.

No live environment files or state are moved in this change. Documentation stays
under the existing `docs/operations/` operator entrypoint, with developer links
from `automation/README.md` and the delivery decision.
