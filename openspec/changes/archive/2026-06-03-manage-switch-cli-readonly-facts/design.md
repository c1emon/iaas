## Context

The repository currently manages OPNsense through API-based Ansible playbooks. The core switch is a SKS8300-12X device that is not officially supported by common Ansible network modules and is currently reachable only by Telnet. Prior exploration documented that the device uses a Cisco-like proprietary CLI with `Switch#` and `Switch(config)#` prompts, but it does not support standard Cisco IOS `configure terminal`; the correct configuration entry command is `config`.

This change focuses on safe read-only management: connecting to the switch, collecting version and VLAN-related outputs, parsing them into structured facts, and exporting those facts under the repository `exports/` tree.

Relevant verified CLI behavior:

- `terminal length 0` disables pagination.
- `show version` returns model, software version, BootRom version, serial number, MACs, and uptime.
- `show vlan` and `show vlan brief` return VLAN inventory.
- `show running-config` returns VLAN definitions, interface VLAN membership, SVI configuration, and local user configuration.
- `show mac-address-table` is valid, while `show mac address-table` is ambiguous.
- `show interface` is valid, while `show interfaces status` and `show interfaces switchport` are invalid.

## Goals / Non-Goals

**Goals:**

- Provide an Ansible playbook path for Telnet-only read-only collection from the SKS8300-12X switch.
- Parse collected outputs into structured switch facts.
- Include structured device identity fields: hostname, model, software version, BootRom version, serial number, MACs, and uptime.
- Include structured VLAN facts: VLAN IDs, names, and interface VLAN membership derived from running configuration.
- Support configurable YAML and JSON export formats.
- Write exports under `exports/` in a switch-specific subdirectory.
- Redact secrets before writing raw running configuration output.

**Non-Goals:**

- No VLAN creation, deletion, or mutation.
- No interface configuration changes.
- No configuration mode entry.
- No save, reload, delete, clear, format, or copy operations.
- No SSH enablement or migration in this change.
- No support for other switch platforms unless they match the same verified CLI contract.
- No fallback pagination commands beyond `terminal length 0`.

## Decisions

### Use `ansible.netcommon.telnet` for first-version collection

The switch is Telnet-only and does not map cleanly to a supported network OS plugin. `ansible.netcommon.telnet` can run a fixed list of commands without requiring Cisco IOS compatibility.

Alternatives considered:

- `cisco.ios.ios_command`: rejected because the device is not Cisco IOS and already fails standard Cisco config entry.
- `ansible.netcommon.cli_command`: rejected for the first version because it expects network platform plumbing that is not yet defined for this proprietary Telnet-only device.
- Custom Python/Expect script: deferred because the Ansible Telnet module already provides enough behavior for read-only command collection.

### Parse VLAN membership from `show running-config`

`show vlan` provides VLAN membership output, but `show running-config` is a more stable source for interface mode and membership lines. The parser should derive VLAN definitions and interface membership from running configuration, while retaining `show vlan` and `show vlan brief` as supporting raw outputs.

Expected interface parsing patterns include:

- `Interface Ethernet1/0/N`
- `switchport mode hybrid`
- `switchport hybrid allowed vlan 1;21;99 tag`
- `switchport mode trunk`
- `switchport trunk allowed vlan 10;50`
- `switchport access vlan 50`
- `interface Vlan1` with `ip address ...`

### Export under `exports/switches/<inventory_hostname>/`

Generated output should be kept outside source playbook directories and grouped under the repository `exports/` tree. A host-specific subdirectory avoids mixing switch snapshots.

The implementation may use timestamped child directories to avoid overwriting historical exports.

### Redact raw running configuration before writing

`show running-config` can contain plaintext or reversible secrets. Any saved raw running configuration must be redacted before writing to disk.

Minimum redaction targets:

- `username ... password 0 ...`
- `username ... password 7 ...`
- `password 0 ...`
- `password 7 ...`
- `auth-secret-key ...`
- `acct-secret-key ...`
- `snmp-server community ...`

### Keep credentials out of inventory files

Telnet credentials should be supplied through runtime secrets, environment-backed variables, or another secret manager pattern already acceptable for the repository. Plaintext credentials must not be committed.

## Risks / Trade-offs

- Telnet transmits credentials in plaintext → Keep the scope limited to the management network and avoid committing credentials; future SSH enablement can be a separate change.
- CLI output may vary by firmware → Keep parsers focused on verified SKS8300-12X output and preserve raw redacted outputs for debugging.
- `show running-config` contains secrets → Redact before export and avoid exposing raw output in debug logs.
- Parser mistakes could produce misleading VLAN facts → Include validation tasks and sample-output parser tests or check-mode fixtures where practical.
- Timestamped exports can accumulate files → Document cleanup expectations and keep export location predictable.

## Migration Plan

This is an additive read-only workflow. Deployment consists of adding Ansible inventory variables, playbooks, parser tasks, and documentation. Rollback is removing the added change artifacts and generated exports; no switch state changes are expected.

## Open Questions

- Should timestamped export directories be enabled by default, or should the default overwrite a stable `latest` output?
- Should raw command outputs be saved by default, or only when an explicit variable enables raw export?
- Should MAC address table parsing be included in the first implementation, or only collected as optional raw data?
