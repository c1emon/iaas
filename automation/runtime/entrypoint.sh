#!/bin/sh
set -eu

if [ "$#" -eq 0 ] || [ "$1" = help ] || [ "$1" = --help ]; then
    exec make --no-print-directory -f /opt/iaas/Makefile help
fi

operation=$1
shift
case "$operation" in
    generate|check-generated|pve-*|services-generate|services-check|foundation-generate|foundation-check|foundation-health|opnsense-validate|render-cloud-init|upload-cloud-init|verify-cloud-init|k3s-*|platform-handoff-*) ;;
    *) printf 'error: unsupported runtime operation: %s\n' "$operation" >&2; exit 2 ;;
esac
for argument do
    case "$argument" in
        [A-Z]*=*) ;;
        *) printf 'error: operation arguments must be Make VARIABLE=value inputs\n' >&2; exit 2 ;;
    esac
done

# Check caller paths before creating a writable home or cache.
case "$operation" in
    k3s-*|platform-handoff-*) guard=require-output ;;
    *) guard=require-environment ;;
esac
make --no-print-directory -f /opt/iaas/Makefile "$guard" "$@"
: "${HOME:=/tmp/iaas-home-$(id -u)}"
export HOME
umask 077
mkdir -p "$HOME"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
export ANSIBLE_LOCAL_TEMP="${ANSIBLE_LOCAL_TEMP:-$HOME/.ansible/tmp}"
exec make --no-print-directory -f /opt/iaas/Makefile "$operation" "$@"
