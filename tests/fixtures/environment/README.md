# Synthetic environment regression fixture

This fixture exercises supported inventory relationships, generated outputs and offline
Ansible/OpenTofu validation. Names, addresses and credential references are synthetic;
no real environment is selected and references must never be resolved in CI.

The topology deliberately covers multiple network/storage roles, lifecycle classes,
passthrough, service references, foundation dependencies and OPNsense resource shapes.
It is test data, not a deployment recommendation or an environment starter template.

From the repository root:

```sh
export ENVIRONMENT_DIR="$PWD/tests/fixtures/environment"
export OUTPUT_DIR="$PWD/.cache/synthetic"
export GENERATED_DIR="$ENVIRONMENT_DIR/generated"
export PVE_DIR="$ENVIRONMENT_DIR/opentofu"
make generate
make check
```

Only non-sensitive generated outputs are tracked. The OpenTofu root references the
reusable module for offline validation; do not plan/apply it against infrastructure.
