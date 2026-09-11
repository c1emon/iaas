FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS tools
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /downloads
ARG TARGETARCH
RUN case "$TARGETARCH" in \
      amd64) uv_arch=x86_64; checksum=ec7a99cd05e0cd7f80243f135ce1361c76835cb0ee60055d14d20eba8eba1460 ;; \
      arm64) uv_arch=aarch64; checksum=c36fe17937ff6bd16dc42fc13854b5465999fcab2efe0af559381e945e3c6001 ;; \
      *) exit 2 ;; \
    esac \
 && curl -fL --retry 3 "https://github.com/astral-sh/uv/releases/download/0.12.9/uv-${uv_arch}-unknown-linux-gnu.tar.gz" -o uv.tar.gz \
 && echo "$checksum  uv.tar.gz" | sha256sum -c - \
 && tar -xzf uv.tar.gz \
 && cp "uv-${uv_arch}-unknown-linux-gnu/uv" /downloads/uv
RUN mkdir -p /downloads/uv-licenses \
 && curl -fL --retry 3 https://raw.githubusercontent.com/astral-sh/uv/0.12.9/LICENSE-MIT -o /downloads/uv-licenses/LICENSE-MIT \
 && curl -fL --retry 3 https://raw.githubusercontent.com/astral-sh/uv/0.12.9/LICENSE-APACHE -o /downloads/uv-licenses/LICENSE-APACHE
RUN case "$TARGETARCH" in \
      amd64) checksum=5dc43da4f750f33873dc25e94587128709e819e544b7be9016b255316153c3a8 ;; \
      arm64) checksum=e573979ba68a17fe7b881752051a694a7efcd970e39521f6a25775197861ed4d ;; \
      *) exit 2 ;; \
    esac \
 && curl -fL --retry 3 "https://github.com/opentofu/opentofu/releases/download/v1.12.6/tofu_1.12.6_linux_${TARGETARCH}.zip" -o tofu.zip \
 && echo "$checksum  tofu.zip" | sha256sum -c - \
 && unzip tofu.zip -d tofu
RUN case "$TARGETARCH" in \
      amd64) checksum=5edcd14ab59b535040c512dbecd6ec9ef976a000b073c19d93e4c431c948581e ;; \
      arm64) checksum=cf18f03460d92265d49b56befff333e80641d845822799eab04357c39f75b5d7 ;; \
      *) exit 2 ;; \
    esac \
 && curl -fL --retry 3 "https://releases.hashicorp.com/packer/1.16.0/packer_1.16.0_linux_${TARGETARCH}.zip" -o packer.zip \
 && echo "$checksum  packer.zip" | sha256sum -c - \
 && unzip packer.zip -d packer

FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    make=4.3-4.1 openssh-client=1:9.2p1-2+deb12u10 ca-certificates=20250419~deb12u1 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=tools /downloads/uv /usr/local/bin/uv
COPY --from=tools /downloads/tofu/tofu /usr/local/bin/tofu
COPY --from=tools /downloads/packer/packer /usr/local/bin/packer
COPY --from=tools /downloads/uv-licenses/ /usr/share/licenses/uv/
COPY --from=tools /downloads/tofu/LICENSE* /usr/share/licenses/opentofu/
COPY --from=tools /downloads/packer/LICENSE* /usr/share/licenses/packer/
WORKDIR /opt/iaas
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --group runtime --no-install-project --python /usr/local/bin/python3.12
COPY automation/runtime/collections.yml /tmp/collections.yml
RUN .venv/bin/ansible-galaxy collection install --no-deps -r /tmp/collections.yml -p /opt/iaas/automation/ansible/collections
COPY automation/runtime/prune.py /tmp/prune.py
RUN python /tmp/prune.py

# Publish a reusable, pruned dependency filesystem first. Repository code is
# copied only afterwards, so code-only edits reuse installed dependencies and
# preserve the dependency layer in the final image.
FROM scratch
COPY --from=dependencies / /
WORKDIR /opt/iaas
COPY Makefile ./
COPY automation/src/ automation/src/
COPY automation/ansible/ansible.cfg automation/ansible/ansible.cfg
COPY automation/ansible/playbooks/ automation/ansible/playbooks/
COPY automation/ansible/roles/ automation/ansible/roles/
COPY automation/ansible/plugins/ automation/ansible/plugins/
COPY automation/ansible/filter_plugins/ automation/ansible/filter_plugins/
COPY automation/ansible/module_utils/ automation/ansible/module_utils/
COPY automation/opentofu/modules/ automation/opentofu/modules/
COPY automation/packer/ automation/packer/
COPY automation/pve-node/ automation/pve-node/
COPY --chmod=755 automation/runtime/entrypoint.sh /usr/local/bin/iaas
COPY automation/runtime/NOTICE /usr/share/licenses/iaas-runtime/NOTICE
ENV PATH="/opt/iaas/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
    PYTHONPATH="/opt/iaas/automation/src" \
    UV_NO_SYNC=1 UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1 HOME="" \
    ANSIBLE_CONFIG="/opt/iaas/automation/ansible/ansible.cfg" \
    ANSIBLE_ROLES_PATH="/opt/iaas/automation/ansible/roles" \
    ANSIBLE_COLLECTIONS_PATH="/opt/iaas/automation/ansible/collections" \
    ANSIBLE_FILTER_PLUGINS="/opt/iaas/automation/ansible/filter_plugins" \
    ANSIBLE_LOOKUP_PLUGINS="/opt/iaas/automation/ansible/plugins/lookup"
WORKDIR /work
ARG OCI_SOURCE="https://github.com/c1emon/iaas"
ARG OCI_REVISION="development"
ARG OCI_VERSION="development"
LABEL org.opencontainers.image.source=$OCI_SOURCE \
      org.opencontainers.image.revision=$OCI_REVISION \
      org.opencontainers.image.version=$OCI_VERSION
ENTRYPOINT ["/usr/local/bin/iaas"]
