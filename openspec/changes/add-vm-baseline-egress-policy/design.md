## Context

`vm_baseline` currently installs environment-declared packages and services but
does not manage guest APT sources, proxy policy, or additional trust anchors. The
Packer template path already has independent build-time APT mirror inputs; those
settings must not become the mutable guest policy.

The K3s automation change consumes prepared Debian hosts and only checks APT and
artifact reachability. Generic guest package access therefore belongs in this
separate VM bootstrap change.

## Goals / Non-Goals

**Goals:**

- Add optional, environment-owned Debian package-access policy to `vm_baseline`.
- Require an explicitly selected policy-vars file and reuse the existing VM
  bootstrap target scope.
- Compose that policy with generated VM NIC facts instead of copying host IPs or
  subnets into proxy configuration.
- Apply trust, APT, and optional tool-proxy configuration in a deterministic
  order before package installation.
- Keep secret material runtime-only and every managed file narrowly scoped.

**Non-Goals:**

- Configuring K3s/containerd registries or K3s service proxy variables.
- Changing guest interfaces, routes, DNS, firewalls, or PVE networking.
- Baking environment proxies or credentials into the Debian template.
- Installing or configuring browsers, desktop applications, user dotfiles, or
  arbitrary developer tools.
- Applying the policy to real Astra guests in this capability change.

## Decisions

### Compose VM facts with environment egress policy

Generated inventory remains authoritative for VM identity, NICs, addresses, and
subnets. A separate, explicitly selected environment policy-vars file declares
only policy: lifecycle state, deb822 repository definitions, verified signing
keyrings, proxy mode and secret references, custom CA artifacts, and explicit
extra bypass destinations. The normalized model derives host-local addresses and
subnets from `pve_nics`; it rejects copied host facts and unknown policy keys.

Policy-enabled bootstrap requires the policy-vars path. It follows the existing
bootstrap contract: the generated `pve_vms` group is the default and an operator
may provide the existing narrower limit.

The lifecycle states are deliberately small: omitted policy does not take
ownership and preserves existing configuration; `present` converges the declared
policy; `absent` removes only fixed, deterministically named role-owned artifacts
identified by the policy. Omission never implies deletion.

### Apply configuration before installing packages

The role orders mutations as follows:

```text
validate complete policy, secrets, tools, keyrings, and source ownership
  -> perform all read-only host prechecks
  -> install verified repository signing keyrings
  -> install verified custom CA files and refresh trust when changed
  -> render managed deb822 APT sources and APT proxy/auth files
  -> refresh APT metadata only when required
  -> install baseline packages
  -> apply explicitly enabled shell/Git proxy settings
```

APT sources use a role-owned deb822 file and explicit `Signed-By` paths. A
repository signing-key artifact is non-secret, carries an exact SHA-256 digest,
is verified on the controller before mutation,
and is installed atomically under the role-owned `/etc/apt/keyrings` boundary
before its source is enabled. An explicitly allowed package-managed keyring may
instead be referenced by absolute path and expected fingerprint; that host path
must already exist, be readable by APT, and match before mutation. Missing or
mismatched source artifacts and package-managed keyrings fail closed.

The role does not delete arbitrary unmanaged source files. If exclusive source
ownership is requested, unknown enabled sources are discovered during the
read-only precheck. Any conflict fails before a keyring, CA, source, proxy, or
package is changed.

Bypass policy is rendered per consumer rather than copying one CIDR list into
every syntax. APT `DIRECT` entries are derived from validated repository host
names; shell/Git settings receive only host, domain, address, or subnet forms
that their selected client supports. Unsupported representations fail validation.

### Keep global shell and Git proxy support narrow

Global shell and Git proxy settings are disabled by default. They may be enabled
independently and must use non-secret endpoints. Authenticated proxy values are
allowed only for scoped APT or runtime command injection, never in a world-readable
profile script or global Git configuration. Git proxy configuration requires an
existing Git installation; enabling it does not add Git to the package set.

### Protect credentials and trust material

Committed policy contains secret references, not proxy passwords or APT
credentials. Runtime injection uses a documented protected channel and SHALL not
place resolved values in CLI arguments, generated or cached variables, Ansible
facts/fact cache, diffs, or ordinary controller temporary files. Secret-bearing
tasks use output redaction and no-diff behavior; protected temporary material is
permission-restricted and removed after the action. Credential-bearing APT files
are root-owned and restrictive. Custom CA content is pinned by exact SHA-256
before installation; read-only precheck confirms the system trust-refresh tool
already exists. TLS verification is not disabled as a proxy workaround.

### Preserve idempotence and existing safety boundaries

All policy and host preconditions are validated before the first host mutation.
Repeated bootstrap with unchanged inputs reports no change and does not refresh
trust or APT metadata
unnecessarily. `absent` removes only deterministically named role-owned keyrings,
CAs, source, proxy/auth, and optional tool-proxy files declared for retirement,
then refreshes trust or APT metadata
only when the removed state requires it. The role changes only its declared guest
files and continues to
avoid PVE lifecycle, guest network, DNS, firewall, K3s, and workload mutation.

## Risks / Trade-offs

- [A bad source or proxy blocks package installation] -> Validate the complete
  policy first and report the failing repository or endpoint before installing
  packages.
- [Global proxy settings leak credentials] -> Permit only non-secret global
  endpoints and keep authenticated values scoped to protected APT/runtime files.
- [Custom CA weakens trust] -> Require immutable identity and never enable global
  TLS verification bypass.
- [Unmanaged APT sources conflict] -> Fail closed under exclusive mode; never
  delete unknown files automatically and detect conflicts before mutation.
- [Local-network traffic is sent through a proxy] -> Derive VM subnet bypasses
  from generated inventory, validate explicit additions, and render only
  representations supported by each consumer.
- [Managed credentials remain after policy retirement] -> Require explicit
  `absent`; omission preserves state and never acts as deletion.

## Migration Plan

1. Add conservative lifecycle and policy validation with
   synthetic fixtures.
2. Add verified signing-keyring, custom-CA, and managed deb822/APT proxy tasks
   after read-only host prechecks and before package installation.
3. Add default-disabled shell and Git proxy tasks.
4. Add idempotence, redaction, invalid-policy, and unmanaged-source tests.
5. Update VM bootstrap documentation and run the complete offline validation gate.
6. Add explicit deterministic role-owned artifact retirement and reapply-the-previous-policy
   rollback documentation.
7. Archive this software-only capability change without applying it to Astra;
   introduce real environment values through a separate deployment change.
