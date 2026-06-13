# switch_readonly_facts

Side-effect-free read-only CLI facts provider for SKS8300/XikeOS-series switches.

The role validates inputs, plans approved read-only commands, collects CLI output
over `network_cli`, and parses structured facts. It does not create directories
or write export files. Callers that want persistence should run a separate
playbook-level export workflow after the role completes.
Inventory and playbooks use `ansible_network_os: c1emon.xikeos.xikeos` with
`ansible.netcommon.network_cli`; the role collects approved commands through the
native `c1emon.xikeos.xikeos_command` module.

Supported user-facing inputs:

```yaml
switch_platform_profile: sks8300
switch_readonly_gather_subset:
  - device
  - vlans
  - interfaces
```

Do not override raw CLI command lists for this role. The `sks8300` profile maps
gather subsets to approved read-only commands, parser dispatch, and raw export
policy through `ansible/module_utils/switch_profiles/`.

Phases:

- validate runtime credentials and guardrails
- plan commands from `switch_platform_profile` and `switch_readonly_gather_subset`
- collect approved CLI output over `network_cli` with `c1emon.xikeos.xikeos_command`
- parse command-ID mapped outputs into structured facts

Output variables:

- `switch_read_command_plan`: profile-expanded approved command plan
- `switch_cli_command_results`: registered `xikeos_command` results
- `switch_cli_raw_outputs`: raw stdout list selected from command results
- `switch_command_outputs`: command-ID keyed normalized output map
- `switch_facts`: parsed structured switch facts
- `switch_raw_export_items`: profile-approved raw export plan with filenames and
  redacted content where required
- `switch_redacted_running_config`: redacted running configuration text

Migration note: callers that previously relied on this role to write
`facts.yml`, `facts.json`, `README.md`, or `raw-output/*` should import or copy a
caller-owned export task file after the role. The switch playbook uses
`playbooks/switches/tasks/export-readonly-facts.yml` for that purpose.

This keeps read-only facts separate from future configuration resources: gather
subsets select facts, the command catalog owns CLI/read-only policy, and profile
core modules own SKS8300 parsing/redaction behavior.
