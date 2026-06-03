## 1. Inventory and Dependencies

- [x] 1.1 Add or confirm the Ansible collection dependency required for `ansible.netcommon.telnet`.
- [x] 1.2 Add switch inventory structure for `SW_CORE` without committing plaintext credentials.
- [x] 1.3 Add switch group/host variables for Telnet prompts, pagination command, export settings, and output format selection.

## 2. Read-only Telnet Collection

- [x] 2.1 Create a switch read-only playbook that connects to the SKS8300-12X over Telnet.
- [x] 2.2 Ensure the playbook sends only `terminal length 0` for pagination setup.
- [x] 2.3 Collect `show version`, `show vlan`, `show vlan brief`, and `show running-config` outputs.
- [x] 2.4 Guard the workflow so it does not run mutating commands or enter configuration mode.

## 3. Structured Parsing

- [x] 3.1 Parse `show version` output into structured model, version, BootRom, serial, MAC, and uptime facts.
- [x] 3.2 Parse VLAN definitions from collected configuration into structured VLAN ID/name facts.
- [x] 3.3 Parse interface VLAN membership for hybrid, trunk, and access switchport modes.
- [x] 3.4 Normalize parsed VLAN IDs as numeric lists suitable for YAML and JSON output.

## 4. Export and Redaction

- [x] 4.1 Add export logic that writes generated outputs under `exports/switches/<inventory_hostname>/`.
- [x] 4.2 Support configurable YAML, JSON, or combined structured export formats.
- [x] 4.3 Redact secrets before saving raw `show running-config` output.
- [x] 4.4 Optionally save raw command outputs in a predictable raw-output subdirectory when enabled.

## 5. Documentation and Validation

- [x] 5.1 Document the switch playbook usage, required runtime secrets, and supported CLI commands.
- [x] 5.2 Document that only `terminal length 0` is supported for pagination.
- [x] 5.3 Add validation or smoke-test instructions for running the read-only collection safely.
- [x] 5.4 Verify generated YAML/JSON exports contain structured version and VLAN facts and no unredacted secrets.
