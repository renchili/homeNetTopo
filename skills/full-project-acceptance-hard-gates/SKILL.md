---
name: full-project-acceptance-hard-gates
description: Generic hard-gated methodology for accepting a plan, complete software project, ZIP package, branch, commit, or pull request by validating user intent, artifact necessity, requirements, implementation, repository quality, documentation, real interactions, tests, CI, artifacts, and deployment evidence.
---

# Full Project Acceptance Hard Gates

Use this Skill to accept or reject a project plan, complete repository, generated project, ZIP package, branch, commit, or pull request output.

The skill is project-agnostic. Apply it to the target project at runtime. Do not encode project names, repository names, PR numbers, conversation history, or project-specific conclusions into this file.

## Core rule

Internal consistency is necessary but not sufficient.

A plan or project does not pass merely because:

- its documents agree with each other;
- every requirement has a named owner;
- tests are green;
- a report, route, screenshot, fixture, example, or artifact exists;
- a PR was merged;
- the proposed implementation is technically possible.

A final `PASS` requires all of the following:

1. the original user intent and explicit corrections are reconstructed;
2. every material requirement is mapped to current implementation and evidence;
3. every proposed or added artifact is necessary, proportionate, and authorized;
4. optional implementation choices are not silently converted into obligations;
5. repository structure, file formats, naming, comments, packaging, and change size are checked;
6. documentation and comments agree with implementation and executed evidence;
7. security, access control, workflow, and negative paths are verified separately;
8. real interaction flows are exercised when the project has a user or operator surface;
9. local tests, full regression, CI, artifacts, and deployment evidence are distinguished;
10. the acceptance reviewer is independent from generation claims and rechecks the exact revision;
11. no blocking gate fails.

## Acceptance modes

Record exactly one mode before review:

```text
PLAN ACCEPTANCE
IMPLEMENTATION ACCEPTANCE
PACKAGE/RELEASE ACCEPTANCE
```

### Plan acceptance boundary

Plan acceptance evaluates whether the plan is correct, necessary, proportionate, and safe to authorize. It does not accept source code that does not yet exist.

A plan cannot receive `PASS` unless it includes:

- the exact proposed file and directory manifest;
- classification of every proposed artifact as required, optional, or rejected;
- a necessity explanation for every new file;
- lower-footprint alternatives considered;
- explicit separation between user requirements and implementation suggestions;
- the expected repository delta visible to the user;
- test-data and fixture policy;
- deletion, migration, publishing, and destructive-action boundaries;
- acceptance evidence that will be required after implementation.

A plan document listing a path does not itself authorize that path to be created.

### Implementation acceptance boundary

Implementation acceptance compares the actual revision against:

1. original user intent and corrections;
2. controlling repository rules;
3. the accepted requirement ledger;
4. the accepted artifact manifest, when one exists;
5. current source and executed evidence.

Unexpected files, directories, dependencies, toolchains, fixtures, examples, reports, generated assets, or scope expansion must be reviewed as new obligations. A generator's static self-review is not independent acceptance evidence.

### Package/release acceptance boundary

Package or release acceptance additionally validates archive contents, modes, installability, startup, runtime behavior, reproducibility, artifacts, deployment, and rollback evidence.

## User-intent hierarchy

Use this order when deciding whether a requirement or artifact is authorized:

1. the user's explicit current instruction;
2. explicit user corrections and non-goals;
3. controlling repository rules;
4. original specification or linked authoritative requirement;
5. accepted plan items that were explicitly disclosed as deliverables;
6. current production architecture and repository conventions;
7. tests and documentation;
8. reviewer or assistant preferences.

A lower item cannot expand a higher item silently.

Technical convenience, common practice, a plan author's preference, or easier testing is not user authorization.

## Evidence hierarchy

Prefer evidence in this order:

1. executed end-to-end interaction evidence tied to the exact revision;
2. executed test logs and generated artifacts tied to the exact revision;
3. CI workflow runs, job conclusions, and downloadable artifacts;
4. generated summaries produced by executed commands;
5. current source, migrations, configuration, manifests, scripts, and comments;
6. static or contract guards;
7. current documentation;
8. user claims;
9. reviewer or assistant summaries.

Reviewer-written reports are summaries only. They are never test artifacts.

## Status vocabulary

Use only:

```text
PASS          Implemented or planned correctly and directly supported by current evidence.
CONDITIONAL   No P0, but evidence, authorization, necessity, or environment coverage remains incomplete.
FAIL          Required behavior or boundary is missing, contradicted, unauthorized, excessive, misleading, malformed, non-portable, or not reproducible.
NOT VERIFIED  Required evidence was not available or was not actually checked.
N/A           Not required by the original specification; reason is mandatory.
```

Final `PASS` is allowed only when every required gate is `PASS` or justified `N/A`. Any required `CONDITIONAL`, `FAIL`, or `NOT VERIFIED` prevents final `PASS`.

## Gap severity

```text
P0 blocker                 Cannot accept.
P1 conditional             Acceptance requires explicit caveat and follow-up evidence or authorization.
P2 quality                 Non-blocking maintainability or presentation issue.
Intent gap                 User intent or correction was not reconstructed accurately.
Authorization gap          An artifact or operation lacks explicit or traceable authorization.
Artifact-necessity gap     A file, directory, fixture, example, report, dependency, or toolchain is not proven necessary.
Scope-expansion gap        The plan or implementation expands beyond the approved deliverable.
Evidence gap               Implementation may exist, but proof is missing.
Spec gap                   Original requirement is ambiguous.
Packaging gap              Path, mode, format, archive, or installability affects reproducibility.
Doc-code gap               Documentation or comments contradict implementation or evidence.
Interaction gap            Real user/operator behavior is missing or only simulated.
Code-quality gap           Naming, structure, idiom, or comments harm maintainability.
```

## Mandatory preflight inventory

Before judging, record:

```text
acceptance mode
repository or package path
branch, commit, tag, PR head, or ZIP SHA256
original user instruction and corrections
loaded controlling rules and identifiers
baseline file count and root layout
current/proposed file count and root layout
added, modified, renamed, and deleted paths
new top-level directories
new dependencies and toolchains
source, test, documentation, scripts, workflow, deployment, migration, and artifact paths
binary, large, generated, cache, secret, runtime, fixture, example, demo, sample, and report files
publication and destructive-action authorization
```

For ZIP packages, compare archive entries and modes with extracted entries and modes.

No complete inventory means no final `PASS`.

# Hard gates

## Gate 0: Evidence provenance

Check the exact target revision or package hash, latest relevant changes, evidence-revision match, every cited path, and separation of reviewer reports from executed artifacts.

FAIL if conclusions are reused without rechecking current content, evidence belongs to another revision, or paths are invented or stale.

## Gate 1: Requirement coverage

Reconstruct the original prompt, specification, and user corrections into atomic requirements grouped by:

```text
user intent and non-goals
architecture
runtime and deployment
data model, state, storage, and persistence
API, command, event, or library contract
workflow and state machine
access control, authentication, privacy, and security
domain features and side effects
audit, observability, backup, restore, and operations
UI, CLI, manual, or operator interaction
accessibility and adaptive behavior
documentation and handoff
tests, CI, artifacts, and release evidence
repository hygiene, artifact necessity, and maintainability
```

Required table:

```text
ID | Requirement | Source | Category | Implementation/plan path | Test/evidence path | Status | Gap
```

FAIL if a material requirement, correction, non-goal, or deliverable boundary is omitted.

## Gate 2: Deliverable boundary and invented obligations

For every claimed obligation, identify its source.

Required table:

```text
Obligation | User/spec/rule source | Required or optional | Disclosed to user? | Accepted? | Status | Gap
```

FAIL if an optional design choice, test convenience, best practice, example, fixture, directory suggestion, or plan-author preference is treated as a required deliverable without authorization.

## Gate 3: Artifact necessity and repository proportionality

Review every proposed or actual added path, new top-level directory, dependency, toolchain, generated artifact, fixture, sample, example, demo, report, schema, script, workflow, and documentation file.

Required table:

```text
Path/artifact | Added/changed | Requirement source | Why existing owner is insufficient | Runtime/test/doc necessity | Lower-footprint alternative | User-visible and authorized? | Status | Required action
```

For each item ask:

- Does removing it break a stated requirement?
- Could an existing file or established owner contain the content?
- Is it reusable enough to justify a separate owner?
- Is it only convenient for testing or review?
- Is it a temporary sample, example, placeholder, or generated report?
- Does it introduce a new directory or maintenance obligation?
- Was the exact artifact disclosed before authorization?

A fixture or sample directory is not automatically justified by parser tests. Inline test data, local constants, existing test helpers, or fewer representative cases must be considered.

FAIL if a convenience-only or unapproved artifact remains, if the repository expands materially without justification, or if the acceptance report omits this table.

## Gate 4: Plan implementability and manifest accuracy

Apply in plan acceptance.

Check that the proposed manifest is exact, complete, minimal, consistent with repository conventions, and separates required paths from optional alternatives. Check that implementation sequencing does not make optional paths mandatory.

Required table:

```text
Proposed path | Owner | Requirement | Required/optional | Creation reason | Alternative | Expected validation | Status
```

FAIL if the plan uses vague phrases such as `files such as`, hides material directory expansion, or treats its own path list as authorization.

## Gate 5: Architecture and deployment model

Check required language, framework, runtime, persistence, dependency posture, build/package files, startup, lifecycle, copied assets, and deployment model.

FAIL if architecture is absent, contradicted, unnecessarily replaced, or cannot operate in the required model.

## Gate 6: Data model, state, and persistence

Check entities, identifiers, constraints, source-of-truth fields, versions, history, migrations, atomicity, read/write alignment, concurrency, restart behavior, and failure preservation.

FAIL if required state or invariants are absent.

## Gate 7: Authentication, authorization, freshness, replay, and sensitive data

When applicable, verify credential handling, session/token lifecycle, revocation, freshness, replay protection, roles, object scope, field visibility, protected formats, key sources, masking, positive tests, and negative tests.

Required table:

```text
Principal/role | Allowed | Forbidden | Object scope | Visible fields | Hidden fields | Positive evidence | Negative evidence | Status
```

FAIL if forbidden paths are untested or sensitive data boundaries rely only on UI hiding.

## Gate 8: Workflow, conflicts, terminal states, and recovery

Check states, valid and invalid transitions, re-entrancy, conflicts, cancellation, interruption, retries, rollback, terminal immutability, history, audit, notifications, and recovery.

FAIL if invalid transitions are accepted or users/operators can become stuck without recovery.

## Gate 9: Domain feature completeness

For each material feature verify entry point, domain logic, state/storage mutation, side effects, error handling, positive test, negative test, realistic evidence, and implementation path.

FAIL if a feature exists only in prose, route names, mocks, screenshots, placeholders, or direct-function tests.

## Gate 10: API, command, event, and library contracts

Check route or command coverage, schemas, validation, status and error envelopes, pagination and limits, idempotency, ordering, compatibility, generated-contract ownership, and consumer/producer agreement.

FAIL if public contracts and implementation disagree.

## Gate 11: Operations, configuration, backup, restore, migration, and rollback

Check configuration ownership, secrets, startup/shutdown, installation, upgrade, migration, backup artifacts, restore mechanisms, schedules, rollback, and executed operational evidence when required.

FAIL if required operational behavior exists only in documentation.

## Gate 12: Local test entrypoints

Record each test script's normal command, probe command, required services, stage list, output paths, summaries, logs, exit behavior, permissions, working-directory assumptions, and nested invocations.

A probe proves only entrypoint or report generation. It is not full-suite evidence.

## Gate 13: Full regression

Check a separate full-regression entrypoint, known stages, generated summary, runtime/build acceptance, artifacts, portability, and executed overall result.

PASS requires executed evidence tied to the exact revision.

## Gate 14: CI workflows and artifacts

Check triggers, path filters, skipped jobs, conclusions, referenced paths, failure uploads, retention, downloadability, and artifact-revision match.

FAIL if skipped or unexecuted jobs are presented as passing.

## Gate 15: Manual UI, CLI, API-client, and smoke surfaces

Check that required surfaces exist, are packaged and served correctly, exercise critical flows, distinguish production UI from test aids, and provide loading, empty, success, error, conflict, cancellation, and recovery behavior.

A screenshot is not interaction evidence.

## Gate 16: Real interaction and reliable guidance

At least one realistic end-to-end path per critical role or flow must be executed with reproducible input, expected interaction, actual result, resulting-state verification, and evidence artifact.

Required tables:

```text
Flow | Role | Realistic input | Expected interaction | Actual result | State verification | Evidence | Status | Gap
Negative flow | Trigger | Expected message/recovery | Actual result | Evidence | Status
Evidence item | Real or mock | What it proves | What it does not prove
```

FAIL if mock or synthetic evidence is reported as real, critical flows lack state verification, or errors and guidance are vague or unrecoverable.

## Gate 17: Documentation and implementation consistency

Compare setup, commands, paths, environment variables, dependencies, routes, schemas, errors, security, storage, workflow, deployment, test commands, evidence status, limitations, and exclusions.

Required table:

```text
Doc claim | Document path | Implementation path | Test/artifact path | Match? | Severity | Required correction
```

FAIL if documentation overstates implementation, test, CI, deployment, acceptance, or release status.

## Gate 18: Repository and package layout

Check expected root files, unambiguous package root, stable owners, duplicate or conflicting files, misplaced implementation, unexpected top-level directories, hidden implementation in generated output, and actual delta against the approved manifest.

FAIL if unexpected artifacts remain or required owners are missing.

## Gate 19: File format, encoding, modes, and content hygiene

Check encoding, JSON/YAML/TOML/Markdown/script syntax, line endings, extension/content agreement, shebangs, executable modes, symlinks, placeholders, binary/runtime content, path portability, and archive-mode preservation.

FAIL if malformed or misleading files affect build, execution, evidence, or rendering.

## Gate 20: Source and evidence path validation

Every material claim must cite an existing current path.

Required table:

```text
Claim | Implementation path | Test path | Artifact/log path | Exists? | Current revision? | Notes
```

## Gate 21: Naming, structure, and readable code

Check language and framework conventions, domain intent, module size, responsibility boundaries, duplication, hidden coupling, and public-name agreement with contracts and docs.

FAIL if critical behavior is obscured or misleading.

## Gate 22: Comment quality and consistency

Check comments for non-obvious intent, agreement with code and docs, generated-code marking, and all TODO/FIXME/HACK/XXX items.

FAIL if comments claim behavior that does not exist or critical logic is opaque and unsupported.

## Gate 23: Source-package contamination

Scan for caches, compiled output, runtime state, secrets, real environment files, logs, packet captures, databases, coverage output, generated reports, editor/system files, exported user data, and real sensitive fixtures.

FAIL if contamination can alter tests, leak data, or conceal missing implementation.

## Gate 24: Test-data, fixtures, samples, examples, and demos

For each such artifact verify:

```text
Path | Purpose | Requirement source | Why inline/existing helper is insufficient | Synthetic or real | Reuse count | Maintenance owner | Included in runtime/package? | Status
```

FAIL if test convenience alone created a permanent directory, if real or identifying data is present, if redundant cases exist, or if samples are presented as product functionality or runtime evidence.

## Gate 25: Documentation pollution and roadmap validity

Scan README, design, architecture, questions, FAQ, prompt, plan, ledger, and evidence documents for process residue, assistant language, temporary history, generic recommendations, invented next steps, and untracked roadmap obligations.

Every roadmap or future item must map to user instruction, a tracked issue/task, implementation, or an explicit non-goal.

FAIL if process residue or invented obligations remain.

## Gate 26: Independent review and generator-acceptor separation

The acceptance report must state:

- who or what generated the project;
- whether the same process performed static self-review;
- which conclusions were independently rechecked;
- which evidence was executed rather than inferred;
- whether the actual diff was compared with the accepted manifest.

Static self-review can find defects but cannot by itself justify formal `PASS`.

FAIL if generation claims are reused as acceptance findings without reinspection.

## Gate 27: Report schema and rendering

Validate required sections, tables, links, code fences, approved statuses, gap explanations, and verdict consistency.

Every `FAIL`, `CONDITIONAL`, or `NOT VERIFIED` row must include the missing fix, evidence, or authorization.

## Gate 28: Final verdict

Before the verdict produce:

```text
scope and exact revision/package hash
acceptance mode
user-intent and non-goal summary
repository/package baseline and delta inventory
requirement matrix
obligation-source table
artifact-necessity and proportionality table
plan manifest or actual-manifest comparison
hard-gate table
source/evidence validation table
documentation-code consistency table
naming and comment tables
test-data/fixture/sample table
documentation pollution table
real interaction tables
test and artifact provenance table
gap severity table
final decision and caveats
```

Verdict rules:

```text
PASS          Every required gate is PASS or justified N/A.
CONDITIONAL   No P0, but at least one required gate is CONDITIONAL or NOT VERIFIED.
FAIL          Any P0 exists, a core requirement is missing, or scope/artifact expansion is unauthorized.
```

# Required report template

```markdown
# Full Project Acceptance Report

## Scope and acceptance mode
## Executive verdict
## User intent, corrections, and non-goals
## Baseline and repository/package delta inventory
## Requirement matrix
## Obligation-source validation
## Artifact necessity and proportionality
## Plan manifest or actual-manifest comparison
## Hard gate results
## Source and evidence path validation
## Documentation-code consistency
## Code readability, naming, and comments
## Test data, fixtures, samples, examples, and demos
## Documentation pollution and roadmap validation
## Real interaction and recovery flows
## Test, CI, artifact, and deployment provenance
## Gaps and required actions
## Final decision
```

# Anti-false-acceptance checklist

```text
[ ] Acceptance mode declared
[ ] Original user intent and corrections reconstructed
[ ] Current revision or package hash confirmed
[ ] Baseline and actual/proposed repository delta inventoried
[ ] Requirement matrix complete
[ ] Every claimed obligation has a valid source
[ ] Every added artifact has a necessity and authorization row
[ ] Lower-footprint alternatives were considered
[ ] Plan path listings were not treated as creation authorization
[ ] New top-level directories, dependencies, fixtures, examples, reports, and toolchains were disclosed
[ ] Optional choices were not converted into mandatory deliverables
[ ] Security, workflow, conflict, invalid, and recovery paths checked
[ ] Documentation checked against implementation and executed evidence
[ ] Naming, comments, modes, formats, and evidence paths checked
[ ] Test-data and fixture necessity checked separately
[ ] Source-package contamination checked
[ ] Probe, local suite, full regression, CI, deployment, and release distinguished
[ ] Real interaction and resulting state verified where applicable
[ ] Mock or synthetic evidence not presented as real evidence
[ ] Generator self-review not used as independent acceptance
[ ] Actual diff compared with accepted manifest
[ ] Report rendering and links validated
[ ] Every caveat includes required fix, evidence, or authorization
```

If any required item is unchecked, final `PASS` is prohibited.
