# Switch Playbooks

These playbooks collect read-only facts from the `SW_CORE` SKS8300-12X switch over Telnet. Telnet credentials are supplied at runtime and must not be committed.

Run commands from the `ansible/` directory.

## `readonly-facts.yml`

Collects version and VLAN facts from the switch, parses them into structured output, and writes exports under:

```text
exports/switches/<inventory_hostname>/
```

Runtime secrets are injected with 1Password CLI, matching the OPNsense playbook pattern:

```bash
op run --env-file ../.env.switch.tpl -- uv run ansible-playbook playbooks/switches/readonly-facts.yml
```

The template maps:

```text
SWITCH_TELNET_USER=op://Astra/SW_CORE/username
SWITCH_TELNET_PASSWORD=op://Astra/SW_CORE/password
```

Adjust `.env.switch.tpl` if the 1Password item or field names differ.

Supported CLI commands are fixed to this read-only list:

- `terminal length 0`
- `show version`
- `show vlan`
- `show vlan brief`
- `show running-config`

Only `terminal length 0` is supported for pagination setup. Do not add fallback pagination commands such as `screen-rows per-page 0`.

Safety boundary:

- The playbook asserts the exact command list before connecting.
- It does not enter configuration mode.
- It rejects mutating command prefixes including `config`, `configure`, `write`, `copy`, `reload`, `delete`, `clear`, and `format`.
- Raw `show running-config` output is redacted before saving when raw export is enabled.

Export options can be overridden at runtime:

```bash
op run --env-file ../.env.switch.tpl -- uv run ansible-playbook playbooks/switches/readonly-facts.yml \
  -e '{"switch_export_formats":["yaml","json"],"switch_export_save_raw":true}'
```

Smoke-test and validation commands:

```bash
uv run ansible-playbook --syntax-check playbooks/switches/readonly-facts.yml
uv run yamllint inventories/homelab.yml inventories/group_vars/switches.yml playbooks/switches/readonly-facts.yml
uv run ansible-lint playbooks/switches/readonly-facts.yml
```

After a live run, verify the generated `facts.yml` or `facts.json` contains:

- `device.model`, `device.software_version`, `device.bootrom_version`, serial/MAC, and uptime fields from `show version`
- VLAN entries under `vlans`
- interface membership under `interfaces` with numeric `allowed_vlans`, `tagged_vlans`, and `untagged_vlans` lists

If `switch_export_save_raw=true`, verify `raw-output/show-running-config.txt` contains no plaintext local user passwords, RADIUS/TACACS secrets, or SNMP communities.
