# k3s_prerequisites

Installs the small, Debian-specific package set required before a K3s server or
agent is installed. The package task is convergent (`state: present`) and does
not refresh APT metadata.

This role deliberately does not manage APT sources, APT credentials or proxies,
global shell/Git proxy settings, host networking, kernel policy, or K3s
configuration. Those concerns belong to their respective workflows.

The caller must gather facts before applying the role. Non-Debian hosts and
non-APT package managers fail closed.
