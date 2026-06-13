## 1. Interface Resource Registry

- [x] 1.1 Add an `interfaces` resource definition with primary key `name` and `collect_subset: interfaces`.
- [x] 1.2 Define interface field metadata for `name`, `mode`, `access_vlan`, `tagged_vlans`, `untagged_vlans`, and `state`.
- [x] 1.3 Add validation for supported interface modes: `access`, `trunk`, and `hybrid`.
- [x] 1.4 Add validation for SKS8300 interface names and VLAN ID lists.
- [x] 1.5 Reject mode-inconsistent fields, such as tagged VLANs on access ports or access VLANs on trunk ports.

## 2. Diff and Planning

- [x] 2.1 Reuse existing SKS8300 interface current-state parsing through the `interfaces` collect subset.
- [x] 2.2 Normalize desired and current interface VLAN lists into sorted integer lists before comparison.
- [x] 2.3 Extend diff generation to report interface mode, access VLAN, tagged VLAN, and untagged VLAN changes.
- [x] 2.4 Ensure interface operations respect `switch_config_allowed_operations` and default plan-only behavior.
- [x] 2.5 Include interface current state, desired intent, and planned operations in the redacted change report.

## 3. Command Rendering and Apply Safety

- [x] 3.1 Add SKS8300 interface command rendering from validated interface diffs.
- [x] 3.2 Render interface context blocks without accepting raw operator command strings.
- [x] 3.3 Keep rendered interface commands behind the existing forbidden command checks.
- [x] 3.4 Confirm rendered commands are wrapped by the existing SKS8300 `config` / `exit` apply transaction.
- [x] 3.5 Document that interface changes can disrupt connectivity and require explicit apply review.

## 4. Verification

- [x] 4.1 Extend post-apply verification to compare interface mode and VLAN membership against declared intent.
- [x] 4.2 Report verification failures for mismatched mode, access VLAN, tagged VLANs, and untagged VLANs.
- [x] 4.3 Add Python smoke tests or equivalent checks for access, trunk, and hybrid interface plan/verify behavior.

## 5. Vars and Documentation

- [x] 5.1 Update `ansible/vars/switches/<inventory_hostname>-vlans.yml` examples to include interface intent.
- [x] 5.2 Update `ansible/roles/switch_config/README.md` with interface resource schema and examples.
- [x] 5.3 Document low-risk live validation guidance for unused ports and manual rollback.

## 6. Validation

- [x] 6.1 Run Python compile/smoke validation for updated profile code.
- [x] 6.2 Run `yamllint` on updated switch role/playbook/vars files.
- [x] 6.3 Run `ansible-playbook --syntax-check` for the switch config playbook.
- [x] 6.4 Run `ansible-lint` on the switch config role, playbook, and vars examples.
- [x] 6.5 Run plan-only validation for interface intent on a selected low-risk port.
- [x] 6.6 Validate explicit apply and verify behavior against a low-risk live port only after operator approval, then restore the previous port configuration.
