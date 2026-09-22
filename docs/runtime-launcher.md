# Native runtime launcher

The launcher runs the versioned container interface. The caller host needs the
launcher binary and Docker CLI connected to its selected daemon. Python, Ansible,
OpenTofu and 1Password are not launcher host dependencies. Resolve credentials
before invocation using the caller's existing secrets system.

CI accepts only caller-supplied parameters, resolved credentials and protected
files. It must not use a developer's local 1Password session, desktop integration
or shell startup files. Local `op run` remains an optional caller-side preparation
step. Release jobs receive their publication tokens from the CI platform; launcher
asset upload uses noninteractive Bash and the explicitly injected `GH_TOKEN`, as
described in [GitHub's CLI workflow guidance](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-github-cli).

## Install and select a runtime

The release workflow attaches `iaas-linux-amd64`, `iaas-darwin-arm64` and `SHA256SUMS`.
Verify the downloaded binary against that release's checksum, rename it to `iaas`
and put it on PATH. These changes do not themselves publish a release. Developers
can build both binaries with Go 1.27.1:

```sh
build_dir="$(mktemp -d)"
sh automation/launcher/build.sh "$build_dir" development
(cd "$build_dir" && sha256sum -c SHA256SUMS)
test -x "$build_dir/iaas-linux-amd64" -a -x "$build_dir/iaas-darwin-arm64"
```

The release artifact set is exactly `iaas-linux-amd64`,
`iaas-darwin-arm64` and `SHA256SUMS`. Runtime image artifacts are built and
tested by the Release workflow as separate `amd64` and `arm64` images, then
assembled into one versioned manifest; the tested image archive is transferred
to publication without rebuilding. These checks do not create a tag, publish a
release or qualify a real PVE environment.

Keep a separate caller-owned `runtime.json`:

```json
{"interface_version":1,"image":"ghcr.io/OWNER/iaas-runtime:vX.Y.Z","platform":"linux/amd64"}
```

Replace the example image with the chosen published tag or repository digest.
Select `linux/arm64` for a native ARM64 image, or `linux/amd64` for an AMD64 image
(Apple Silicon requires explicit emulation for the latter). `latest`, missing
tags and unsupported interface/schema versions are rejected.
`iaas prepare --runtime-config runtime.json` explicitly pulls
the selected image. Normal operations never implicitly pull an image. Tags are
resolved to a repository digest for execution and saved-plan compatibility.
When Docker reports digests from several repositories, the launcher prefers the
requested repository; a local retag without its own digest association uses an
existing repository digest.
Saved plans also bind the runtime architecture; plans from another architecture
or older plans without that field must be prepared again.
Use `iaas capabilities --runtime-config runtime.json` to inspect operation effects.

The cutover keeps these interfaces aligned: launcher capabilities/interface
version `1`; runtime environment schema `1`; PVE plan metadata `2`; PVE result,
template preview and template receipt `1`; and the PVE template helper protocol
`2`. The PVE helper executables are `iaas-pve-template` and
`iaas-pve-template-worker`; installation also includes the snippet upload
helper. A capability response is the compatibility gate: old PVE operation
names are rejected instead of being silently translated.

## Select inputs and an operation

The [environment schema](runtime-configuration.md) selects component input files,
facts and optional scenarios. Paths are relative to the declaring environment
file, including files outside its directory. Unselected components and scenarios
do not contribute inputs or credentials.

```sh
iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component opnsense --operation generate --output ./new-result
```

Use `--scenario NAME` for an explicit scenario. Each invocation requires a new
output directory. Offline check/generate/render operations disable container
network access and forward no credentials. Online operations require `--scope`:

| Component | Operations | Online scope |
| --- | --- | --- |
| OPNsense | check, generate, diagnose, read, plan, apply, verify | One inventory host |
| switch | check, generate, diagnose (read-only facts) | Explicit comma-separated inventory hosts |
| PVE | check, generate, preflight, health, prepare-dependencies, read, plan, apply, verify | Cluster name for diagnostics; complete root ID for lifecycle operations |
| PVE template | check, read, plan, apply, verify | One explicit PVE node for helper operations |
| services | check, generate | — |
| foundation | check, generate, health | Declared environment name |
| K3s | check, generate / render, preflight, verify, deploy, snapshot, upgrade | Explicit VM references; deploy/upgrade use the complete cluster; snapshot uses its declared source |

K3s deploy, snapshot and upgrade write remote infrastructure. PVE apply also
writes infrastructure. Plan accesses state and uses its native lock. Supported
effects appear before execution and in the result. The new interface does not
accept arbitrary commands or direct destroy. PVE deletion is an ordinary
`plan` with `options.destroy: true`, followed by the same reviewed `apply`;
template builds use the independent `pve-template` component. Legacy write
entrypoints return migration errors.

Online component `files` aliases are explicit:

- PVE read: `backend` and optional `execution_result`; the declared root ID is
  checked from options but the root is not materialized. PVE plan adds every
  declared root file, `state_admission`, and any declared `ssh_key`,
  `known_hosts`, `dependencies`, `template_records` and `template_admission`.
  PVE apply consumes `backend`, `execution_admission`, `state_admission`,
  optional template admission and explicit SSH files. Verify uses the selected
  plan and companions plus an optional `execution_result`; missing result
  material is reported as `unknown`.
- PVE template: `recipe` is an independent input. Build plans use the recipe;
  apply uses a selected `template_preview`, `execution_admission` and explicit
  SSH files; verify uses a selected `template_receipt`. The helper target names
  one explicit node and does not use the VM root.
- K3s: `ssh_key`, `known_hosts`; preflight/deploy/upgrade also `runtime_secrets`
  (the existing protected JSON contract); upgrade adds `observed_versions`.
  Options include explicit `preflight_mode` and `upgrade_target` when applicable.
- OPNsense diagnose: `inventory`, `request`. Inventory must be self-contained,
  with existing API host/TLS variables. A request selecting details writes them
  under the private diagnostics directory. API credentials come from
  `OPNSENSE_API_KEY` and `OPNSENSE_API_SECRET`.
- Switch diagnose: self-contained `inventory` and `known_hosts`; the existing
  `SWITCH_SSH_USER`, `SWITCH_SSH_PASSWORD`, `SWITCH_SSH_PORT` environment channels.
- Foundation health: CA files are explicit aliases, associated with their
  inventory paths through `options.ca_files`.

- OPNsense workflow: `read` uses `inventory` and `request`; `plan` uses
  `inventory`, `request` and every explicitly declared standard resource input;
  `apply` and `verify` use `inventory` and `candidate`. A recovery plan uses
  `inventory`, `request` and `recovery`, with no desired inputs. The request
  controls the execution selection while the plan candidate retains the complete
  declared context. API credentials use `OPNSENSE_API_KEY` and
  `OPNSENSE_API_SECRET`.

For OPNsense `read`, `components.opnsense.options.include_system: true` includes
confirmed system and derived object details in the selected view. It is a strict
boolean accepted only by `read`. The default view retains unknown objects and
unsupported user configurations. Complete scoped observations are saved separately
in `diagnostics/observations.json`; the `result.json` display projection is not an
execution snapshot. Workflow candidate/result/recovery formats are v3; re-plan old
candidates and retain old recovery evidence for explicit reconciliation.

```sh
iaas run --runtime-config runtime.json \
  --environment docs/examples/opnsense-workflow/environment.yml \
  --engine local --component opnsense --operation plan \
  --scope firewall --output ./opnsense-plan

iaas run --runtime-config runtime.json \
  --environment apply-environment.yml \
  --engine local --component opnsense --operation apply \
  --scope firewall --execution-id fw-apply-001 --output ./fw-apply-001
```

The apply environment must carry the candidate file and options bound to the same
candidate bytes. Its options require `candidate_sha256`, `execution_id` and
`activation_check`, with optional boolean `check_mode`; the activation check repeats
the candidate digest and execution ID and records the target connection identity,
`checked_no_pending: true` and `serialized: true`. The launcher passes the execution ID to discovery and runtime,
requires it for OPNsense apply, and requires the output directory basename to match.
These checks bind the workflow; they do not establish device data-plane success or
production acceptance.

Adjacent undeclared `group_vars`, files and secrets directories are not uploaded.
Secret files must be nonempty, owned by the execution user and inaccessible to
group/others. Known-hosts/CA files must not be group/other writable. The launcher
preserves input ownership/mode, forwards selected environment names instead of
putting secret values in command arguments, and never forwards `OP_*` bootstrap
credentials. Standard AWS file environment channels are explicitly transferred
and mapped, or supplied by `aws_credentials`, `aws_config`, `aws_ca` and
`aws_web_identity` aliases. S3 configuration stays with the caller.
An explicit AWS file alias takes precedence over its corresponding host file
environment variable. Discovery does not request that overridden variable, so a
stale host path is neither read nor uploaded. Foundation services with no health
probe (`health_check: null`) retain their `SKIP` result without blocking others.

## Local Docker and DinD

Choose `--engine local` only when the daemon can bind the client's declared
paths. It mounts individual selected files read-only and uses an independent
task output directory. A failed bind stops the operation.

Choose `--engine dind` when client and daemon filesystems differ. It uploads
selected files using Docker's archive transport, uses task-specific named volumes,
and collects results back into the client. It does not assume host path sharing.
The engine must support named-volume file subpaths; local tests used Docker
29.5.2 and a nested 29.8.0 daemon. A short root-owned transfer container only
prepares volume permissions; operation containers use the client's UID/GID.

The launcher uses the caller's Docker context or `DOCKER_HOST`. Never overlap
state/snippet workflows: CI must serialize the complete plan/apply sequence, and
local callers must avoid simultaneous runs against the same target.

## PVE read, plan, apply, verify and recovery

```sh
iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation read \
  --scope ROOT_ID --output ./pve-read

iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation plan \
  --scope ROOT_ID --output ./planned

iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation apply \
  --scope ROOT_ID --plan ./planned/plan/plan.tfplan \
  --companions ./planned/plan --execution-id pve-apply-001 \
  --output ./pve-apply-001

iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation verify \
  --scope ROOT_ID --plan ./planned/plan/plan.tfplan \
  --companions ./planned/plan --output ./pve-verify
```

Review the private `plan/review.txt` and select the native plan explicitly. Retain
its complete companion directory. `summary.json` records `companion_files` for
the original declared root files and any supplied dependency archive. Admission
checks their presence before backend initialization or SSH writes, using the
saved list rather than current input declarations. Plans without this list must
be prepared again; do not reconstruct it from an incomplete directory. Existing
plan, lockfile and snippet digest checks remain. Upgrading the runtime invalidates
saved plans from another image digest; prepare a new plan explicitly. Changing
the runtime selection or adding an environment entry does not migrate source
files/state. Set `components.pve.options.destroy: true` for a reviewed delete
plan; it still travels through the ordinary `plan` and `apply` operations.

Independent `verify` reports current configuration against the retained plan
expectation. Its success does not change an earlier failed execution or prove
that a replacement completed: `original_phase`, native execution, state
persistence and collection facts remain separate, and the original result is
never rewritten. Required caller-owned guest/business acceptance remains a
separate gate.

Creation conflict checks and deletion verification confirm VMID absence through
the cluster resource list after checking the token's effective `VM.Audit` on
each selected `/vms/<vmid>` path. A permission-filtered empty list or a failed
configuration request is not evidence of absence; unavailable permissions or
an incomplete list block planning or leave verification unknown.

Template build and cleanup use the independent `pve-template` component. The
recipe, preview, execution admission and receipt are separate from the VM root.
Online template operations use explicitly mapped SSH key/known_hosts files and
the fixed node helper; caller-supplied helper commands are rejected. They do
not forward VM API or S3 credentials.
Cleanup carries an explicit VMID, original execution, ownership and management
status. The old `prepare-plan` and `apply-saved-plan` names are rejected with a
migration message, as are the old Make write entrypoints.

Results contain `generated`, `diagnostics`, `plan`, `recovery`, `work` and summaries.
`input-provenance.json` records the environment repository revision and dirty
status when optional Git is available; otherwise it explicitly reports unavailable.
It does not attest referenced files outside that repository or prove input bytes.
Sensitive captures and state use private files under a mode-0700 task directory.
Online failures return the real phase exit code. Cancellation is forwarded to the
container and native child before collecting results. Do not interpret earlier
successful uploads as rolled back when a later apply fails or rejects a stale plan.

Successful collection normally removes the task's temporary containers/volumes.
Failed collection, unconfirmed completion or incomplete recovery retains task
resources and reports their name prefix plus local metadata directory. Inspect
only that task's resources. Copy and verify recovery materials before manually
removing them; there is no automatic state push, force-unlock or retry apply.
After ordinary successful recovery export, both original and exported recovery
files are included in the returned task tree.

## Verification boundaries

Historical checks cover local Docker, independent DinD transfer and synthetic
state recovery. AMD64 ran through emulation on Apple Silicon; later native ARM64
checks covered local execution, not DinD or S3 failure recovery. These checks do
not qualify real facilities or a shared CI environment. See the
[verification scope and exceptional failures](runtime-adaptation-validation.md).

## Native ARM64 builds

Docker Buildx is required. Build one architecture at a time, using distinct tags
and cache directories when retaining both architectures:

```sh
RUNTIME_PLATFORM=linux/arm64 make runtime-build RUNTIME_IMAGE=iaas-runtime:arm64
make runtime-tofu-check RUNTIME_IMAGE=iaas-runtime:arm64
uv run python automation/runtime/inspect_image.py --image iaas-runtime:arm64
```

For Colima, point `TMPDIR` at an existing shared host directory before running
the smoke check; macOS's default `/var/folders` temporary directory may not be
mounted into the VM.

The default local build remains `linux/amd64`. PR/push and Release CI check both
architectures serially using native runners and separate caches. A published
Release builds and tests both images, transfers the tested artifacts without
rebuilding, then publishes one version tag containing both architectures.
Docker selects the matching image when pulling that tag; the launcher still
requires explicit platform selection. The launcher requires a repository digest reported by the Docker
daemon; if a locally loaded image lacks one, push/pull it through a caller-managed
registry. Distribution to other machines must provide an ARM64-compatible tag or digest.

Release publication requires [Docker API 1.49+ for platform-specific inspection](https://docs.docker.com/reference/cli/docker/image/inspect/).
The image validation, build, publish and anonymous-consumption jobs install the
same Docker CLI and Engine version, 29.5.2, with the containerd image store enabled.
They retain explicit platform selection and set `DOCKER_HOST` so temporary
authentication directories cannot switch publication or anonymous checks back to
the runner's preinstalled daemon. Buildx continues to build each selected platform.
The version tag (for example `v1.2.3`) points to a two-platform manifest;
`v1.2.3-amd64` and `v1.2.3-arm64` retain the individual tested images. The workflow
reserves six characters for these suffixes, limiting release tags to 122 characters.
It reports the shared manifest digest and verifies anonymous consumption on both
architectures. Existing tags are never overwritten: retries must reuse the same
tested artifacts. If only one architecture was pushed before failure, retry the
publish job with those artifacts. A full rebuild that changes image identity
requires a new release version. Historical single-architecture versions remain
unchanged. See the [validation record](runtime-adaptation-validation.md) for
local test results; workflow configuration does not mean a release has run.

The existing Darwin ARM64 launcher can select the ARM64 container on Apple
Silicon. Native Linux ARM64 launcher packaging is separate from image building.
The runtime reports its actual architecture, and rejects a mismatch before an
operation. Caller-supplied providers and dependency bundles must support that
architecture. Host image architecture does not change PVE guest/template
architecture or qualify real PVE, K3s, OPNsense or template builds.
