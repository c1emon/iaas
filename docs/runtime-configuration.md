# Runtime configuration

The versioned entry selects caller-owned component documents; it does not replace
their existing domain schemas. Configuration-relative paths resolve against the
entry file. `$ref` nodes in selected documents resolve named facts from that entry.
No shell expansion, template evaluation or recursive scenario merge is performed.

```yaml
schema_version: 1
environment: lab
facts:
  network: ./network.yml
components:
  opnsense:
    inputs:
      aliases: ./router/aliases.yml
scenarios:
  maintenance:
    opnsense:
      inputs:
        aliases: ./router/maintenance-aliases.yml
```

The default `components` mapping is used without `--scenario`. A selected scenario
replaces each component mapping it names, in full; other components retain their
default mapping. Unselected scenes and unused fact files are not loaded.

Each component mapping accepts `inputs` (named YAML documents), `files` (explicit
auxiliary file paths), and `options` (operation options). Required domain inputs:

| Component | Input names | Non-sensitive generation |
| --- | --- | --- |
| pve | cluster, vms | tfvars, Ansible inventory, VM documentation, template build parameters |
| services | services, vms | service documentation |
| foundation | inventory | recovery documentation |
| k3s | intent, inventory | composed K3s review |
| opnsense | aliases, vips, gateways, filter-rules, dnat, one-to-one-nat, interface-groups | validated standard desired-state YAML |
| switch | config | validated collection-native configuration YAML |

Caller-authored Alias/Rules files may be hand-written or deterministically generated.
Both use the same standard fields, validation and source selection. High-level policy
compilation and migration staging belong to the caller; iaas has no policy input mode.
Gateway/VIP inputs continue to reference the original base source files.

An entire reference node looks like `{ $ref: facts.network.management }`.
The reference preserves the fact's type; the existing component validator checks
the resolved document. Missing and cyclic reachable references fail. Independent
policy fields remain independent even when their values happen to be equal.
Selecting a field through an intermediate alias reads only that field's dependency
closure, just like direct selection; unrelated sibling references are not expanded.
Invalid schema versions, unknown scenarios and malformed references report safe
field or error descriptions through the runtime and launcher. Source values and
raw YAML/domain-parser exceptions remain excluded from public diagnostics.

Two synthetic layouts are provided: [flat](examples/runtime/flat/environment.yml)
and [facility-oriented](examples/runtime/facility/environment.yml). Both select the
same input facts without requiring an internal Ansible directory structure.

For development, run the offline compiler through the project environment:

```sh
PYTHONPATH=automation/src uv run python -m iaas_automation.runtime_config \
  --environment docs/examples/runtime/flat/environment.yml \
  --component opnsense --operation check
```

`generate --output <new-directory>` writes only the selected component's derived
files. It refuses existing destinations and overlap with source files or runtime
implementation resources, including resolved symlinks. Source documents are not
rewritten. Existing directory/file commands remain supported; migration is an
explicit new entry pointing at existing documents, not an automatic conversion.

The separate caller-owned runtime selection contains `interface_version: 1`, an
explicit `image` release tag or digest, and `platform: linux/amd64` or
`platform: linux/arm64`, matching the selected image. `latest`, missing tags and
unknown interfaces are rejected; Apple Silicon can select a native ARM64 image
or explicitly select AMD64 emulation. See the launcher guide for the ARM64 build
and publication boundary. Backend locations
and credentials belong to caller configuration, never these synthetic examples.

See the [native launcher guide](runtime-launcher.md) for installation, local/DinD
execution, component scopes, credentials and recovery.

## OPNsense workflow selection

The OPNsense configuration workflow uses four operations: `read`, `plan`, `apply`
and `verify`. Its files are explicit aliases. `inventory` is always required;
`request` is required by `read` and `plan`; `candidate` is required by `apply` and
`verify`; `recovery` is optional for `plan` and is mutually exclusive with desired
resource inputs. A request is always the source of the execution selection.

```yaml
components:
  opnsense:
    inputs:
      aliases: opnsense/aliases.yml
      dnat: opnsense/dnat.yml
    files:
      inventory: opnsense/inventory.yml
      request: opnsense/request.yml
```

The plan loader validates and loads every explicitly declared standard resource
input, including inputs that the request does not select. This keeps the candidate
context complete while `request.selection` controls the managed execution set.
Unknown input names fail before credentials are prepared. `read` loads only the
request and `apply`/`verify` load only the candidate; they do not load desired
resource inputs. A recovery plan loads `request` and `recovery` and no desired
inputs.

The request has `schema_version: 1` and a `selection` mapping whose identities are
the stable identities defined by the resource validators. `selection: {aliases: all}` selects
all records from the declared aliases file (and all observed aliases for read). An explicit list selects identities
such as `[SYNTHETIC_WEB]` for an alias or
`[iaas:opnsense:dnat:synthetic:web]` for DNAT. Unknown resources and undeclared
identities are rejected.

`read`, `plan` and `verify` require an empty `options` mapping. `apply` requires
`candidate_sha256`, `execution_id` and `activation_check`, and may additionally set
the boolean `check_mode`. The digest is a lowercase SHA-256 of the candidate bytes;
the execution ID is a bounded token. The activation check contains the target
connection identity, the same candidate digest and execution ID, plus
`checked_no_pending: true` and `serialized: true`. The
launcher also binds the execution ID to the new output directory basename and
checks the runtime discovery response. The caller must choose a fresh execution ID
and maintain serialization through activation; this is not a distributed lock or replay registry.

## S3 and protected process results

The state execution layer consumes a caller-supplied JSON file with `workspace`
and `config` fields. `config` is native OpenTofu S3 backend configuration and must
include `bucket`, `key`, `region`, and `use_lockfile: true`. A non-default workspace
also requires an explicit `workspace_key_prefix`. Custom S3 `endpoints` and the
service's necessary compatibility options remain caller-owned. Prepare the bucket
with versioning before invocation. Credentials are injected separately through
selected AWS environment variables or protected credential files.

An S3 backend override is written only in a fresh task copy of the selected root.
No caller source or existing state is rewritten. Existing local state/backend
metadata is rejected for initialization rather than automatically migrated.
Dependency files may already be prepared; init preserves the provider lockfile.
This uses native [S3 locking](https://opentofu.org/docs/language/settings/backends/s3/)
and [backend override semantics](https://opentofu.org/docs/language/files/override/).

Each task has separate generated, diagnostics, plan, recovery and work directories.
Raw tool stdout/stderr is captured privately before starting the child process;
it is never forwarded directly to container/CI logs. Failure or cancellation
preserves the real exit status. An emergency state dump, including one emitted
when both S3 and local recovery-file writes fail, stays in protected capture.
File capture uses mode 0600. If capture cannot be prepared, the operation does not
start. If capture fails during execution, the stream is drained without public
fallback and the summary reports recovery completeness as unconfirmed.

The original `errored.tfstate` remains until result collection is complete. Failed
recovery export retains the original storage and does not turn execution failure
into success. No automatic state push, apply retry or force-unlock is performed.
Inspect protected recovery materials before authorizing manual recovery.

Software tests and local synthetic S3 tests cover this execution layer. Exact
platform and CI acceptance boundaries remain recorded in the change tasks and
launcher guide.

## Saved native plans

The new execution layer prepares a native plan alongside `inputs.tfvars.json`,
the declared root files, provider lockfile, rendered snippets and their manifest.
The manifest binds the native plan through `plan_sha256`. Applying from another
directory checks the selected root, workspace/backend, image digest and this
binding before any SSH upload; it uses the saved inputs and does not render new
password hashes or replan. Empty VM selections need no snippet upload. The legacy
cloud-init upload interface retains its existing nonempty-artifact requirement.

Root inputs are explicit: component `options.root` contains `id`, relative
`directory`, and `files` mapping relative destinations to aliases in component
`files`. Include `.terraform.lock.hcl`; exclude state and caches. Executable owner
permission is preserved for caller scripts. `options.pve` declares `storage_id`,
`ssh_host` and `ssh_user`. Plan/apply scope is the complete root ID.

`prepare-dependencies` is a separate network operation. Its `dependencies.tar.gz`
contains the caller-locked providers/modules. Supply it through the `dependencies`
file alias for later plan preparation. Plan/apply initialize with downloads
disabled and fail if a required dependency is absent. Saved companion artifacts
include that archive when provided. Keep the entire plan directory private.

Apply runs backend initialization, snippet upload, snippet verification, then native
saved-plan apply. A failure stops following phases. Native stale-plan rejection
can happen after snippets were overwritten; there is no automatic rollback or
retry. The caller must serialize the complete workflow. Shared locks and immutable
snippets remain deferred work.
