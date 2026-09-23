# Dedicated Linux amd64 executor image. It is intentionally separate from the
# ordinary runtime so KVM and libguestfs permissions never reach PVE/OPNsense.
FROM --platform=linux/amd64 python:3.12.12-slim-bookworm@sha256:2986c55feb36e6cae00fa1fefb454283e4b33f35e75ff8bdd123b134130be301

ARG PACKER_VERSION=1.16.0
ARG PACKER_SHA256=5edcd14ab59b535040c512dbecd6ec9ef976a000b073c19d93e4c431c948581e

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/opt/iaas/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
    PYTHONPATH="/opt/iaas/automation/src" \
    UV_NO_SYNC=1 UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 \
    ANSIBLE_CONFIG="/opt/iaas/automation/ansible/ansible.cfg" \
    ANSIBLE_COLLECTIONS_PATH="/opt/iaas/automation/ansible/collections" \
    PACKER_PLUGIN_PATH="/opt/packer/plugins"

ARG DEBIAN_MIRROR=https://deb.debian.org/debian
ARG DEBIAN_SECURITY_MIRROR=https://security.debian.org/debian-security

RUN DEBIAN_MIRROR="$DEBIAN_MIRROR" DEBIAN_SECURITY_MIRROR="$DEBIAN_SECURITY_MIRROR" \
    python3 - <<'PY'
from pathlib import Path
import os

sources = Path("/etc/apt/sources.list.d/debian.sources")
if not sources.is_file():
    raise SystemExit("the base image does not provide deb822 Debian sources")

mirrors = {
    "/debian": os.environ["DEBIAN_MIRROR"].rstrip("/"),
    "/debian-security": os.environ["DEBIAN_SECURITY_MIRROR"].rstrip("/"),
}
lines = sources.read_text(encoding="utf-8").splitlines()
seen = set()
for index, line in enumerate(lines):
    if not line.startswith("URIs: "):
        continue
    uri = line.removeprefix("URIs: ").strip().rstrip("/")
    suffix = next((value for value in mirrors if uri.endswith(value)), None)
    if suffix is not None:
        lines[index] = f"URIs: {mirrors[suffix]}"
        seen.add(suffix)
if seen != set(mirrors):
    raise SystemExit(f"unexpected Debian deb822 sources: {sorted(seen)}")
sources.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

RUN apt-get update && apt-get install -y --no-install-recommends \
      cloud-image-utils libguestfs-tools linux-image-amd64 openssh-client ovmf qemu-system-x86 qemu-utils \
      ca-certificates curl unzip \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fL --retry 3 "https://releases.hashicorp.com/packer/${PACKER_VERSION}/packer_${PACKER_VERSION}_linux_amd64.zip" -o /tmp/packer.zip \
 && echo "${PACKER_SHA256}  /tmp/packer.zip" | sha256sum -c - \
 && unzip -q /tmp/packer.zip -d /usr/local/bin \
 && mkdir -p /usr/share/licenses/packer \
 && mv /usr/local/bin/LICENSE.txt /usr/share/licenses/packer/LICENSE.txt \
 && rm /tmp/packer.zip

WORKDIR /opt/iaas
COPY pyproject.toml uv.lock ./
ARG UV_DOWNLOAD_URL=https://github.com/astral-sh/uv/releases/download/0.12.9/uv-x86_64-unknown-linux-gnu.tar.gz
RUN curl -fL --retry 3 "$UV_DOWNLOAD_URL" -o /tmp/uv.tar.gz \
 && echo 'ec7a99cd05e0cd7f80243f135ce1361c76835cb0ee60055d14d20eba8eba1460  /tmp/uv.tar.gz' | sha256sum -c - \
 && tar -xzf /tmp/uv.tar.gz -C /tmp \
 && cp /tmp/uv-x86_64-unknown-linux-gnu/uv /usr/local/bin/uv \
 && rm -rf /tmp/uv.tar.gz /tmp/uv-x86_64-unknown-linux-gnu \
 && uv sync --locked --no-dev --group runtime --python /usr/local/bin/python3.12 --no-install-project

COPY automation/src/ automation/src/
COPY automation/ansible/ansible.cfg automation/ansible/ansible.cfg
COPY automation/ansible/collections/ automation/ansible/collections/
COPY automation/packer/qemu/ automation/packer/qemu/
RUN mkdir -p /opt/packer/plugins \
 && packer init automation/packer/qemu/debian-13 \
 && chmod -R a+rX /opt/packer
COPY --chmod=755 automation/runtime/entrypoint.sh /usr/local/bin/iaas

WORKDIR /work
ARG OCI_SOURCE="https://github.com/c1emon/iaas"
ARG OCI_REVISION="development"
ARG OCI_VERSION="development"
LABEL org.opencontainers.image.source=$OCI_SOURCE \
      org.opencontainers.image.revision=$OCI_REVISION \
      org.opencontainers.image.version=$OCI_VERSION
ENTRYPOINT ["/usr/local/bin/iaas"]
