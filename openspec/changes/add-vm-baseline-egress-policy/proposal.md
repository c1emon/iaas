## Why

The common Debian VM baseline can install declared apt packages, but it relies on
whatever package sources, trust anchors, and egress settings happen to be present
in the template. K3s and other VM workloads need a reusable way to declare this
host-level access policy without baking environment proxy state or credentials
into templates and without making a workload-specific role own generic APT
configuration.

## What Changes

- Extend the existing VM bootstrap capability with an optional environment-owned
  baseline egress policy, selected explicitly and composed with generated VM
  facts while reusing the bootstrap workflow's existing host-scope semantics.
- Add idempotent Debian deb822 APT source, verified signing-keyring, APT
  proxy/direct-exception, and custom-CA management before baseline package
  installation.
- Add default-disabled global shell and Git proxy settings for the narrow cases
  that explicitly need them; do not install Git solely to configure its proxy.
- Derive host-local bypass networks from generated VM NIC facts and accept only
  explicit additional non-secret bypass destinations.
- Keep authenticated proxy material outside committed variables, inject it at
  runtime, redact output, and protect any node-side credential files.
- Support an explicit absent state that removes only deterministically named,
  role-owned policy artifacts.
- Add synthetic tests and software-only evidence. Do not bootstrap real guests or
  change Astra's current package sources and proxies in this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `vm-ansible-bootstrap`: Adds optional, fail-closed Debian package-access,
  trust, and narrowly scoped tool-proxy policy to the common VM baseline.

## Impact

- Expected implementation areas: `automation/ansible/roles/vm_baseline/`, an
  explicitly selected environment policy-vars file, focused Ansible/Python
  tests, and operator documentation.
- Existing PVE VM inventory and generated Ansible inventory schemas remain
  unchanged; the new policy consumes their NIC facts read-only.
- This change is independently implementable and is not a prerequisite for the
  K3s capability; K3s preflight may instead report current package access as
  unavailable.
- Template-build APT mirrors remain separate because they configure image build
  time, while this change configures cloned guests during VM bootstrap.
- No PVE apply, template rebuild, guest bootstrap, package update, proxy change,
  or other external mutation is part of designing this change.
