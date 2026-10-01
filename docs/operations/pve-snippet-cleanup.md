# PVE snippet cleanup

`iaas run --component pve --operation snippet-cleanup` runs an independent,
evidence-bound cleanup. It never initializes OpenTofu/S3 or clones, deletes or
changes a VM. Use a new execution ID/admission for a new cleanup attempt; use
`options.execution_mode: observe` and a read-only original execution directory
for a repeated execution ID.

Install helper protocol v2 on each node used for cleanup, after provisioning the
existing automation account and known-host trust:

```sh
ansible-playbook -i inventory automation/ansible/playbooks/pve/bootstrap-pve-snippet-cleanup.yml \
  -e pve_bootstrap_user=YOUR_EXISTING_AUTOMATION_ACCOUNT
```

This installs `/usr/local/sbin/iaas-pve-snippet-delete` and a dedicated sudoers
rule validated by `visudo`. Python 3, `pvesm`, a quorate pmxcfs cluster and its
complete `/etc/pve/nodes` configuration view are required. The account receives
only this helper, with no arbitrary shell/rm permission. Existing upload
permissions remain independent. This is an installation recipe, not evidence
of installation on any live node.

After both helper bootstraps, use the same SSH account to probe the restricted
commands with `sudo -n /usr/local/sbin/iaas-pve-snippet-upload --capabilities` and
`sudo -n /usr/local/sbin/iaas-pve-snippet-delete --capabilities`. Each returns
`schema_version: "helper-capabilities/v1"`, its `helper` identity,
`protocol_version: 2`, and boolean `capabilities`. Upload declares `acceptance`,
`create_only`, `verify`, and `deadline`; delete declares `inspect`, `exact_delete`,
`reference`, `digest`, and `deadline`. Probe arguments must be used alone. Probes
do not read stdin, invoke pvesm, inspect cluster configuration, create directories
or acquire a lock. Missing pvesm makes dependent capabilities false; upload also
checks PyYAML for verification. Missing Python or a refused sudo command makes
the helper unavailable. Admission must refuse missing required capabilities;
`--help` success alone is insufficient. Cluster/storage/node usability is checked
separately by online admission, rather than inferred from this declaration.

Installation checks that `/usr`, `/usr/local` and `/usr/local/sbin` are existing
root-owned directories without group/other write permission or symlinks. If
this check fails, an administrator must resolve the directory ownership or
permissions; the playbook does not change existing directory permissions.

Pass isolated `files.ssh_key` and `files.known_hosts`. Fix `ssh.host`, `ssh.user`
and `ssh.port` in the cleanup request; all three are covered by its digest and
execution admission. The SSH host must be the original VM's node; the helper
verifies its pmxcfs local identity. Ambient `PVE_SSH_*` values cannot select or
override the connection target.
SSH agent authentication and ambient SSH config are disabled. API credentials
are not needed by the cleanup helper.

Start requires `files.snippet_cleanup_request`, `files.execution_admission`, and
read-only `files.cleanup_evidence_dir`. Every request evidence reference is a
relative regular file plus its SHA-256. Keep original request/journal and
result materials protected; generated summaries expose statuses, not contents.

For deployment origin, reference the original snippet manifest and the original
deployment `pve-result.json` as ownership manifest/upload. `record_ref` is the
manifest entry's `file_name`. The saved delete-plan `summary.json`, apply
`execution-context.json` (its admission), and delete `pve-result.json` bind
approved plan, native UUID, exact VM absence and persisted backend state.
`deletion_evidence.native_task` is `opentofu-apply`, backed by the recorded native
execution result. The result's native expectations must retain the original
VM UUID; incomplete older evidence is refused, not reconstructed.

For acceptance origin, request/journal are the original acceptance materials.
The deletion result, VM absence and ownership references all select the original
journal with its exact `temporary_vm`, `vm_delete` and `snippets` records. Each
snippet row retains `vmid`, `file_name`, `file_id`, `sha256`, and `uploaded: true`.
The delete UPID must be a succeeded terminal journal task. The current acceptance
operation uses native cloud-init parameters and normally creates no snippets;
this branch supports explicitly recorded dedicated snippets, not inferred files.

The root helper compares the cluster `.vmlist` with every QEMU/LXC configuration
and scans the whole config text, including pending and snapshot sections.
Missing/malformed/inaccessible configuration or lost quorum prevents mutation.
Filename references are matched across *all* storage aliases and nodes. Thus a
same-named reference on an unrelated storage conservatively retains a file;
this is deliberate and is reported as `referenced`. A configuration reference
does not prove the file exists, so its residual existence can remain unknown.

The caller must retain the admitted complete mutation serialization context
through scanning and deletion. The helper repeats the full scope/VM-absence
check immediately before each file and uses no-follow directory/file handles,
original digest/inode checks, exact unlink and an absence recheck. Missing
parents, symlinks and inaccessible paths never count as an absent file.

Retain `diagnostics/execution` outside the temporary runtime. Map that directory
as `files.original_execution_dir` for observe. A retry uses a new execution ID
with previous request/journal/available-result references and the unchanged
original ownership list. Only the timeout, deadlines and retry association may change.
An interrupted SSH mutation stays active/unknown; a new retry must wait for
protected evidence that the original mutation terminated. Never edit old
journals to invent termination or overwrite the original acceptance result.

Protocol v2 requires `--deadline-at YYYY-MM-DDTHH:mm:ssZ` for both cluster
inspection and exact deletion. The runner supplies the work cutoff during
admission and the cleanup cutoff during compensation. Offsets, fractional
seconds, invalid calendar dates and missing values are refused. At `now >=
deadline` the helper stops; after cluster/reference and digest/inode checks it
checks again immediately before unlink. Its pvesm subprocess timeout is bounded
by the remaining window, and the nonblocking lock never waits beyond it. An
expired delete returns `schema_version: 2`, `status: failed`, and
`reason_code: cleanup_deadline_expired`; it does not claim the file is absent.

Install the current upload helper using the existing SSH-user bootstrap when
acceptance uses snippets. Acceptance calls must explicitly select `--mode
acceptance --deadline-at WORK_CUTOFF` with `--create-only` or checksum verification.
Ordinary cloud-init upload keeps its existing default `ordinary` mode without a
deadline. Acceptance cannot downgrade to ordinary mode after helper rejection.
The upload helper checks immediately before directory/file creation and bounds
pvesm, mount inspection and input waits to its remaining work window.

Node and runner UTC clocks must be reasonably synchronized. Each helper freezes
a monotonic upper limit at process start; wall clock jumps only tighten that
limit. A runner SSH timeout does not prove the remote helper stopped or rolled
back an issued unlink/create. Preserve unknown/active evidence until confirmed,
and use a newly admitted request with new deadlines for later cleanup rather
than extending the old execution.
