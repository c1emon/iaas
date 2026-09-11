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
sh automation/launcher/build.sh /tmp/iaas-launcher-build development
```

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
| OPNsense | check, generate, diagnose | One inventory host |
| switch | check, generate, diagnose (read-only facts) | Explicit comma-separated inventory hosts |
| PVE | check, generate, preflight, health, prepare-dependencies, plan / prepare-plan, apply-saved-plan | Cluster name for diagnostics; complete root ID for dependency/state operations |
| services | check, generate | — |
| foundation | check, generate, health | Declared environment name |
| K3s | check, generate / render, preflight, verify, deploy, snapshot, upgrade | Explicit VM references; deploy/upgrade use the complete cluster; snapshot uses its declared source |

K3s deploy, snapshot and upgrade write remote infrastructure. PVE apply also
writes infrastructure. Plan accesses state and uses its native lock. Supported
effects appear before execution and in the result. The new interface does not
accept arbitrary commands, direct apply, destroy or template builds. Existing
Make/container commands retain their previous interfaces.

Online component `files` aliases are explicit:

- PVE state: `backend`; saved apply also `ssh_key`, `known_hosts`. Root file
  mappings, `dependencies` and PVE target options are described in the saved-plan
  section of the environment guide.
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

## Saved apply and recovery

```sh
iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation prepare-plan \
  --scope ROOT_ID --output ./prepared

iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation apply-saved-plan \
  --scope ROOT_ID --plan ./prepared/plan/plan.tfplan \
  --companions ./prepared/plan --output ./applied
```

Review the private `plan/review.txt` and select the native plan explicitly. Retain
its complete companion directory. `summary.json` records `companion_files` for
the original declared root files (including helper scripts) and any supplied
dependency archive. Admission checks their presence before backend initialization
or SSH writes, using the saved list rather than current input declarations.
Plans without this list must be prepared again; do not reconstruct the list from
an incomplete directory. Existing plan, lockfile and snippet digest checks remain.
Upgrading the runtime invalidates saved plans
from another image digest; prepare a new plan explicitly. Changing the runtime
selection or adding an environment entry does not migrate source files/state.

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

Darwin arm64 and Linux amd64 launchers build locally. On Apple Silicon, local
Docker and a nested Linux Docker daemon ran the `linux/amd64` runtime through
explicit emulation. Offline generation, isolated input transfer and UID/mode
preservation passed. Local MinIO passed native synthetic state read/write, locking,
stale-plan rejection and outage recovery. A disposable Forgejo 15.0.8 / runner
12.13.2 job additionally passed native plan creation, an S3 write outage and
failed-result-collection retention using the separate DinD daemon. A Linux VM
client also passed local-bind execution. These are explicit amd64 emulation
results on an Apple Silicon host; native amd64 hardware and real facilities were
not qualified. See the [validation record](runtime-adaptation-validation.md).

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
