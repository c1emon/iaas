#!/usr/bin/env bash
set -euo pipefail

# Thin local trigger only: validate inputs, then hand off to the remote wrapper.

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
template_build_env=${TEMPLATE_BUILD_ENV:-${script_dir}/template-build.env}
if [[ -r ${template_build_env} ]]; then
  # shellcheck disable=SC1090
  . "${template_build_env}"
fi

# Local settings are sourced from the generated env; only ssh transport is required here.
readonly PVE_HOST="${PVE_HOST:?set PVE_HOST to the selected PVE build node SSH host}"
readonly PVE_USER="${PVE_USER:-pve-ops}"
readonly TEMPLATE_VMID="${TEMPLATE_VMID:?set TEMPLATE_VMID or source template-build.env}"
readonly TEMPLATE_NAME="${TEMPLATE_NAME:?set TEMPLATE_NAME or source template-build.env}"
readonly IMAGE_URL="${IMAGE_URL:?set IMAGE_URL or source template-build.env}"
readonly IMAGE_SHA512="${IMAGE_SHA512:?set IMAGE_SHA512 or source template-build.env}"
readonly IMAGE_URL_PREFIX="${IMAGE_URL_PREFIX:?set IMAGE_URL_PREFIX or source template-build.env}"
readonly IMPORT_STORAGE="${IMPORT_STORAGE:?set IMPORT_STORAGE or source template-build.env}"
readonly DISK_STORAGE="${DISK_STORAGE:?set DISK_STORAGE or source template-build.env}"
readonly BUILD_DOMAIN="${BUILD_DOMAIN:?set BUILD_DOMAIN or source template-build.env}"
readonly APT_MIRROR="${APT_MIRROR:?set APT_MIRROR or source template-build.env}"
readonly APT_SECURITY_MIRROR="${APT_SECURITY_MIRROR:?set APT_SECURITY_MIRROR or source template-build.env}"
readonly TIMEZONE="${TIMEZONE:?set TIMEZONE or source template-build.env}"
readonly LOCALE="${LOCALE:?set LOCALE or source template-build.env}"
readonly CIUSER="${CIUSER:?set CIUSER or source template-build.env}"
readonly NAMESERVER="${NAMESERVER:?set NAMESERVER or source template-build.env}"
readonly BUILD_BRIDGE="${BUILD_BRIDGE:?set BUILD_BRIDGE or source template-build.env}"
readonly FORCE_REPLACE="${FORCE_REPLACE:-false}"
readonly TEMPLATE_DEBUG="${TEMPLATE_DEBUG:-${DEBUG:-false}}"

if ! command -v ssh >/dev/null 2>&1; then
  printf 'missing required local command: ssh\n' >&2
  exit 1
fi

shell_quote() {
  local value=${1//\'/\'\\\'\'}
  printf "'%s'" "${value}"
}

join_shell_quoted_args() {
  local quoted_command=
  local arg
  for arg in "$@"; do
    if [[ -n ${quoted_command} ]]; then
      quoted_command+=' '
    fi
    quoted_command+=$(shell_quote "${arg}")
  done
  printf '%s' "${quoted_command}"
}

# Keep the local trigger aligned with the wrapper's safety envelope.
[[ ${TEMPLATE_VMID} =~ ^(9[0-4][0-9][0-9]|9500)$ ]] || {
  printf 'template VMID must be in 9000-9500\n' >&2
  exit 1
}

[[ ${TEMPLATE_NAME} =~ ^[A-Za-z0-9][A-Za-z0-9._-]+$ ]] || {
  printf 'template name must match the conservative template regex\n' >&2
  exit 1
}

remote_args=(
  sudo
  -n
  /usr/local/sbin/astra-pve-template-build
  --vmid "${TEMPLATE_VMID}"
  --name "${TEMPLATE_NAME}"
  --image-url-prefix "${IMAGE_URL_PREFIX}"
  --image-url "${IMAGE_URL}"
  --sha512 "${IMAGE_SHA512}"
  --import-storage "${IMPORT_STORAGE}"
  --disk-storage "${DISK_STORAGE}"
  --build-domain "${BUILD_DOMAIN}"
  --apt-mirror "${APT_MIRROR}"
  --apt-security-mirror "${APT_SECURITY_MIRROR}"
  --timezone "${TIMEZONE}"
  --locale "${LOCALE}"
  --ciuser "${CIUSER}"
  --nameserver "${NAMESERVER}"
  --build-bridge "${BUILD_BRIDGE}"
)

# Run the root-owned wrapper on the selected node through the allowlisted sudoers entry.
if [[ "${FORCE_REPLACE}" == true ]]; then
  remote_args+=(--force)
fi

# Debug mode is wrapper-only; keep the local trigger thin.
if [[ "${TEMPLATE_DEBUG}" == true ]]; then
  remote_args+=(--debug)
fi

ssh "${PVE_USER}@${PVE_HOST}" "$(join_shell_quoted_args "${remote_args[@]}")"
