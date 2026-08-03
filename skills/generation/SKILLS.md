---
name: project-generation-workflow
description: Reusable static workflow for generating, repairing, completing, packaging, and reviewing software projects from current user intent and repository evidence, with hard limits on unapproved artifacts and repository expansion.
---

# Project Generation Workflow

## Purpose

Use this Skill to generate, repair, complete, package, or statically review a software project from current user requirements and repository evidence.

This is a reusable development workflow. It must not embed product-specific requirements, repository-specific conclusions, fixed technologies, fixed paths, named business flows, sample credentials, or assumptions copied from one project.

Project-specific facts belong in the current user request, repository rules, source, configuration, tests, documentation, and task-scoped evidence.

## Ownership boundary

This Skill owns generation and repair methodology. It does not replace:

- project-specific repository rules;
- platform or framework guidance loaded for the task;
- a dedicated acceptance workflow;
- repository build, test, release, or submission instructions.

Static self-review is required, but it is not formal acceptance. The generator must never claim that its own implementation has passed independent acceptance.

## User-intent hierarchy

Use this order for every implementation and artifact decision:

1. the user's explicit current instruction;
2. explicit user corrections and non-goals;
3. controlling repository rules;
4. original authoritative specification;
5. an accepted plan item only when the exact deliverable was disclosed to the user;
6. current production architecture and repository conventions;
7. tests and documentation;
8. implementation preference or convenience.

A lower source cannot silently expand a higher source.

## Plan is not creation authorization

A plan, design, checklist, source-layout suggestion, acceptance matrix, or document path list does not by itself authorize creation of those files.

Before creating an artifact that the user did not explicitly name, establish both:

- requirement necessity; and
- creation authorization under the rules below.

Words such as `plan`, `proposed`, `suggested`, `for example`, `fixtures`, `samples`, `helpers`, or a directory tree are not automatic authorization.

An accepted plan authorizes creation only when its acceptance report exposed the exact proposed manifest to the user and classified every path as required or optional. Optional paths remain unapproved until explicitly selected.

## Absolute blocker and no-bypass rule

Any execution blocker immediately stops the blocked operation.

Blockers include missing repository, branch, revision, file, permission, approval, required source, required capability, or an unresolved rule conflict.

When blocked:

1. stop the blocked operation;
2. preserve the last confirmed state;
3. identify the exact operation, tool, path, permission, policy, or approval;
4. state what was completed and what was not;
5. give the exact user action that removes the blocker;
6. do not switch accounts, repositories, branches, tools, proxies, or workflows to evade it;
7. do not claim success or validation for blocked work.

Destructive, publishing, merging, releasing, force-updating, deleting, or irreversible actions require explicit authorization.

## Core static-generation rule

Generation and repair under this Skill are static source-completion tasks.

Do not:

- run project code;
- run unit, integration, API, browser, device, regression, or acceptance tests;
- execute repository scripts or generated binaries;
- build packages, applications, images, or containers;
- start services, databases, browsers, simulators, devices, or deployments;
- trigger, retry, approve, cancel, or wait for CI;
- treat an external result as a prerequisite for continuing static implementation;
- stop after a minimum patch or first defect;
- defer statically identifiable work merely to reduce effort.

Existing logs, reports, screenshots, artifacts, or CI results may be inspected read-only. Missing runtime evidence does not block static source completion, but it must remain clearly unverified.

## Required pre-work record

Before editing, record:

```text
target repository/package
base revision and working branch
loaded rules and stable identifiers
original user instruction
user corrections and non-goals
project and surface classification
atomic requirement ledger
affected existing owners
exact proposed added, modified, renamed, and deleted paths
authorization basis for every proposed path
lower-footprint alternatives
new top-level directories
new dependencies and toolchains
fixtures, samples, examples, demos, reports, and generated assets
publication and destructive-action authorization
prohibited or unavailable operations
expected static checks
known blockers
```

If this record cannot be established, stop before editing.

## Pre-write artifact manifest hard gate

Before the first repository write, create this table:

```text
Path | Action | Requirement source | Existing owner considered | Why separate artifact is necessary | Lower-footprint alternative | Required/optional | Authorization basis | Long-term owner | Status
```

Every row must be `APPROVED` or `REJECTED` before writing.

### Directly authorized artifacts

An artifact is directly authorized when:

- the user explicitly names the exact path or artifact; or
- the repository already contains the owner and the request clearly requires changing it; or
- an accepted plan disclosed that exact required path and the user authorized implementation of that manifest.

### Material-expansion disclosure

Before writing, present the exact new-path manifest to the user and obtain approval when any of these applies:

- a new top-level directory;
- a fixtures, samples, examples, demos, mock-data, snapshots, generated, reports, or artifacts directory;
- a new dependency, package manager, runtime, build system, framework, or toolchain;
- a material multi-file expansion from a documentation-only or minimal repository;
- generated source or copied third-party assets;
- a new test architecture rather than additions to the existing test owner;
- optional artifacts that are not necessary for runtime correctness.

Do not conceal material expansion inside an update message or final report after the write.

## Minimal repository delta rule

Complete delivery does not mean maximum file count.

Choose the smallest maintainable repository delta that fully satisfies the requirements and current architecture.

For every proposed new artifact ask:

1. Does removing it break an explicit requirement?
2. Can an existing file or owner contain the content without harming clarity?
3. Is a separate reusable owner justified by actual reuse, format, size, lifecycle, or tooling?
4. Is it only convenient for implementation, testing, review, or explanation?
5. Does it create a new directory, toolchain, maintenance burden, or public contract?
6. Was the exact artifact disclosed and authorized?

A new file is invalid when the answer to necessity is no, or when an existing owner is sufficient.

Do not generate ornamental architecture, speculative abstractions, duplicate wrappers, unnecessary modules, placeholder owners, arbitrary reports, extra examples, or directory structures merely because they look complete.

## Test data, fixtures, samples, examples, and demos

These artifacts require an independent necessity decision.

Default order:

1. use an existing test helper or existing fixture owner;
2. use a local constant or inline representative input in the relevant test;
3. use a shared helper inside the existing test layout when multiple tests genuinely reuse it;
4. create a separate fixture file only when its native format, realistic size, parser behavior, binary form, readability, or repeated reuse makes inline data materially worse;
5. create a new fixture directory only when multiple necessary fixture files share a stable long-term owner and the directory was disclosed and authorized.

Test convenience alone is not sufficient.

Every fixture/sample row must record:

```text
Path | Purpose | Requirement | Why inline is insufficient | Reuse count | Synthetic/real | Runtime inclusion | Owner | Authorization
```

Never commit real credentials, network identities, local addresses, hostnames, MAC addresses, personal data, logs, packet captures, scan exports, or user-generated runtime state unless explicitly required and safely handled.

## Complete-delivery rule

Scope is determined by complete user requirements and repository constraints, not by minimizing effort. Artifact count is minimized only after requirements are complete.

Before delivery:

1. reconstruct the request into atomic requirements;
2. classify all user-facing and machine-facing surfaces;
3. inspect every materially affected repository area;
4. map requirements to existing production, schema, configuration, API, UI, test, documentation, packaging, migration, and deployment owners;
5. approve the exact artifact manifest;
6. resolve all statically identifiable contradictions, omissions, unsafe fallbacks, stale paths, and disconnected artifacts;
7. update affected owners together;
8. add necessary tests without inventing convenience artifacts;
9. compare the actual delta with the approved manifest;
10. stop if unexpected artifacts, permission blockers, or unresolved scope expansion appear.

A narrow request requires a narrow change. A broad request does not authorize unrelated expansion.

## Project and surface classification

Classify from evidence rather than assumption. Possible surfaces include backend service, browser UI, native UI, desktop app, CLI, library/SDK, plugin, data workflow, infrastructure, firmware, documentation-only artifact, design prototype, or multi-surface product.

For every surface record:

```text
intended user/caller
entry point and lifecycle
state and data owner
permissions and dependencies
visible or machine output
failure and recovery
implementation owner
test owner
documentation owner
```

Do not let one surface erase another.

## Atomic requirement ledger

Use:

```text
ID | Requirement | Source | Surface | Existing owner | State/data owner | Contract/interaction path | Test/static path | Documentation owner | Status | Gap
```

Include architecture, state, persistence, APIs, commands, events, authentication, authorization, privacy, security, configuration, secrets, observability, deployment, packaging, installation, upgrade, rollback, UI, accessibility, positive, negative, boundary, conflict, recovery, destructive paths, repository hygiene, and artifact necessity.

A requirement is incomplete when only its route, type, mock, fixture, screenshot, prose, or happy path exists.

## Architecture generation contract

Resolve from current evidence:

- process and module boundaries;
- dependency direction;
- state ownership;
- synchronous and asynchronous flows;
- persistence and transaction boundaries;
- concurrency and re-entrancy;
- error propagation;
- configuration and secret ownership;
- logging and observability;
- startup, shutdown, migration, upgrade, and rollback;
- packaging and deployment;
- external dependency and offline assumptions;
- platform lifecycle obligations.

Preserve the repository architecture unless the user explicitly requests migration.

Do not split code into modules merely to match a plan tree. Split only when responsibility, reuse, file size, dependency direction, testability, lifecycle, or repository convention justifies a separate owner.

## Data, API, command, event, and library contract

When applicable, implement entities, identifiers, constraints, versions, request/response schemas, validation, errors, ordering, pagination, idempotency, replay behavior, authorization, compatibility, serialization, storage, side effects, and positive/negative/boundary/failure tests.

All producers, consumers, tests, and docs must agree statically.

## User-interface contract

For every material UI or interactive surface define:

- user goal, entry, exit, navigation, restore, and interruption behavior;
- environment-owned versus product-owned regions;
- component hierarchy and ownership;
- data sources, events, state, and mutations;
- dimensions, spacing, typography, colors, icons, density, overflow, scrolling, zoom, and adaptive behavior;
- default, loading, empty, success, validation, request-error, permission, conflict, stale, destructive, offline, and read-only states;
- keyboard order, focus, accessible names, announcements, and non-pointer operation;
- cancellation, escape, pointer cancellation, lost focus, route change, retry, and recovery;
- reduced-motion behavior when motion exists.

Do not create a design-system catalog, icon library, sample screen, prototype directory, or asset set unless required and authorized.

A static image is not an interaction specification. A prototype does not replace requested production implementation.

## Documentation contract

Documentation is stable project source, not a transcript of the work.

Update existing documentation owners before creating new ones. Document current scope, non-goals, architecture, state, contracts, security, UI behavior, accessibility, errors, recovery, deployment, tests, limitations, and evidence status where applicable.

Do not add task chronology, tool failures, branch history, assistant corrections, temporary checklists, generic recommendations, or untracked future work.

A new document requires the same artifact-manifest approval as source code.

## Tests and static evidence contract

For changed behavior, add or update assertions in the existing test layout when tests are in scope.

Cover applicable positive, denial, invalid, boundary, duplicate, re-entrant, state, terminal, loading, empty, error, conflict, retry, recovery, persistence, migration, accessibility, adaptive, cancellation, interruption, and platform paths.

A test name, mock, fixture, sample, type, or placeholder is not evidence without assertions covering expected result and side effects.

Do not claim execution. Static completion means only that source and test definitions are present and consistent.

## Configuration, packaging, deployment, migration, and rollback

Trace every required value through application configuration, installation configuration, package manifests, build ownership, deployment manifests, migrations, startup/shutdown, persistent state, upgrade compatibility, secrets, permissions, offline assumptions, tests, and docs.

Reject disconnected configuration, undocumented fallbacks, fixed machine identity, unowned generated output, and migration claims without implementation.

Do not add a package manager, lockfile, container, workflow, installer, generated contract, or deployment directory unless required and authorized.

## Security, privacy, and observability

Map trust boundaries, authentication, authorization, field visibility, credentials, storage, transport, logging, analytics, telemetry, permissions, destructive operations, import/export, backup/recovery, dependencies, UI masking, tests, and docs.

Do not rely on UI hiding as authorization. Do not invent security claims. Do not log credentials, secrets, protected content, full sensitive payloads, or private environment values.

## Repository hygiene

- use the resolved repository root only;
- preserve existing language, architecture, package, test, and documentation conventions;
- avoid parallel projects, duplicate roots, placeholder files, no-op files, samples, and unrelated outputs;
- exclude runtime databases, caches, build output, logs, temp files, secrets, exports, generated reports, and real environment data;
- inspect paths for portability, case collisions, spaces, control characters, locale dependence, symlink risks, and near duplicates;
- preserve exact paths unless rename is required;
- do not create replacement rule files or invent rule paths.

## Static development workflow

For repository changes:

1. load controlling rules and current requirements;
2. resolve target, revision, branch, permissions, and allowed actions;
3. stop on blockers;
4. classify project and surfaces;
5. build the atomic requirement ledger;
6. map requirements to existing owners;
7. build and approve the exact artifact manifest;
8. disclose material expansion before writing;
9. implement the complete approved surface;
10. add necessary tests using the minimum justified test-data footprint;
11. update configuration, contracts, UI, comments, and docs consistently;
12. inspect the complete source statically;
13. compare actual delta against the approved manifest;
14. stop and report any unexpected path rather than rationalizing it after creation;
15. repeat until every requirement is complete, blocked, or explicitly unresolved;
16. report without claiming external execution or formal acceptance.

## Post-write delta hard gate

Before delivery, produce:

```text
Approved path | Actual action | Matches manifest? | Necessity still valid? | Unexpected artifact? | Required correction
```

Also compare:

```text
baseline file count
actual file count
new top-level directories
new dependencies/toolchains
fixtures/samples/examples/reports/generated artifacts
unexpected modifications or deletions
```

If an unexpected artifact has already been published, do not silently delete it. Stop, identify it, and obtain destructive authorization when deletion is required.

## Submission rules

When publication is explicitly requested and authorized:

- use the existing workflow;
- keep the branch and change set purpose-specific;
- exclude unrelated cleanup and generated state;
- do not merge, force-update, delete, release, or publish without explicit approval;
- stop when permission, policy, review, or approval blocks publication;
- do not bypass the blocker through another account, branch, tool, workflow, or repository.

## Static evidence model

Use this order:

1. user instruction and corrections;
2. controlling rules;
3. current production source, schema, configuration, manifests, UI, and contracts;
4. current tests and static guards;
5. current documentation and comments;
6. pre-existing external artifacts, read-only and optional;
7. summaries and claims.

A missing external result does not demote complete static source. A green external result does not excuse a static contradiction or unauthorized artifact.

## Completion criteria

Before delivery answer:

1. Is every atomic requirement mapped to an owner?
2. Does every added artifact have requirement, necessity, alternative, authorization, and long-term owner evidence?
3. Were exact new paths disclosed before material expansion?
4. Did the actual delta match the approved manifest?
5. Could any fixture, sample, helper, report, module, or directory be removed or inlined without breaking a requirement?
6. Do source, schema, configuration, API, UI, packaging, tests, and docs agree?
7. Are positive, negative, boundary, failure, conflict, destructive, and recovery paths defined?
8. Are accessibility, adaptive behavior, permissions, privacy, and security explicit where applicable?
9. Were all blockers handled without bypass?
10. Is the result described as generated and statically reviewed rather than independently accepted?

If any required answer is no, generation is not complete.

## Final response contract

The final response must include:

- target repository/package, base revision, branch, and final revision;
- loaded rule paths and identifiers;
- user intent, corrections, and non-goals;
- exact existing files changed;
- exact files created, renamed, and deleted;
- necessity and authorization summary for every created path;
- new top-level directories, dependencies, toolchains, fixtures, examples, reports, and generated assets;
- approved-manifest versus actual-delta result;
- repository reads and writes actually performed;
- external execution performed: `none` under this Skill;
- CI triggered or awaited: `none`;
- blockers and exact required user actions;
- remaining static defects, unresolved requirements, inaccessible sources, risks, and acceptance work still required.

Do not claim formal acceptance. Do not describe optional or convenience artifacts as required after the fact.
