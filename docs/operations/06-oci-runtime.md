# OCI runtime

The [native launcher](../runtime-launcher.md) requires a runtime image exposing
interface version 1 through `capabilities`. The same response advertises the
versioned lifecycle contracts consumed by callers:

```json
"lifecycle_versions": {
  "pve": {"plan": 2, "result": 1},
  "pve-template": {"preview": 1, "receipt": 1, "helper": 2}
}
```

Select a published version compatible with the launcher interface and these
component contracts, then pin its repository digest. Historical `v0.1.0-rc.2`
provides only the legacy Make interface and is not launcher-compatible.

Builds support Linux amd64 and arm64; the Release workflow publishes both under
one version manifest. Use the digest from the selected successful release;
workflow configuration alone does not prove publication. See
[build and publication rules](../runtime-launcher.md#native-arm64-builds) and
[environment configuration](../runtime-configuration.md).

## Directory and command interface

The native launcher selects its environment and operation explicitly:

```sh
iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation plan \
  --scope synthetic-root --output ./pve-plan
```

The selected environment owns authored cluster/VM inputs, an explicit OpenTofu
root and caller-owned backend/admission files. Runtime outputs contain generated
inputs, review, native plan, snippets, recovery material and protected results.
Keep those outputs separate from authored source and do not upload an undeclared
directory.

There is no implicit Astra selector or external state path. The old `ASTRA`
selector, old `ASTRA_PVE_SSH_TIMEOUT_SECONDS`, and the old Make write commands
return migration errors. The new SSH timeout variable is
`IAAS_PVE_SSH_TIMEOUT_SECONDS`. Existing PVE hosts must finish the separate
[helper cutover](pve-helper-cutover.md) before online helper calls.

K3s retains its explicit intent, inventory, scope and protected-secret file
inputs. This packaging change does not qualify a cluster or repair handoff logic.

Example offline capability invocation with readonly inputs and caller-owned
outputs:

```sh
docker run --rm --network none --read-only \
  --user "$(id -u):$(id -g)" --tmpfs /tmp:rw,mode=1777 \
  -v /absolute/environment:/environment:ro \
  -v /absolute/output:/output \
  -e RUNTIME_CONFIG=/environment/runtime.json \
  'ghcr.io/<owner>/iaas-runtime@sha256:<digest>' capabilities
```

Create the output directory as the invoking user first. Startup creates a private
writable home under `/tmp`; an explicitly supplied HOME must also be writable.
No-argument invocation prints help without creating outputs or contacting a
provider. Offline operations do not install dependencies. Checkout-only test,
lint and aggregate `check` commands are not advertised as container operations.

## Credentials belong to the caller

IaaS accepts resolved environment variables or protected files. The image does
not contain `op`, authenticate to 1Password, or require its service token.

For 1Password, the caller owns `op run`, reference-only templates, authentication
and CI service-account permissions. For example, on a runner with op installed:

```sh
op run --env-file=/private/pve.env.tpl -- \
  docker run --rm --user "$(id -u):$(id -g)" \
    -v /absolute/environment:/environment:ro -v /absolute/output:/output \
    -e ENVIRONMENT_DIR=/environment -e OUTPUT_DIR=/output \
    -e TF_VAR_pve_endpoint -e TF_VAR_pve_api_username \
    -e TF_VAR_pve_api_token_id -e TF_VAR_pve_api_token_secret \
    'ghcr.io/<owner>/iaas-runtime@sha256:<digest>' pve-health
```

Traditional CI Secrets inject those same named variables and invoke Docker
directly, omitting `op run`. Do not put secret values in command arguments.
Pass only operation inputs into the container, not `OP_SERVICE_ACCOUNT_TOKEN`.
Neither method silently falls back to another provider when inputs are missing.

SSH keys/known_hosts and K3s secret JSON use explicit readonly mounts. Keep
protected-file ownership and restrictive modes compatible with the invoking UID.
K3s JSON reference keys identify entries in the supplied mapping; they do not
cause 1Password reads. Do not weaken SSH host-key checks or file checks to make
container execution work. See [credential inputs](00-preparation-and-conventions.md#04-运行时凭据与文件权限).

The private deployment pipeline owns service identities, runner network access,
backend, persistent state, locking and deployment authorization. Public build
jobs need none of those credentials; GHCR publication uses its separate temporary
`GITHUB_TOKEN` only in the publish job.

## Caller-owned OpenTofu root

The module source inside the image is the literal path
`/opt/iaas/automation/opentofu/modules/pve-cloudinit-vm`. Pinning the image digest
pins that module. See the [synthetic root](../../tests/fixtures/runtime-root/main.tf)
and its committed provider lock for a backend-disabled example.

The caller owns the root and `.terraform.lock.hcl`; the runtime materializes only
the explicit `options.root.files` mapping into its private task workspace. The
root must declare one supported Proxmox provider, fixed API/TLS selection and
ephemeral sensitive credential variables. Provider downloads belong to the
separate dependency preparation operation. Actual deployment uses the selected
S3 backend and native lock; local state migration is not supplied.

## Build and validation

```sh
make runtime-build
make runtime-smoke
make runtime-tofu-check
uv run python automation/runtime/inspect_image.py
```

These repository checks use synthetic inputs. Generation runs offline; the
OpenTofu check permits locked provider downloads. They do not validate real
infrastructure.

Dependency installation precedes repository source copying. Final dependency
and source layers are separate. Code-only builds reuse dependency caches;
dependency lock/installation changes legitimately invalidate them. CI persists
BuildKit's local cache through Actions cache without GHCR credentials. Cache loss
may require a fresh install; it does not change pinned dependency selection.

## Release, visibility and reruns

The release workflow handles only `release.published` with stable `vX.Y.Z` or
prerelease `vX.Y.Z-suffix` tags (OCI-compatible SemVer without build metadata).
Draft creation, edits, tag-only pushes and ordinary PR/main checks do not publish.
The exact tagged commit is validated. The publish job loads the tested image
artifact and checks its image ID; it does not rebuild it.

Canonical tags are `ghcr.io/<lowercase-owner>/iaas-runtime:<release-tag>`; there
is no mutable `latest`. The image has source, revision and version OCI labels.
Publication is serialized per tag. If absent, a version can be retried after a
failure. If present, its labels must match; it is not overwritten. Conflicting
source requires a new version. Authentication/network lookup failures do not
count as evidence of an absent image.

The authorized package owner must configure the GHCR package as public; public
repository visibility is insufficient. A fresh job anonymously pulls the digest
and invokes help before reporting public consumption success. A push can succeed
while this check fails: fix visibility and rerun, retaining the existing version.
A visible GitHub Release alone is not evidence that its image is consumable.

GitHub suppresses a follow-on release event created by another workflow's
`GITHUB_TOKEN`. Future Release automation must explicitly arrange publication or
use an appropriately scoped GitHub App identity. This change does not automate
Release creation. Rollback selects an older known compatible image digest; it
does not roll back infrastructure or state.
