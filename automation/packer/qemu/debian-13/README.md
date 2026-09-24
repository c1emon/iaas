# Debian 13 amd64 QEMU image profile

This profile is the image executor's only supported build recipe in v1. It
uses the pinned HashiCorp QEMU plugin with `accelerator = "kvm"`, a transient
NoCloud seed, and an Ansible provisioner over Packer's temporary SSH channel.
The seed and SSH key are task-owned and are removed after build cleanup. The
profile does not accept PVE endpoints, tokens, arbitrary shell, or bridge
configuration.

`virt-sysprep` and `virt-customize` are run by the image runtime after Packer
has shut the guest down. They remove machine identity, host keys, cloud-init
state, logs, caches, temporary network identity, and the builder account.
