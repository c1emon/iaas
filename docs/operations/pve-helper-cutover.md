# PVE helper naming cutover

The generic runtime calls `iaas-pve-template-build` and
`iaas-pve-snippet-upload`. Existing hosts using the `astra-pve-*` commands must
complete a separately authorized host cutover before running these online
operations. This software change does not install or remove anything on hosts.

1. Stop template-build and snippet-upload jobs. Confirm no old helper process
   or template-build lock owner remains.
2. Install the generic helper files from `automation/pve-node/bin/` and their
   matching sudoers from `automation/pve-node/sudoers.d/`. Validate sudoers with
   `visudo -cf` and retain the existing dedicated `pve-ops` identity and narrow
   command permissions.
3. Remove the old helper execution permissions, old sudoers entries and old
   entrypoints before resuming jobs. Do not leave both generations executable:
   their template-build lock names differ. The generic cache is
   `/var/cache/iaas/packer`; no cache migration is required by this release.
4. Check the installed helper help and the intended sudo permission as the
   dedicated identity, then resume the jobs using the generic runtime.

There is no fallback to old helper names and no broad sudo workaround.
Replace `ASTRA_PVE_SSH_TIMEOUT_SECONDS` with `IAAS_PVE_SSH_TIMEOUT_SECONDS`.
The snippet wrapper's test/execution override is now
`IAAS_PVE_SNIPPET_UPLOAD_PVESM`; the old variable fails with a migration message.
