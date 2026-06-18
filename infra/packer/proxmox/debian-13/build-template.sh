#!/usr/bin/env bash
set -euo pipefail

# Thin local trigger only: validate inputs, then hand off to the remote wrapper.

readonly DEFAULT_IMAGE_URL='https://cloud.debian.org/images/cloud/trixie/20260601-2496/debian-13-genericcloud-amd64-20260601-2496.qcow2'
readonly DEFAULT_IMAGE_SHA512='61264ae6968d765e61cf5607a664ba63099ddfb66b8404aa737d06f89b39c8e0fbaa1517b13705909ff01686d32015a0147436662672b4dacc10b4a171d7993d'

# Local defaults mirror the wrapper contract; only ssh is required here.
readonly PVE_HOST="${PVE_HOST:?set PVE_HOST to the selected PVE build node SSH host}"
readonly PVE_USER="${PVE_USER:-pve-ops}"
readonly TEMPLATE_VMID="${TEMPLATE_VMID:-9001}"
readonly TEMPLATE_NAME="${TEMPLATE_NAME:-debian-13-tmpl-$(date +%Y%m%d)}"
readonly IMPORT_STORAGE="${IMPORT_STORAGE:-images}"
readonly DISK_STORAGE="${DISK_STORAGE:-memory}"
readonly BUILD_DOMAIN="${BUILD_DOMAIN:-localdomain}"
readonly IMAGE_URL="${IMAGE_URL:-${DEFAULT_IMAGE_URL}}"
readonly IMAGE_SHA512="${IMAGE_SHA512:-${DEFAULT_IMAGE_SHA512}}"
readonly FORCE_REPLACE="${FORCE_REPLACE:-false}"
readonly TEMPLATE_DEBUG="${TEMPLATE_DEBUG:-${DEBUG:-false}}"

if ! command -v ssh >/dev/null 2>&1; then
  printf 'missing required local command: ssh\n' >&2
  exit 1
fi

# Keep the local trigger aligned with the wrapper's safety envelope.
[[ ${TEMPLATE_VMID} =~ ^(9[0-4][0-9][0-9]|9500)$ ]] || {
  printf 'template VMID must be in 9000-9500\n' >&2
  exit 1
}

[[ ${TEMPLATE_NAME} =~ ^debian-13-tmpl-[0-9]{8}$ ]] || {
  printf 'template name must match debian-13-tmpl-YYYYMMDD\n' >&2
  exit 1
}

remote_args=(
  sudo
  -n
  /usr/local/sbin/astra-pve-template-build
  --vmid "${TEMPLATE_VMID}"
  --name "${TEMPLATE_NAME}"
  --image-url "${IMAGE_URL}"
  --sha512 "${IMAGE_SHA512}"
  --import-storage "${IMPORT_STORAGE}"
  --disk-storage "${DISK_STORAGE}"
  --build-domain "${BUILD_DOMAIN}"
)

# Run the root-owned wrapper on the selected node through the allowlisted sudoers entry.
if [[ "${FORCE_REPLACE}" == true ]]; then
  remote_args+=(--force)
fi

# Debug mode is wrapper-only; keep the local trigger thin.
if [[ "${TEMPLATE_DEBUG}" == true ]]; then
  remote_args+=(--debug)
fi

ssh "${PVE_USER}@${PVE_HOST}" "${remote_args[@]}"
