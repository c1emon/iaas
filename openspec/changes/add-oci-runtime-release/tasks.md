## 1. Generic environment and runtime paths

- [x] 1.1 Confirm the implementation branch under repository rules and refresh GitNexus impact for actual edit targets; record callers/risk and confirm the worktree has no unrelated changes before implementation.
- [ ] 1.2 Replace `ASTRA` and fixed environment defaults with explicit `ENVIRONMENT_DIR`/`OUTPUT_DIR`, preserving operation names and schemas; verify missing inputs and legacy selectors fail, while environment-independent commands still work.
- [ ] 1.3 Route generated/runtime paths and Ansible inventory, vars, roles, Collections and plugins through the selected directories, retaining environment-supplied secret references without a fixed vault; verify a read-only non-Astra environment works from an arbitrary working directory with no implicit Astra reads/writes or offline secret resolution.
- [ ] 1.4 Generalize generated source descriptions, PVE helper paths, execution variable prefixes and their callers/bootstrap/sudoers assets; verify naming regressions and existing helper argument/identity/locking tests, and document the separate host cutover prerequisite without touching hosts.
- [ ] 1.5 Migrate supported local/CI callers and add directory-boundary/UID coverage; verify existing grouped regressions pass with explicit inputs and unsafe output placement fails before writes.

## 2. Container contents and OpenTofu integration

- [ ] 2.1 Add a Linux amd64 build definition with explicit runtime-only copy allowlist/exclusions and `/opt/iaas` layout; inspect the final image and its layers for absence of docs/READMEs, OpenSpec, tests/fixtures, examples, CI/editor files, build-only tools and real environment/runtime material, while retaining required licenses and runtime metadata; verify existing container smoke operations still work after pruning.
- [ ] 2.2 Lock the base, execution tools, Python runtime group and Collection dependency closure; verify uv locked installation, required command versions, upstream download checksums and redistribution notices without runtime dependency installation.
- [ ] 2.3 Add the minimal operation entrypoint and writable home/cache conventions; verify no-argument help is side-effect-free and an explicit caller UID can use mounted outputs without weakening secret-file or SSH checks.
- [ ] 2.4 Add a synthetic external OpenTofu root using the documented image-local module source and provider lock; verify backend-disabled init with lockfile preservation and validate without infrastructure/state access.

## 3. Representative software validation

- [ ] 3.1 Add a repository-owned container smoke command covering grouped PVE/services/foundation generate/check and K3s composition/rendering; verify it passes with no source checkout, no credentials, read-only input and disabled container networking.
- [ ] 3.2 Exercise packaged Ansible roles/Collections/lookup/filter loading and focused invalid-input, stale-output and missing-directory cases; verify the real shipped entrypoint/resources are used and no external mutation occurs.
- [ ] 3.3 Reuse build/smoke commands in PR/main CI without GHCR credentials; run the current aggregate checkout gate with explicit inputs plus secret scanning and report software-only results.

## 4. Release-to-GHCR workflow

- [ ] 4.1 Add `release.published` handling for supported stable/prerelease tags and exact tagged revision selection; verify representative event fixtures reject drafts, edits, tag-only pushes and invalid versions, and document automated-Release token suppression.
- [ ] 4.2 Gate publication on repository and image checks, transfer the tested image without rebuilding, and limit package-write permission to the dependent publish job; verify workflow configuration and build/publish identity continuity with local fixtures.
- [ ] 4.3 Publish canonical version tags and OCI source/revision/version metadata using `GITHUB_TOKEN`; verify concurrency, absent-image retry, existing-version no-overwrite and conflicting-source failure with focused registry substitutes before any actual publication.
- [ ] 4.4 Record the pushed digest in the CI summary and add clean anonymous pull/minimal invocation; verify failures distinguish push success from public consumption and do not report distribution success prematurely.

## 5. Documentation and delivery acceptance

- [ ] 5.1 Update canonical operator/developer docs, generic local/container examples, naming migration, external module-root example, noninteractive input requirements, public package setup and rerun guidance; verify examples match the tested command interface and retain platform/private-CI ownership boundaries.
- [ ] 5.2 Synchronize the delivery decision and relevant current docs to reflect GHCR publication and generic execution paths; run `openspec validate add-oci-runtime-release --strict` and appropriate repository checks, and run GitNexus change analysis before any implementation commit.
- [ ] 5.3 When an actual Release is authorized, record its successful workflow, source revision and GHCR digest plus anonymous pull result; leave this task unchecked if only local or simulated publication evidence exists, and do not treat it as Forgejo or infrastructure acceptance.
