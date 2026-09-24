#!/bin/sh
# Check recipe-specific requirements against a built OCI executor.
set -eu
image=${1:-iaas-image-builder:oci-release-test}
operations=$(docker run --rm --network none --platform linux/amd64 \
    --entrypoint virt-sysprep "$image" --list-operations)
for operation in machine-id ssh-hostkeys logfiles tmp-files package-manager-cache net-hwaddr; do
    printf '%s\n' "$operations" | awk -v expected="$operation" \
        '$1 == expected { found = 1 } END { exit found ? 0 : 1 }' || {
        echo "virt-sysprep operation is unavailable: $operation" >&2
        exit 1
    }
done
docker run --rm --network none --platform linux/amd64 --read-only --tmpfs /tmp:rw,mode=1777 \
    --entrypoint packer "$image" validate -syntax-only \
    /opt/iaas/automation/packer/qemu/debian-13
docker run --rm --network none --platform linux/amd64 --read-only --tmpfs /tmp:rw,mode=1777 \
    -e HOME=/tmp -e ANSIBLE_LOCAL_TEMP=/tmp/ansible \
    --entrypoint ansible-playbook "$image" --syntax-check -i localhost, \
    /opt/iaas/automation/packer/qemu/debian-13/ansible/customize.yml \
    -e apt_mirror=https://deb.debian.org/debian \
    -e apt_security_mirror=https://security.debian.org/debian-security \
    -e packages_json='[]' \
    -e image_timezone=UTC \
    -e image_locale=C.UTF-8 \
    -e image_cloud_init=installed \
    -e image_guest_agent=installed
