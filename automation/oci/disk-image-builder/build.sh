#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
image=${1:-iaas-image-builder:oci-release-test}
platform=${IMAGE_BUILDER_PLATFORM:-linux/amd64}
if [ "$platform" != linux/amd64 ]; then
    echo "unsupported disk image builder platform: $platform" >&2
    exit 2
fi
exec docker buildx build --load --platform "$platform" \
    -f "$root/automation/oci/disk-image-builder/Dockerfile" -t "$image" \
    --build-arg "OCI_SOURCE=${OCI_SOURCE:-https://github.com/c1emon/iaas}" \
    --build-arg "OCI_REVISION=${OCI_REVISION:-development}" \
    --build-arg "OCI_VERSION=${OCI_VERSION:-development}" "$root"
