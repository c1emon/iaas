# Debian 13 PVE template foundation

This directory documents the first template build path:

- source image: Debian 13 Trixie genericcloud qcow2
- build host SSH target: `cohe` by default
- local trigger: `build-template.sh`
- remote wrapper: `infra/pve-node/bin/astra-pve-template-build`
- remote cache: `/var/cache/astra/packer`
- generated env: `template-build.env` (committed, non-secret, sourced by the local trigger)
- template naming: `debian-13-tmpl-YYYYMMDD`

## Build flow

1. The local trigger validates the requested VMID/name and forwards the build to the selected PVE node over SSH.
2. The remote wrapper downloads or reuses the cached qcow2 in `/var/cache/astra/packer/downloads/`.
3. The wrapper always verifies the pinned SHA512 checksum before customization.
4. The wrapper customizes, syspreps, imports, and templates the VM on the PVE host.

Set `TEMPLATE_DEBUG=true` to keep the JSON step logs while exposing the underlying
`virt-customize`, `virt-sysprep`, and `qm` output.

The wrapper writes a temporary deb822 `debian.sources`, removes stale
`/etc/apt/sources.list`, and runs `apt-get update` before package installation.
It also runs `cloud-init clean --logs || true` after installing cloud-init, then
uses virt-sysprep for the remaining cleanup operations.

`PVE_HOST` must be set explicitly to the selected build node SSH host. Remote
commands run as `pve-ops` and use `sudo` for the wrapper entrypoint, with a
sudoers template allowing only `/usr/local/sbin/astra-pve-template-build`.

`build-template.sh` sources the generated `template-build.env` beside the script
before applying any environment overrides.

Wrapper runtime dependencies on the PVE node: `/usr/bin/curl`,
`/usr/bin/shasum`, `/usr/bin/cp`, `/usr/bin/virt-customize`,
`/usr/bin/virt-sysprep`, `/usr/sbin/qm`, and `/usr/bin/flock`.
Install `libguestfs-tools` on the PVE node to provide `virt-customize` and
`virt-sysprep` before running the template build.

For OVMF/q35 builds, the template is created with an explicit 4m EFI disk on
`DISK_STORAGE`.

The configured build bridge must exist and remain attachable for template builds.

`qm importdisk` attachment uses the imported volume reported in VM config and
fails rather than guessing if that volume cannot be detected.

## Installation

- `sudo install -m 750 -o root -g root infra/pve-node/bin/astra-pve-template-build /usr/local/sbin/astra-pve-template-build`
- copy `infra/pve-node/sudoers.d/astra-pve-template-build` to a temp path, validate it with `sudo visudo -cf`, then install it as `/etc/sudoers.d/astra-pve-template-build` with mode `440` and owner `root:root`
- keep the wrapper executable and owned by root

After wrapper installation, remove the temporary preflight multi-binary `pve-ops` sudo allowlist and leave only the wrapper NOPASSWD rule.

## Variables

`packer.pkr.hcl` records the intended inputs for future Packer integration; the
Packer CLI is not required for this helper yet.

- `pve_endpoint`, `pve_node`
- `import_storage`, `disk_storage`
- `template_vmid`, `template_name`
- `pve_username`, `pve_token_id`, `pve_token_secret`
- `cache_dir`, `force_replace`
- `image_url`, `image_sha512`, `image_url_prefix`
- `apt_mirror`, `apt_security_mirror`, `timezone`, `locale`, `ciuser`, `nameserver`, `build_bridge`

Generated non-secret defaults live in `template-build.env`; `PVE_HOST` remains a
required explicit local setting.

## Ownership boundary

Packer owns template creation. OpenTofu may consume the template later, but this foundation does not manage template lifecycle.
