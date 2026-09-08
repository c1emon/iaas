# Design review

Reviewed 2026-09-08 against source baseline `ffa4f70`, the delivery decision,
current capability specs and official GitHub/uv documentation linked in
`design.md`. This is a review of the proposed change, not implementation or
deployment acceptance. No sub-agents or live infrastructure were used.

## Findings resolved in the proposal

1. **External Make overrides alone were insufficient.** Ansible inventory and
   OPNsense variable-file defaults, generated source descriptions, PVE helper
   names and execution variables also embed Astra. The revised scope covers
   these callers, removes implicit selection in checkout and image modes, and
   records the breaking invocation/helper migration. Real environment identities
   and host protection limits are preserved.
2. **The main specs still mandated fixed Astra locations.** Added full modified
   requirements for repository ownership, PVE, services, foundation documents,
   validation, operator path maps and state guidance. Vault selection is explicit
   environment data. Existing requirement scenarios and their domain safety
   constraints are retained; historical state deletion is not reused as new
   migration authority.
3. **An external environment cannot use the checkout-relative module source.**
   The design now fixes an image-local module path and a separately mounted
   OpenTofu root, with a synthetic backend-disabled init/validate check using
   a provider lock. Backend deployment and saved-plan authorization remain
   phase 5 work.
4. **Runtime packaging could omit Ansible or leak environment data.** The design
   accounts for Ansible's current dev-group placement, loose Collection versions,
   image copy boundaries, runtime dependency installation and plugin-relative
   paths. It requires the actual packaged caller paths to be exercised.
5. **A Release or successful push is not sufficient delivery evidence.** The
   workflow tests the tagged source, publishes that tested artifact, reports its
   registry digest, checks anonymous consumption and preserves existing version
   tags on rerun. Public visibility setup and `GITHUB_TOKEN`-created Release
   trigger suppression are documented.
6. **Generic outputs must not force an environment-data migration.** Container
   defaults use a separate output mount; explicit generated-directory/file
   overrides allow existing committed generated-only subtrees to be checked.
   Runtime work remains separate from authored inputs and image resources.
7. **Only runtime necessities may ship.** Following the packaging clarification,
   the proposal, design, runtime spec and task 2.1 explicitly exclude documents,
   READMEs, OpenSpec, tests/fixtures, examples, CI/editor files and build-only
   tools from published layers. Required licenses, executable resources and
   runtime metadata remain. Runtime-generated documentation is external output,
   not image content. This is a design constraint, not an inspected image result.

## Requirement coverage

| Requested outcome / boundary | Proposed contract | Implementation verification tasks |
| --- | --- | --- |
| Generic execution for other environments | Runtime paths; repository layering; domain source/output deltas | 1.2–1.5, 3.1–3.2 |
| One OCI image with reusable code/resources and locked tools | Runtime independence and contents | 2.1–2.3 |
| No documentation or other non-runtime content in the image | Publish only runtime necessities | 2.1, 3.1–3.2 |
| External OpenTofu root resolves released modules | Module resolution contract | 2.4 |
| Release triggers CI and GHCR publication | Release source selection and credentials | 4.1–4.3 |
| Fixed digest usable by private CI | Verified immutable reference | 4.4, 5.3 |
| Representative synthetic validation, no live deployment claims | Bounded acceptance | 3.1–3.3, 5.3 |
| Current docs and contracts remain consistent | Seven modified capabilities and canonical documentation updates | 5.1–5.2 |
| Create and review only in this session | All implementation tasks remain unchecked; changes confined to this change directory | Current worktree and scoped OpenSpec validation |

## Review evidence and limits

- `openspec validate add-oci-runtime-release --strict --json`: valid, no issues.
- OpenSpec recognizes all four planning artifact types as complete; this reports
  planning readiness only.
- Eight capability delta files contain 19 requirements and 70 scenarios.
  All pre-existing scenario headings in modified requirements are preserved.
- Nineteen implementation tasks are unchecked; each includes a verification
  method. Real GHCR publication remains an explicit future acceptance task.
- GitNexus source analysis was refreshed; PVE CLI parameter impact is LOW.
  Makefile impact remains graph-UNKNOWN and was supplemented with current
  CI/test/operator caller inspection. No zero-impact claim is made.
- Source review found no remaining design blocker within this scope. Exact tool
  pins and their standard redistribution checks are implementation work; actual
  GHCR permission/visibility, runner connectivity, private credentials/backend
  and installed host helper cutover remain unverified external conditions.
- No code, workflow, live configuration, main spec, branch or commit was changed
  by this design review. No container build, test suite, Release or image push
  was executed; those would test or perform implementation not present yet.
