# Snippet upload bootstrap identity

`automation/ansible/playbooks/pve/bootstrap-pve-ssh-user.yml` requires callers to supply
`pve_bootstrap_user` and `pve_bootstrap_authorized_key` through inventory, vars
files, or extra vars. Neither input has a playbook default. The username must be a
non-root Linux username matching `[a-z_][a-z0-9_-]{0,31}`; provide the authorized
SSH public key, never a private key.

The playbook creates that account and renders `iaas-pve-snippet-upload.j2` for the
same account, validating the rendered rule with `visudo` before installation.
The `.j2` source is not an installable sudoers file. The playbook does not select an account name.

Changing the requested identity does not remove a previous account, its SSH
keys, or independently installed permissions. The caller must assess any such
migration separately.

The SSH directory follows the home returned by Ansible's user module, including
an existing account with a nonstandard home. Restoring the default sudo command list removes a previous
`/etc/sudoers.d/iaas-pve-bootstrap-override` only when its first line carries the
managed marker from this playbook or its former `bootstrap-pve-ops.yml` name.
Selecting broader commands replaces that managed override for the selected user.
An unrecognized file or symlink blocks the playbook before account changes and
requires explicit caller resolution; other site sudoers files are untouched.
