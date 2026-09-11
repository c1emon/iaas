#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
image=${1:-iaas-runtime:oci-release-test}
platform=${RUNTIME_PLATFORM:-linux/amd64}
case "$platform" in
    linux/amd64|linux/arm64) ;;
    *) echo "unsupported runtime platform: $platform" >&2; exit 2 ;;
esac
set -- --platform "$platform" -f "$root/automation/runtime/Dockerfile" -t "$image" \
    --build-arg "OCI_SOURCE=${OCI_SOURCE:-https://github.com/c1emon/iaas}" \
    --build-arg "OCI_REVISION=${OCI_REVISION:-development}" \
    --build-arg "OCI_VERSION=${OCI_VERSION:-development}"
if [ -n "${RUNTIME_BUILD_CACHE_DIR:-}" ]; then
    if [ -f "$RUNTIME_BUILD_CACHE_DIR/index.json" ]; then
        set -- "$@" --cache-from "type=local,src=$RUNTIME_BUILD_CACHE_DIR"
    fi
    exec docker buildx build --load "$@" --cache-to "type=local,dest=$RUNTIME_BUILD_CACHE_DIR,mode=max" "$root"
fi
exec docker buildx build --load "$@" "$root"
