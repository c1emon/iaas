# PVE Automation Preflight Research

Date: 2026-06-16
OpenSpec change: `add-pve-automation-foundation`

## Decisions

### Debian 13 template route

Use the Debian 13 `genericcloud` qcow2 image import route for the first reusable PVE template, not an installer ISO route.

Recommended first implementation shape:

1. Download and checksum-pin the current Debian 13 genericcloud amd64 qcow2 from Debian cloud images at implementation time.
2. Customize the image offline with `libguestfs-tools`/`virt-customize` for template-level packages and settings such as `qemu-guest-agent`, serial-console readiness, TUNA apt mirrors, timezone, locale, and cleanup.
3. Import the disk into PVE storage with `qm importdisk`/equivalent PVE workflow.
4. Attach it as the template root disk, add a cloud-init drive, set OVMF/q35-compatible defaults, set boot order, enable guest agent, and convert the VM to a template.

Rationale: Debian cloud images are already cloud-init native, avoid slow installer automation, and reduce boot-command fragility. The ISO installer route remains a fallback only if custom partitioning or installer-only behavior becomes required. `proxmox-clone` can be used later for layered images once a base template exists.

References:

- Debian cloud images: <https://cloud.debian.org/images/cloud/trixie/latest/>
- Packer Proxmox plugin: <https://github.com/hashicorp/packer-plugin-proxmox>

### Packer and provider version constraints

Use explicit version constraints rather than floating latest versions:

- Packer Proxmox plugin: `hashicorp/proxmox` constrained to `~> 1.2`.
- Packer CLI: require at least `1.7` for plugin initialization workflow.
- OpenTofu: require at least `1.6` for first-version provider compatibility.
- `bpg/proxmox` provider: constrain to `~> 0.109` for the first implementation and revisit before upgrades because the provider is pre-1.0.

The implementation should still run `packer init`, `packer validate`, `tofu init`, `tofu validate`, and a disposable `tofu plan` during acceptance to catch registry/provider drift.

References:

- Packer Proxmox plugin releases: <https://github.com/hashicorp/packer-plugin-proxmox/releases>
- `bpg/proxmox` provider repository: <https://github.com/bpg/terraform-provider-proxmox>
- `bpg/proxmox` provider docs: <https://registry.terraform.io/providers/bpg/proxmox/latest/docs>

### API tokens, SSH, and limited sudo

Use PVE API tokens for Packer/OpenTofu API operations and reserve the Linux `pve-ops` SSH user for host-side operations that cannot be performed through the API.

Create a passwordless PVE realm automation user and separate privilege-separated tokens:

```bash
pveum user add pve-ops@pve --comment "Automation API user for Packer and OpenTofu"
pveum user token add pve-ops@pve opentofu --comment "OpenTofu automation token" --privsep 1
pveum user token add pve-ops@pve packer --comment "Packer automation token" --privsep 1
```

Do not set a password for `pve-ops@pve` unless an interactive fallback is deliberately needed. Store the one-time token secrets immediately in 1Password.

Initial role definitions should be explicit and treated as bootstrap defaults to reduce after online validation. PVE reserves role IDs starting with the case-insensitive `PVE` namespace, so use project-specific role IDs that do not start with `PVE`:

```bash
pveum role add AstraAutomation --privs "Datastore.AllocateSpace,Datastore.Audit,Mapping.Use,SDN.Use,Sys.Audit,VM.Allocate,VM.Audit,VM.Clone,VM.Config.CDROM,VM.Config.CPU,VM.Config.Cloudinit,VM.Config.Disk,VM.Config.HWType,VM.Config.Memory,VM.Config.Network,VM.Config.Options,VM.Console,VM.GuestAgent.Audit,VM.PowerMgmt"

pveum role add AstraTemplateBuilder --privs "Datastore.AllocateSpace,Datastore.AllocateTemplate,Datastore.Audit,Sys.Audit,Sys.Modify,VM.Allocate,VM.Audit,VM.Clone,VM.Config.CDROM,VM.Config.CPU,VM.Config.Cloudinit,VM.Config.Disk,VM.Config.HWType,VM.Config.Memory,VM.Config.Network,VM.Config.Options,VM.Console,VM.GuestAgent.Audit,VM.PowerMgmt"
```

Assign the roles to the parent user and the tokens. PVE 9 live validation showed the privilege-separated token still failed clone checks until the parent user also had the role at `/`:

```bash
pveum aclmod / --users 'pve-ops@pve' --roles AstraAutomation
pveum aclmod / --users 'pve-ops@pve' --roles AstraTemplateBuilder
pveum aclmod / --tokens 'pve-ops@pve!opentofu' --roles AstraAutomation
pveum aclmod / --tokens 'pve-ops@pve!packer' --roles AstraTemplateBuilder
pveum acl list
```

Notes:

- `AstraAutomation` is for OpenTofu-managed VM lifecycle: clone/create/update new VMs, configure disks/network/cloud-init/options, power operations, and use existing PCI resource mappings.
- `SDN.Use` is required when the target bridge is represented under PVE SDN, such as `/sdn/zones/localnetwork/br_dev`.
- `AstraTemplateBuilder` is for Packer/template construction and starts with template/datastore permissions needed for image/template workflows.
- PVE 9 removed the old `VM.Monitor` privilege. Use `Sys.Audit` for basic QEMU monitor access and `VM.GuestAgent.Audit` for guest-agent information. Escalate to `VM.GuestAgent.Unrestricted` only if a later online provider/Packer validation proves guest-agent command execution is required.
- Creating or modifying PVE PCI hardware mappings is not included in these roles; mapping bootstrap may require an administrator/root workflow.
- If provider behavior shows missing privileges, add the smallest additional permission and document why. If validation shows unused privileges, remove them.

For the first cloud-image import/template build, the expected `pve-ops` host sudo allowlist was a preflight/bootstrap allowance limited to PVE image/template commands and supporting image tooling, not `NOPASSWD: ALL`:

```text
/usr/sbin/qm
/usr/sbin/pvesm
/usr/bin/qemu-img
/usr/bin/virt-customize
/usr/bin/virt-sysprep
/usr/bin/install
/usr/bin/mkdir
/usr/bin/rm
/usr/bin/chown
/usr/bin/chmod
```

Implementation guidance:

- Prefer wrapping these in one audited script path if practical, then allowlist that script instead of many binaries.
- In the final Section 3 wrapper state, reduce `pve-ops` to wrapper-only sudo for template builds.
- Keep Packer guest provisioning sudo separate from PVE host sudo. Guest sudo applies inside temporary/template VMs; `pve-ops` host sudo applies on PVE nodes.
- Validate the final command list during the online template spike and remove entries that are not used.

Bootstrap validation on `cohe` confirmed that `pve-ops` can log in with the 1Password-managed SSH key and run `sudo -l`, `sudo pvesm status`, and `sudo qm list` without a password. `pvesm status` sees active `images`, `local`, and `memory` storage; this validates the initial SSH/sudo path for the default Packer build node.

Section 3 live validation on `pve-ops@10.1.0.72` rebuilt `debian-13-tmpl-20260616` as VMID `9001` from the pinned Debian 13 genericcloud image with explicit force replacement. The successful template config includes `template: 1`, `bios: ovmf`, `machine: q35`, EFI and root disks on `memory`, cloud-init media on `images`, `serial0: socket`, `vga: serial0`, `net0` on `br_dev`, and `agent: enabled=1`. A temporary full clone VMID `799` booted from the template, reported qemu-guest-agent networking with static IP `10.10.0.199/24`, and was destroyed with `--purge`. The live run also confirmed that Debian 13 apt sources must be rewritten as deb822 before package installation and that this PVE `virt-sysprep` version does not support a `cloud-init` operation, so cloud-init cleanup is handled with `cloud-init clean --logs` during customization.

Section 4/4A live validation on `cohe` created disposable VMID `500` (`dev-web-01`) from template VMID `9001`, attached it to `br_dev`, applied static IP `10.10.0.20/24`, started it, confirmed qemu-guest-agent IP reporting, confirmed SSH for both `clemon` and `ops`, and then destroyed it through targeted OpenTofu cleanup. The run exposed these operational requirements:

- OpenTofu should use `tofu`, not Terraform, for live commands.
- `pve-ops@pve` needs `AstraAutomation` on both the parent user and `pve-ops@pve!opentofu` token in this PVE 9 setup.
- `AstraAutomation` needs `SDN.Use` for `br_dev` when PVE checks `/sdn/zones/localnetwork/br_dev`.
- The cloud-init snippet upload wrapper must not force `root:root` ownership on NFS/root-squashed storage; path constraints and mode are the control boundary.
- Snippets remain in shared `images` storage for VM lifetime because OpenTofu references `user_data_file_id`.
- The 1Password SSH Agent config must include `vm-user-ops` and `vm-user-clemon` entries before broad vault catch-alls if key selection order prevents guest login.

References:

- PVE `qm` manual: <https://pve.proxmox.com/pve-docs/qm.1.html>
- PVE storage manual: <https://pve.proxmox.com/pve-docs/chapter-pvesm.html>

### PCI passthrough via PVE resource mappings

Use `hostpci` mapping references, not raw PCI IDs, for VM passthrough declarations.

For `bpg/proxmox`, render VM host PCI attachments with the PVE resource mapping name, for example `mapping = "iGpu0"`. Avoid raw `id = "0000:..."` in generated VM declarations because raw PCI IDs are less portable and are not appropriate for token-based automation in this design.

The existing resource mapping is a prerequisite. Creating or changing PVE PCI resource mappings is not part of this foundation and may require elevated/root bootstrap privileges. The generator should only validate that declared VM node placement is compatible with the mapping data recorded in YAML.

References:

- VM resource docs: <https://registry.terraform.io/providers/bpg/proxmox/latest/docs/resources/virtual_environment_vm>
- PCI mapping resource docs: <https://registry.terraform.io/providers/bpg/proxmox/latest/docs/resources/hardware_mapping_pci>

### OVMF and EFI disk support

Use `bios = "ovmf"` with an explicit `efi_disk` block on the selected VM/template disk datastore.

First-version provider configuration should use the intended VM disk datastore (`memory`) for the EFI disk when supported by the PVE storage content/type settings. Prefer `type = "4m"`; use `file_format = "raw"` unless the selected storage backend requires a different format.

Acceptance must include an online validation that PVE can create a disposable OVMF/q35 VM with an EFI disk on `memory`. If that fails, either move EFI disks to a compatible datastore or adjust storage content settings before VM acceptance.

Reference:

- VM EFI disk docs: <https://registry.terraform.io/providers/bpg/proxmox/latest/docs/resources/virtual_environment_vm>

### Generated tfvars ignore strategy

Keep `infra/tofu/pve/generated.auto.tfvars.json` as a committed, non-sensitive generated review artifact. Add a precise `.gitignore` exception for that one file while continuing to ignore other `*.tfvars.json` and `*.auto.tfvars.json` files.

This preserves the spec requirement that generated OpenTofu input is reviewable and committed, while keeping normal local/secret tfvars files ignored.

### 1Password field lookup rules

Automation must not assume custom 1Password field IDs are stable. Custom fields created in the 1Password UI receive generated IDs, even when their displayed labels are stable.

Use a two-step lookup rule for logical field names:

1. First try stable `field.id` exact match.
2. If no match is found, normalize `field.label` to snake_case and match that normalized label.

Label normalization should trim whitespace, lowercase the label, replace runs of non-alphanumeric characters with `_`, collapse duplicate underscores, and trim leading/trailing underscores. For example:

```text
"public key"  -> "public_key"
"Public Key"  -> "public_key"
"token-secret" -> "token_secret"
"私钥"         -> not used for logical lookup; use field.id == "private_key"
```

When duplicate normalized labels exist, prefer the field in the requested section. If the lookup is not section-scoped and duplicates remain, fail with an ambiguity error instead of guessing.

For SSH Key items such as `pve-ssh-automation-user` and `vm-user-ops`, built-in SSH fields may be read by fixed field ID:

```text
public_key  -> field.id == "public_key"
private_key -> field.id == "private_key"
fingerprint -> field.id == "fingerprint"
key_type    -> field.id == "key_type"
```

For PAM/login credentials added as custom fields inside an item section, read by section label plus logical field lookup. Section matching should also prefer `section.id` when a known stable ID exists, otherwise normalize `section.label` to snake_case and match `pam`:

```text
pam username -> normalized field.section.label == "pam" and logical field name == "username"
pam password -> normalized field.section.label == "pam" and logical field name == "password"
```

Avoid duplicate `username` or `password` fields outside the `pam` section in these SSH Key items, because label-only lookup would become ambiguous.

## Remaining validation during implementation

- Pin the exact Debian 13 genericcloud URL and checksum at implementation time.
- Confirm the observed Packer/PVE command list and reduce the `pve-ops` sudo allowlist accordingly.
- Run an online OVMF EFI disk create/plan/apply test on the chosen storage.
- Run a separate passthrough test after the first non-passthrough disposable VM succeeds.
- Re-check `bpg/proxmox` release notes before upgrading beyond `~> 0.109`.

## Future direction: CI runner image build split

Do not introduce a CI runner in the initial PVE automation foundation. If template builds become frequent or need stronger auditability, prefer a dedicated management runner VM/container rather than installing a runner directly on a PVE hypervisor host.

The preferred future split is:

1. A dedicated runner downloads the pinned Debian cloud image, verifies the checksum, runs image customization and sysprep, and produces a finalized qcow2 artifact.
2. The PVE node remains responsible only for host-local registration steps through the audited wrapper: receive or download the artifact, run `qm create`, `qm importdisk`, `qm set`, and `qm template`.

This keeps CI execution off the hypervisor while still minimizing PVE host operations. The runner should not receive direct `qm` access; it should upload or expose the qcow2 artifact and invoke the wrapper through the existing `pve-ops` SSH/sudo boundary. Section 4A snippet uploads likewise use the audited `/usr/local/sbin/astra-pve-snippet-upload` wrapper instead of broad `sudo install` access.

## Operator runbook: PVE identity bootstrap

Before OpenTofu runs, operators bootstrap the PVE realm identity and store the resulting token material in 1Password.

1. Create the realm user without a password:

   ```bash
   pveum user add pve-ops@pve --comment "Automation API user for Packer and OpenTofu"
   ```

2. Create the privilege-separated API tokens:

   ```bash
   pveum user token add pve-ops@pve opentofu --comment "OpenTofu automation token" --privsep 1
   pveum user token add pve-ops@pve packer --comment "Packer automation token" --privsep 1
   ```

3. Assign the initial roles to the tokens, not just to the parent user:

   ```bash
   pveum role add AstraAutomation --privs "Datastore.AllocateSpace,Datastore.Audit,Mapping.Use,SDN.Use,Sys.Audit,VM.Allocate,VM.Audit,VM.Clone,VM.Config.CDROM,VM.Config.CPU,VM.Config.Cloudinit,VM.Config.Disk,VM.Config.HWType,VM.Config.Memory,VM.Config.Network,VM.Config.Options,VM.Console,VM.GuestAgent.Audit,VM.PowerMgmt"
   pveum role add AstraTemplateBuilder --privs "Datastore.AllocateSpace,Datastore.AllocateTemplate,Datastore.Audit,Sys.Audit,Sys.Modify,VM.Allocate,VM.Audit,VM.Clone,VM.Config.CDROM,VM.Config.CPU,VM.Config.Cloudinit,VM.Config.Disk,VM.Config.HWType,VM.Config.Memory,VM.Config.Network,VM.Config.Options,VM.Console,VM.GuestAgent.Audit,VM.PowerMgmt"
   pveum aclmod / --users 'pve-ops@pve' --roles AstraAutomation
   pveum aclmod / --users 'pve-ops@pve' --roles AstraTemplateBuilder
   pveum aclmod / --tokens 'pve-ops@pve!opentofu' --roles AstraAutomation
   pveum aclmod / --tokens 'pve-ops@pve!packer' --roles AstraTemplateBuilder
   ```

4. Store the API token fields in the `Astra` vault items `pve-opentofu-api-token` and `pve-packer-api-token` using these field names: `username`, `token_id`, `token_secret`, `api_token`, and `endpoint`.

5. Keep the bootstrap root of trust outside OpenTofu: the OpenTofu configuration that consumes `pve-ops@pve!opentofu` must not manage `pve-ops@pve`, its tokens, or the initial ACLs in this foundation.

Future automation for this bootstrap may be added separately under an existing administrator identity, but it must not be the OpenTofu stack that depends on the token being created.

## Operator runbook: SSH bootstrap extra-vars

When passing a public SSH key to `ansible/playbooks/pve/bootstrap-pve-ops.yml`, use JSON extra-vars so spaces in the OpenSSH public key are preserved. Avoid key-value `-e pve_bootstrap_authorized_key="$KEY"`, which can truncate the key at spaces depending on shell/Ansible parsing.

```bash
export KEY="$(op read op://Astra/pve-ssh-automation-user/public_key)"
EXTRA_VARS_JSON="$(python3 -c 'import json, os; print(json.dumps({"pve_bootstrap_authorized_key": os.environ["KEY"]}))')"
uv run ansible-playbook ansible/playbooks/pve/bootstrap-pve-ops.yml \
  --extra-vars "$EXTRA_VARS_JSON"
```
