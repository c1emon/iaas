# Legacy Terraform placeholder

Active PVE VM lifecycle configuration now lives under `infra/tofu/` and uses
OpenTofu. Keep this directory empty unless a future change explicitly
reintroduces Terraform-specific configuration.

Do not commit:

- `.terraform/`
- `*.tfstate`
- `*.tfvars`
- plan files
- provider credentials
