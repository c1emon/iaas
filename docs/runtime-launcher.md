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
version `1`; runtime environment schema `1`; PVE plan metadata `2`; PVE result
`1`; image artifact/build/test contracts `1`; and PVE template preview/result/
record `2`. Image construction is a local QEMU capability and PVE template
publication is a controller-side HTTPS capability. A capability response is
the compatibility gate: old PVE operation names and combined template-build
inputs are rejected instead of being silently translated.

## Controlled network proxy

For operations whose effective effects allow network access, the launcher accepts
`HTTP_PROXY/http_proxy`, `HTTPS_PROXY/https_proxy` and `NO_PROXY/no_proxy` as a
separate channel from facility credentials. Trimmed empty values are absent;
nonempty values in a pair must match exactly. Each selected value is passed in
both cases. HTTP and HTTPS settings are independent. A nonempty setting, including
only NO_PROXY, requires runtime `network_proxy_version: 1`.

Endpoints must use `http://` or `https://`, a valid host and optional port, with
no query, fragment or path other than `/`. Basic userinfo is supported, including
valid percent encoding; usernames must be nonempty and passwords may be empty.
Resolve authentication in the caller environment, never in command arguments or
input YAML. The daemon administrator can inspect container environment values.
Proxy authentication is protected in runtime errors and persisted tool diagnostics;
native state and recovery files keep their existing handling. Proxy values are
not added to saved plans, summaries or dependency archives.

Local and DinD execution use the same controlled channel. All helper containers
and offline execution explicitly clear supported and ALL_PROXY/FTP_PROXY names,
overriding Docker client proxy defaults and image ENV. Offline operations retain
`--network none` and do not parse proxy settings. Proxy names are reserved against
case-insensitive cloud-init credential-name conflicts. Arbitrary host variables,
SOCKS/FTP proxies and ALL_PROXY are not forwarded.

The channel covers actual network tool subprocesses and existing environment-aware
clients such as image base downloads through urllib. PVE explicit HTTPS clients,
uploads and template downloads retain their direct transports. It does not proxy
SSH, raw sockets or Docker daemon image pulls, and is not an egress firewall.
NO_PROXY uses each tool's native matching rules; no internal address is added
automatically. The endpoint must be reachable from the runtime container; DinD
localhost identifies its container, not the caller host.
For a remote TCP Docker daemon, callers must include its control endpoint in
NO_PROXY so the Docker CLI can contact it directly when HTTP_PROXY is set.

No configuration preserves direct access. Invalid configuration fails before
network tools start; tool failures retain their nonzero phase result and protected
diagnostic location. There is no retry with proxies removed or TLS weakened.
`pve prepare-dependencies` retains no facility/backend/state inputs, readonly
provider locks and native checksum validation. Restore checks archive members and
lock equality; provider integrity additionally requires native readonly init using
the returned `.terraform/providers` directory as `-plugin-dir`.

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
| PVE template | check, read, plan, apply, verify | One explicit HTTPS PVE node |
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
- PVE template: `request` is an independent `pve-template-publish-request/v1`
  or action-specific cleanup/retire input. Plan uses the request and optional
  artifact evidence; apply uses a selected `template_preview`, complete
  `execution_admission`, protected artifact locator and API CA; verify uses a
  selected `pve-template-result/v2`. The target is one explicit HTTPS node and
  does not use the VM root.
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
ONE rc.19 consumption uses a nested Docker 29.8.1 daemon. Docker 28's file-subpath
mount failed before runtime startup in that environment; use a tested daemon.

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

Image build/test/clean and template publication use independent components.
The image artifact, publication request, preview, complete execution admission
and result are separate from the VM root. PVE template operations use the
HTTPS API token, CA and protected artifact locator selected for that operation;
they do not forward node SSH or S3 credentials. Cleanup and retire carry exact
current-object identities and caller ownership/dependency admission. The old
`prepare-plan`, `apply-saved-plan`, combined template build, force and helper
entrypoints are rejected with migration guidance.

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
uv run python automation/oci/checks/inspect_image.py --image iaas-runtime:arm64
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

### PVE 模板验收和 snippet 清理（当前合同）

`pve-template accept` 与 `pve snippet-cleanup` 使用独立的 v2 request/result，
capabilities 的 `lifecycle_versions` 分别声明 `acceptance_request`/`acceptance_result`
和 `snippet_cleanup_request`/`snippet_cleanup_result`；`operation_capabilities` 的
`pve-template.accept` 与 `pve.snippet-cleanup` 各自声明 `absolute_deadlines: true`。
launcher 拒绝版本缺失、不匹配或截止能力缺失，不从相对 timeout 推导新授权。
`execution_modes` 声明 `start` 写基础设施但不访问 state，`observe` 只读基础设施；
两种模式都只在新的 output 写收集结果。

调用方（例如 infra-ops）根据合法目标开始时间及已批准策略，计算并持久化
request 和 execution admission 中相同的 `deadlines`：

```json
{"deadlines":{"work_deadline_at":"2026-10-01T10:00:00Z","cleanup_deadline_at":"2026-10-01T10:05:00Z"}}
```

字段使用严格 UTC 秒精度 `YYYY-MM-DDTHH:mm:ssZ`，work 不晚于 cleanup；
`now >= deadline` 到期。示例时间仅说明格式，实际 start 必须使用当前有效的批准窗口。
两个期限进入 request 摘要与执行身份绑定，local/DinD 按原字节传输。
原生执行在 start 同时冻结两个 monotonic 上限，并在每次新的设施写入前检查对应期限；
helper v2 在验收上传/删除模式的最终 create/unlink 前检查截止。
升级 runtime 时须同步升级节点 helper，安装方式见下方操作文档。
launcher 能力检查只是兼容性准入，不能替代这些原生检查。

work 到期后只允许在 cleanup 窗口内清理已证明所属且无活动冲突的资源。
cleanup 到期停止新增写入并保留残留、活动任务及未知事实；已发出的操作
可能继续在设施完成，本地超时不能证明已取消或回滚。
`deadline_outcome` 与独立的 `facility_writes` 区分截止拒绝和本次写入事实；
资源存在性 unknown 不代表本次可能写入，整体结论仍遵守 unknown 优先。
清理成功不能把失败验收变成通过。

```yaml
schema_version: 1
environment: acceptance
components:
  pve-template:
    inputs: {}
    files:
      acceptance_request: ./acceptance-request.json
      execution_admission: ./acceptance-admission.json
      api_ca: ./pve-ca.pem
    options:
      execution_mode: start
```

```sh
iaas run --runtime-config runtime.json --engine local --environment acceptance.yml \
  --component pve-template --operation accept --scope pve1 \
  --execution-id accept-001 --output ./results/accept-001
```

观察时显式改为 `execution_mode: observe`，设置 `files.original_execution_dir` 为原输出
`diagnostics/execution` 目录（包含 request.json、journal.json 和可能存在的 result.json），
使用原 execution-id 和新的 output 路径。`pve-template read` 也可通过该目录查询原验收，
不需新 admission，不重放写操作。缺核心材料返回 unknown，不重建历史成功。

独立清理改用 component `pve`、operation `snippet-cleanup` 和
`files.snippet_cleanup_request`，通过 `files.cleanup_evidence_dir` 提供绑定证据，
必要时同时提供 `original_execution_dir`。目录在 local Docker 与 DinD 都只读映射；
只选择当前操作文件，不读取 backend 或 artifact_locator。
清理 SSH 使用 `files.ssh_key`、`files.known_hosts`，连接目标固定在清理 request 的
`ssh: {host: "pve1.example.invalid", user: "automation", port: 22}` 中，与请求摘要及 admission 绑定。
严格验证主机身份，不从 `PVE_SSH_HOST`、`PVE_SSH_USER` 或 `PVE_SSH_PORT` 环境变量选择目标。
验收不接收 artifact 下载凭据，清理不接收 state 后端凭据。
首次清理及补清理都必须是独立授权的新 start；observe 永远不自动补执行。
补清理使用新的 request/admission/execution_id 和有效 deadlines，保留原资源全清单、
所有权及 retry 关联；不得改写旧执行或延长旧窗口。observe 可在原期限过期后
读取原绑定材料，不刷新预算或重新启动副作用。

上述接口与软件测试不代表真实 PVE 验收；现场创建、启动和删除 VM 需另行限定目标和授权窗口。

观察已有 `accept-001`（新目录可位于另一个父目录，末级仍绑定原执行 ID）：

```yaml
schema_version: 1
environment: acceptance-observe
components:
  pve-template:
    inputs: {}
    files:
      original_execution_dir: ./results/accept-001/diagnostics/execution
    options:
      execution_mode: observe
```

```sh
iaas run --runtime-config runtime.json --engine local --environment observe.yml \
  --component pve-template --operation accept --scope pve1 \
  --execution-id accept-001 --output ./observations/accept-001
```

观察不需要新 admission，也不创建 API 客户端。原 request/journal/result 不完整时失败且无远程写入；
即使原结果 passed，观察结果收集失败也不能成功退出，launcher 保留任务存储供恢复。
请求字段和共享正反例见 [验收合同示例](examples/pve-acceptance/acceptance-request.json)。

安装与最小 sudo 权限见 [PVE snippet cleanup helper](operations/pve-snippet-cleanup.md)。

## Controlled acceptance recovery

PVE template `plan` with `options.action: recover` produces a read-only recovery
preview. `recover` requires explicit `execution_mode: start|observe`; start uses
new scoped v2 approval and current recovery v1 contracts, while observe reads the
already dispatched recovery directory without network or operation credentials.
See [run-120-1 commands, file mappings and evidence boundaries](operations/pve-acceptance-recovery.md).
