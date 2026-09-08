#!/usr/bin/env bash
set -euo pipefail

# Thin local trigger only: validate inputs, then hand off to the remote wrapper.

template_build_env=${TEMPLATE_BUILD_ENV:?set TEMPLATE_BUILD_ENV to the generated template build environment file}
if [[ ! -r ${template_build_env} ]]; then
  printf 'TEMPLATE_BUILD_ENV is not readable: %s\n' "${template_build_env}" >&2
  exit 1
fi
# shellcheck disable=SC1090
. "${template_build_env}"

# Local settings are sourced from the generated env; only ssh transport is required here.
readonly PVE_HOST="${PVE_HOST:?set PVE_HOST to the selected PVE build node SSH host}"
readonly PVE_USER="${PVE_USER:-pve-ops}"
readonly TEMPLATE_VMID="${TEMPLATE_VMID:?set TEMPLATE_VMID in the file named by TEMPLATE_BUILD_ENV}"
readonly TEMPLATE_NAME="${TEMPLATE_NAME:?set TEMPLATE_NAME in the file named by TEMPLATE_BUILD_ENV}"
readonly IMAGE_URL="${IMAGE_URL:?set IMAGE_URL in the file named by TEMPLATE_BUILD_ENV}"
readonly IMAGE_SHA512="${IMAGE_SHA512:?set IMAGE_SHA512 in the file named by TEMPLATE_BUILD_ENV}"
readonly IMAGE_URL_PREFIX="${IMAGE_URL_PREFIX:?set IMAGE_URL_PREFIX in the file named by TEMPLATE_BUILD_ENV}"
readonly IMPORT_STORAGE="${IMPORT_STORAGE:?set IMPORT_STORAGE in the file named by TEMPLATE_BUILD_ENV}"
readonly DISK_STORAGE="${DISK_STORAGE:?set DISK_STORAGE in the file named by TEMPLATE_BUILD_ENV}"
readonly BUILD_DOMAIN="${BUILD_DOMAIN:?set BUILD_DOMAIN in the file named by TEMPLATE_BUILD_ENV}"
readonly APT_MIRROR="${APT_MIRROR:?set APT_MIRROR in the file named by TEMPLATE_BUILD_ENV}"
readonly APT_SECURITY_MIRROR="${APT_SECURITY_MIRROR:?set APT_SECURITY_MIRROR in the file named by TEMPLATE_BUILD_ENV}"
readonly TIMEZONE="${TIMEZONE:?set TIMEZONE in the file named by TEMPLATE_BUILD_ENV}"
readonly LOCALE="${LOCALE:?set LOCALE in the file named by TEMPLATE_BUILD_ENV}"
readonly CIUSER="${CIUSER:?set CIUSER in the file named by TEMPLATE_BUILD_ENV}"
readonly NAMESERVER="${NAMESERVER:?set NAMESERVER in the file named by TEMPLATE_BUILD_ENV}"
readonly BUILD_BRIDGE="${BUILD_BRIDGE:?set BUILD_BRIDGE in the file named by TEMPLATE_BUILD_ENV}"
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
  /usr/local/sbin/iaas-pve-template-build
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
