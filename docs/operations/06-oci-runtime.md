# OCI runtime

The new [native launcher](../runtime-launcher.md) and
[environment configuration](../runtime-configuration.md) are implemented on the
runtime adaptation branch. They require an image exposing interface version 1
through `capabilities`; the historical release below retains the legacy Make
interface and is not a launcher-compatible release. Current implementation and
local test boundaries are recorded in [validation](../runtime-adaptation-validation.md).

This runtime packages reusable Python, Ansible and OpenTofu resources for
Linux amd64. Image publication is not infrastructure deployment or Forgejo
acceptance. The first publicly consumable prerelease is
[`v0.1.0-rc.2`](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.2), from
source commit `42fd9c82511de2d9a646e02e6f7bd7148b688f5a`:

```text
ghcr.io/c1emon/iaas-runtime@sha256:9feb560f05a059e37c7bfc0a6f7042bfe6d6a6510cf8edb86f498bd2c03cb5c8
```

[Release workflow 34185770926](https://github.com/c1emon/iaas/actions/runs/34185770926)
passed build, tested-image transfer, publication and anonymous digest pull/help
invocation on 2026-09-08. The anonymous job passed on attempt 2 after the owner
made the package public; the image was not rebuilt. An independent anonymous
pull/help check on wsx also passed. These are runtime software acceptance results.
The earlier `v0.1.0-rc.1` failed before publication and has no usable image digest.
For future versions, use only a digest reported by a successful release workflow.

## Directory and command interface

Both checkout and container commands select their environment explicitly:

```sh
make pve-generate ENVIRONMENT_DIR=/absolute/environment OUTPUT_DIR=/absolute/output
```

`ENVIRONMENT_DIR` contains authored `inventory/` and `ansible/` inputs.
`OUTPUT_DIR/generated/` receives generated Ansible, OpenTofu, Packer and document
files; `OUTPUT_DIR/runtime/` owns cloud-init, review files and state backups.
`GENERATED_DIR` can explicitly select an existing generated-only subtree, including
the selected environment's committed generated directory. It cannot overlap
authored input directories. Quote arguments containing spaces.

`PVE_DIR` selects an independent external OpenTofu working root for init, plan,
apply or destroy. There is no implicit Astra selection. The old `ASTRA` selector
and `ASTRA_PVE_SSH_TIMEOUT_SECONDS` fail with migration messages. The new SSH
timeout variable is `IAAS_PVE_SSH_TIMEOUT_SECONDS`. Existing PVE hosts must finish
the separate [helper cutover](pve-helper-cutover.md) before online helper calls.

K3s retains its explicit intent, inventory, scope and protected-secret file
inputs. This packaging change does not qualify a cluster or repair handoff logic.

Example offline invocation with readonly inputs and caller-owned outputs:

```sh
docker run --rm --network none --read-only \
  --user "$(id -u):$(id -g)" --tmpfs /tmp:rw,mode=1777 \
  -v /absolute/environment:/environment:ro \
  -v /absolute/output:/output \
  -e ENVIRONMENT_DIR=/environment -e OUTPUT_DIR=/output \
  'ghcr.io/<owner>/iaas-runtime@sha256:<digest>' pve-generate
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

## External OpenTofu root

The module source inside the image is the literal path
`/opt/iaas/automation/opentofu/modules/pve-cloudinit-vm`. Pinning the image digest
pins that module. See the [synthetic root](../../tests/fixtures/runtime-root/main.tf)
and its committed provider lock for a backend-disabled example.

The caller owns its root and `.terraform.lock.hcl`. Mount the working root
separately and invoke `docker run ... --entrypoint tofu IMAGE -chdir=/work/pve
init -backend=false -lockfile=readonly -input=false`, then `validate`. Provider
downloads require networking; these checks do not require API credentials or
state access. Actual deployment needs persistent state outside the container;
no backend or state migration is supplied here.

## Build and validation

```sh
make runtime-build
make runtime-smoke
make runtime-tofu-check
uv run python automation/runtime/inspect_image.py
```

These are repository commands, using synthetic external inputs. The smoke uses
the shipped entrypoint, disables networking for generation, and checks Ansible
resources, caller UID, credential inputs and representative failures. The
separate OpenTofu portion permits locked provider downloads only. Layer inspection
checks excluded content and retained license notices. These are software checks.

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
