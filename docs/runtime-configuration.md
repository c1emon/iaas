# Runtime configuration

The versioned entry selects caller-owned component documents; it does not replace
their existing domain schemas. Configuration-relative paths resolve against the
entry file. `$ref` nodes in selected documents resolve named facts from that entry.
No shell expansion, template evaluation or recursive scenario merge is performed.

```yaml
schema_version: 1
environment: lab
facts:
  network: ./network.yml
components:
  opnsense:
    inputs:
      aliases: ./router/aliases.yml
scenarios:
  maintenance:
    opnsense:
      inputs:
        aliases: ./router/maintenance-aliases.yml
```

The default `components` mapping is used without `--scenario`. A selected scenario
replaces each component mapping it names, in full; other components retain their
default mapping. Unselected scenes and unused fact files are not loaded.

Each component mapping accepts `inputs` (named YAML documents), `files` (explicit
auxiliary file paths), and `options` (operation options). Required domain inputs:

| Component | Input names | Non-sensitive generation |
| --- | --- | --- |
| pve | cluster, vms | tfvars, Ansible inventory, VM documentation, template build parameters |
| services | services, vms | service documentation |
| foundation | inventory | recovery documentation |
| k3s | intent, inventory | composed K3s review |
| opnsense | one or more of aliases, vips, gateways, filter-rules | validated desired-state YAML |
| switch | config | validated collection-native configuration YAML |

An entire reference node looks like `{ $ref: facts.network.management }`.
The reference preserves the fact's type; the existing component validator checks
the resolved document. Missing and cyclic reachable references fail. Independent
policy fields remain independent even when their values happen to be equal.

Two synthetic layouts are provided: [flat](examples/runtime/flat/environment.yml)
and [facility-oriented](examples/runtime/facility/environment.yml). Both select the
same input facts without requiring an internal Ansible directory structure.

For development, run the offline compiler through the project environment:

```sh
PYTHONPATH=automation/src uv run python -m iaas_automation.runtime_config \
  --environment docs/examples/runtime/flat/environment.yml \
  --component opnsense --operation check
```

`generate --output <new-directory>` writes only the selected component's derived
files. It refuses existing destinations and overlap with source files or runtime
implementation resources, including resolved symlinks. Source documents are not
rewritten. Existing directory/file commands remain supported; migration is an
explicit new entry pointing at existing documents, not an automatic conversion.

The separate caller-owned runtime selection contains `interface_version: 1`, an
explicit `image` release tag or digest, and `platform: linux/amd64`. Native arm64
runtime support is not declared. `latest`, missing tags and unknown interfaces are
rejected; Apple Silicon must explicitly select amd64 emulation. Backend locations
and credentials belong to caller configuration, never these synthetic examples.

Launcher and online lifecycle instructions will be added with their implementation.
