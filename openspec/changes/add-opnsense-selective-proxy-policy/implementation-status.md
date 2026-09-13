# Implementation status

Date: 2026-09-13. The change now covers generic OPNsense declaration input and validation only. Its historical identifier is retained; it no longer proposes an iaas selective-proxy compiler.

## Current status

The revised implementation tasks are **0/8 complete**. This document supersedes the former “9/9 complete” statement. The present worktree has not been migrated to the revised ownership boundary; code, tests and ordinary operations documentation remain untouched by this planning revision.

## Historical evidence and limitation

The earlier worktree contained an independent policy compiler, a selective-proxy runtime branch and synthetic tests. A previous revision reported 169 passing tests, including 50 policy tests. Those results describe an earlier revision and the former scope only.

A subsequent correction addressed invalid multi-target inversion. The latest recorded focused run was **84 passed, 1 failed**: the local Ansible-loaded rule safety test rejected a valid integer carrying engine metadata. No fresh software test run was performed during this planning revision. Neither the earlier pass count nor the local image build establishes compatibility or completion of the revised contract.

## Required handoff

- infra-ops change `implement-opnsense-selective-proxy-routing` owns the high-level model, dedicated compiler, classification/conflict tests, resource composition, retirement and activation-stage generation.
- iaas retains only necessary generic constraints, context-aware protection, execution adaptation and standard input documentation. Code removal/migration is a future implementation task, not an action completed by editing these artifacts.
- The standard resource files form the repository boundary; iaas does not import infra-ops or accept its policy input.
- Release uses the existing process when required generic fixes are ready. No release, push, compatible published image or device acceptance is claimed here.
- Appliance inspection, shared settings, deployment batches, state handling and route evidence remain caller work. This change does not manage DNS or systems after the next hop.

## Planning verification

The proposal, design, three generic capability deltas and revised tasks define the new scope. The final multi-agent review found the alias input contract still restricted hand-written sources; the added opnsense-alias-management delta and task 1.2 now cover caller-generated aliases. Gateway/VIP inputs remain references to existing base sources in this change. This resolves the planning omission without claiming implementation or tests complete.

After both final review corrections, both changes passed `openspec validate <change> --strict`, scoped `git diff --check`, and a consistency review of the corrected requirements and tasks. All 6 local Markdown links across the changes resolved; task counts remain infra-ops 1/16 and iaas 0/8. These planning checks do not close any implementation task.
