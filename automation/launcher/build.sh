#!/bin/sh
set -eu

launcher_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output=${1:?usage: build.sh NEW_OUTPUT_DIRECTORY [VERSION]}
version=${2:-development}
mkdir "$output"
output=$(CDPATH= cd -- "$output" && pwd)
cd "$launcher_dir"
go test ./...
for target in linux/amd64 darwin/arm64; do
    target_os=${target%/*}
    target_arch=${target#*/}
    CGO_ENABLED=0 GOOS="$target_os" GOARCH="$target_arch" \
        go build -mod=readonly -trimpath -ldflags "-X main.version=$version" \
        -o "$output/iaas-$target_os-$target_arch" .
done
cd "$output"
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum iaas-* > SHA256SUMS
else
    shasum -a 256 iaas-* > SHA256SUMS
fi
