# Native runtime launcher

The launcher runs the versioned container interface. The caller host needs the
launcher binary and Docker CLI connected to its selected daemon. Python, Ansible,
OpenTofu and 1Password are not launcher host dependencies. Resolve credentials
before invocation using the caller's existing secrets system.

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
`latest`, missing tags, unsupported interface/schema versions and native arm64
images are rejected. `iaas prepare --runtime-config runtime.json` explicitly pulls
the selected image. Normal operations never implicitly pull an image. Tags are
resolved to a repository digest for execution and saved-plan compatibility.
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
its complete companion directory. Upgrading the runtime invalidates saved plans
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

Native Linux arm64 is not advertised by the current image contract:

| Layer | Current assessment |
| --- | --- |
| Python / Ansible | No new architecture-specific domain logic; the complete dependency image is qualified only for the selected amd64 runtime |
| uv / OpenTofu / Packer | Dockerfile download URLs, checksums and copied executable paths explicitly select x86_64/amd64; native arm64 needs a separate build selection |
| PVE provider | Caller-locked bpg/proxmox 0.111.1 prepared and reused as linux_amd64 under emulation; linux_arm64 provider execution is unverified |
| Launcher | Linux amd64 and Darwin arm64 deliverables; the runtime rejects linux/arm64 rather than silently selecting an incompatible image |
