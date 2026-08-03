---
name: full-project-acceptance-hard-gates
description: Generic hard-gated methodology for accepting a complete software project by validating requirements, implementation, repository quality, documentation accuracy, real interactions, tests, CI, artifacts, and deployment evidence.
---

# Full Project Acceptance Hard Gates

Use this skill to accept or reject a complete repository, generated project, ZIP package, branch, commit, or pull request output.

The skill is project-agnostic. Apply it to the target project at runtime. Do not encode project names, repository names, PR numbers, conversation history, or project-specific conclusions into this file.

## Core rule

A project does not pass because a test is green, a report exists, a route exists, a screenshot exists, or a PR was merged.

A project passes only when:

1. the original requirement is reconstructed into an atomic requirement matrix;
2. every material requirement is mapped to current implementation and evidence paths;
3. repository structure, file formats, naming, comments, and packaging are checked;
4. documentation and comments agree with actual implementation;
5. security, access control, workflow, and negative paths are verified separately;
6. real interaction flows are exercised when the project has a user/operator interaction surface;
7. local tests, full regression, CI, artifacts, and deployment evidence are not confused;
8. all required report tables are produced and validated;
9. no blocking gate fails.

## Evidence hierarchy

Prefer evidence in this order:

1. Executed end-to-end interaction logs, traces, recordings, screenshots tied to flows, and resulting state evidence.
2. Executed test logs and generated artifacts tied to the target commit or package hash.
3. CI workflow runs, job conclusions, and downloadable artifacts.
4. Generated summaries produced by the executed commands.
5. Current source code, migrations, configuration, manifests, scripts, and comments.
6. Static or contract guards.
7. Current documentation.
8. User claims.
9. Reviewer or assistant summaries.

Reviewer-written reports are review summaries only. They are never test artifacts.

## Status vocabulary

Use only:

```text
PASS          Implemented and directly supported by current evidence.
CONDITIONAL   Mostly acceptable, but evidence is incomplete, indirect, local-only, probe-only, or environment-limited.
FAIL          Required behavior is missing, contradicted, misleading, malformed, non-portable, or not reproducible.
NOT VERIFIED  Required evidence was not available or was not actually checked.
N/A           Not required by the original specification; reason is mandatory.
```

## Gap severity

```text
P0 blocker       Cannot accept.
P1 conditional   Acceptance requires an explicit caveat and follow-up evidence.
P2 quality       Non-blocking maintainability or presentation issue.
Evidence gap     Implementation may exist, but proof is missing.
Spec gap         Original requirement is ambiguous.
Packaging gap    Path, file, permission, format, or archive issue affects reproducibility.
Doc-code gap     Documentation or comments contradict implementation or evidence.
Interaction gap  Real user/operator behavior is missing or only simulated.
Code-quality gap Naming, structure, language idiom, or comments harm maintainability.
```

Final `PASS` is allowed only when every required gate is `PASS` or justified `N/A`. Any required `CONDITIONAL`, `FAIL`, or `NOT VERIFIED` prevents final `PASS`.

# Mandatory preflight inventory

Before judging implementation, record:

```text
repository or package path
branch, commit, tag, PR head, or ZIP SHA256
file count and root layout
source directories
test directories
documentation files
scripts and executable modes
workflow files
deployment files
migrations and configuration
artifact directories
binary, large, generated, cache, secret, and runtime files
```

For ZIP packages, compare original archive entries and modes with extracted files and modes.

No inventory means no final `PASS`.

# Hard gates

## Gate 0: Evidence provenance

Check:

- exact repository/source package;
- exact branch, commit, PR head, tag, or package hash;
- latest relevant changes;
- evidence revision matches inspected source revision;
- test/CI generated reports are distinguished from reviewer reports;
- every cited path exists in the inspected revision.

FAIL if conclusions are reused without rechecking current code, evidence belongs to another revision, or material paths are invented/stale.

## Gate 1: Requirement coverage

Reconstruct the original prompt/spec into atomic requirements grouped by:

```text
architecture
runtime and deployment
data model and persistence
storage
API contract
workflow/state machine
access control and security
authentication and sessions
protected data and masking
domain features
audit and observability
notifications and side effects
backup, restore, and operations
UI/manual/operator interaction
documentation
tests, CI, artifacts
repository/package hygiene
code quality and maintainability
```

Required table:

```text
ID | Requirement | Category | Implementation path | Test/evidence path | Status | Gap
```

FAIL if a major requirement is omitted or a verdict is issued without this matrix.

## Gate 2: Architecture and deployment model

Check required language, framework, runtime, persistence, storage model, dependency posture, build/package files, startup behavior, copied runtime assets, and deployment model.

FAIL if required architecture is absent or the project cannot build/start in the required model.

## Gate 3: Data model and persistence

Check required entities, schema constraints, source-of-truth fields, versions/history/audit, migrations, read/write alignment, and restart persistence.

FAIL if required state cannot be persisted or core constraints are absent.

## Gate 4: Authentication, session, freshness, and replay

When applicable, verify:

```text
credential storage and comparison
failed-auth lockout
session/token creation
expiration
revocation/logout
request freshness
request-id or nonce replay protection
positive tests
negative tests
```

FAIL if only the happy path is tested.

## Gate 5: Protected data and sensitive fields

For every sensitive field named or implied by the spec, verify:

```text
classification
schema location
write protection path
read/decrypt path
key source
protected format
API exposure/masking
test/static guard
```

FAIL if sensitive plaintext remains the source of truth when protected storage is required.

## Gate 6: RBAC, object access, and field visibility

Verify every role/principal, allowed and forbidden operations, object-level access, state-dependent access, visible/hidden fields, and serialization boundaries.

Required table:

```text
Role | Allowed | Forbidden | Object scope | Visible fields | Hidden fields | Positive evidence | Negative evidence
```

FAIL if forbidden paths are not tested.

## Gate 7: Workflow and terminal immutability

Check states, allowed transitions, rejected transitions, terminal-state immutability across every mutating operation, history, audit, notifications, and valid/invalid tests.

FAIL if terminal objects remain mutable or invalid transitions are accepted.

## Gate 8: Domain feature completeness

For every domain feature, verify:

```text
endpoint/command/interaction
service/domain logic
storage mutation
side effects
error handling
positive test
negative test
realistic artifact/log
implementation path
```

FAIL if a core feature is only documented, represented by a route name, or covered by a direct function stub.

## Gate 9: Audit, notifications, and configuration side effects

Check that all required mutating actions create correct audit records and notifications, sensitive metadata is protected, acknowledgement/read behavior exists, configuration/templates are editable where required, and management paths are authorized.

FAIL if side effects are missing from material mutation flows without a documented specification exception.

## Gate 10: API contract, errors, and pagination

Check generated OpenAPI/equivalent contract, route coverage, request/response schemas, authentication annotations, status codes, uniform error envelopes, pagination defaults/hard maximums, and contract tests.

FAIL if docs/routes/status/error behavior disagree or required schemas are absent.

## Gate 11: Backup, restore, and operations

Check scheduled backup behavior, actual backup artifacts, restore mechanism, point-in-time/disaster-recovery procedure, configured paths/schedules, and executed tests.

FAIL if backup/restore is required but only mentioned in documentation.

## Gate 12: Local test entrypoints

For each script record:

```text
normal command
probe command
required services
stage list
output directory
summary files
HTML/report files
logs
exit behavior
script mode
nested script invocation
```

A probe proves only entrypoint/report generation. It is not full-suite evidence.

FAIL if probe evidence is presented as full acceptance.

## Gate 13: Full regression

Check a separate full-regression entrypoint, known stages, generated summary, runtime/build acceptance, artifacts, CI/manual invocation, and portable nested scripts.

PASS requires an executed generated summary with overall pass.

FAIL if the regression entrypoint is broken by repository/package-relative paths, missing scripts, or required executable-bit assumptions.

## Gate 14: CI workflows and artifacts

Check triggers, path filters, skipped jobs, conclusions, referenced paths, artifact upload paths, failure uploads, retention, downloadability, and whether downloaded artifacts match the claimed command/revision.

FAIL if a skipped/unexecuted job is reported as passing or workflow paths do not exist.

## Gate 15: Manual UI and smoke surfaces

When required, check that the surface exists, is served, is included in the deployable artifact, exercises critical flows, and is correctly described as production UI or manual test aid.

A static screenshot is not proof of interaction.

## Gate 16: Documentation and implementation consistency

Documentation must describe the current implementation exactly.

Compare setup, commands, paths, env vars, dependencies, routes, DTOs, status codes, security behavior, storage, workflow, backup/restore, deployment, test commands, evidence status, and limitations against code and executed evidence.

Required table:

```text
Doc claim | Document path | Implementation path | Test/artifact path | Match? | Severity | Required correction
```

FAIL if documentation overstates features, claims unexecuted tests/CI/deployment, references nonexistent paths, or contradicts critical behavior.

## Gate 17: Repository and package layout

Check expected root files, stable source/test/docs/scripts/migrations/deploy paths, unambiguous package root, duplicate/conflicting files, misplaced implementation, and implementation hidden inside artifact/cache/temp directories.

FAIL if required files are missing, ambiguously duplicated, or placed only in generated output.

## Gate 18: File format, encoding, and content hygiene

Check UTF-8/declared encoding, JSON/YAML/TOML parsing, Markdown structure, SQL/shell syntax, shebangs, line endings, extension/content agreement, empty placeholders, and binary/runtime files bundled as source.

FAIL if malformed or misleading files affect execution, build, evidence, or report rendering.

## Gate 19: Source and evidence path validation

Every report claim must cite existing paths.

Required table:

```text
Claim | Implementation path | Test path | Artifact/log path | Exists? | Current revision? | Notes
```

FAIL if material evidence uses nonexistent, stale, unresolved, or reviewer-invented paths.

## Gate 20: Idiomatic naming and readable code

Check language/framework conventions for file, module, package, type, function, variable, config, env-var, route, DTO, and test names.

Names must express domain intent, especially in security, workflow, persistence, and destructive operations. Complex logic must be decomposed into understandable units. Public names must agree with docs and API contracts.

Required table:

```text
Area | Source path | Finding | Language convention | Status | Required correction
```

FAIL if misleading/non-idiomatic names make critical behavior difficult to verify or contradict public contracts.

## Gate 21: Comment quality and comment-doc-code consistency

Check that comments explain non-obvious intent rather than restating code; comments agree with implementation and documentation; TODO/FIXME/HACK/XXX items are enumerated and classified; generated code is marked; stale comments are not used as evidence.

Required table:

```text
Comment/topic | Source path | Related doc | Related implementation | Consistent? | Severity | Required correction
```

FAIL if comments/documentation claim behavior the code does not implement or critical security/workflow/storage logic is opaque and untested.

## Gate 22: Script permissions and portable execution

Check repository/ZIP mode, extracted mode, shebang, direct versus interpreter invocation, nested scripts, working-directory assumptions, normal clone/unzip behavior, shell syntax, and dependency detection.

FAIL if required scripts fail due to packaging permissions, non-portable paths, missing interpreters, or missing nested files.

## Gate 23: Source-package contamination

Scan for:

```text
__pycache__
.pytest_cache
node_modules unless intentionally vendored
*.pyc
*.class
*.o
*.db
*.sqlite
coverage output
logs
temp files
local secrets
real .env files
editor/system files
stale generated reports
```

FAIL if bundled runtime state, cache, secrets, or stale artifacts can alter tests or conceal missing implementation.

## Gate 24: Report schema and rendering

Validate the acceptance report itself:

- every required section/table exists;
- Markdown tables are valid;
- HTML uses actual HTML tables rather than raw Markdown;
- code fences and links are valid;
- statuses use the approved vocabulary;
- every `FAIL`, `CONDITIONAL`, or `NOT VERIFIED` row contains a gap and required evidence/fix;
- verdict matches gate severities.

FAIL if the report is malformed, unrendered, internally inconsistent, or links to missing evidence.

## Gate 25: Documentation pollution and invented obligations

Especially scan README, DESIGN, ARCHITECTURE, QUESTION/QUESTIONS, FAQ, PROMPT, planning, requirement-ledger, evidence-map, and docs files.

Documentation must contain only project-relevant requirements, current behavior, current evidence, and explicitly requested/tracked roadmap material.

Red flags include process residue and generic assistant language such as:

```text
next step / next steps
接下来 / 下一步
follow-up
future work
we can also / could also
还可以 / 还能
recommendation / suggested improvement
建议 / 可以考虑
nice to have
assistant/model notes
previous mistake / correction
```

Each occurrence must map to the original specification, current implementation/test, an actual tracked issue/task, or an explicit out-of-scope statement. Otherwise it is pollution.

Check README/design/question documents against each other for project purpose, features, exclusions, security, API, storage, deployment, commands, acceptance status, and limitations.

Required tables:

```text
Doc path | Pollution pattern | Excerpt | Source/justification | Classification | Required action
Doc path | Claimed obligation | Original-spec/issue source | Implementation/test path | Valid? | Gap
Topic | README claim | Design claim | Question/FAQ claim | Implementation | Consistent?
Roadmap item | Requested/tracked? | Implemented? | Acceptance relevance | Status
```

Unresolved unrelated process text is at least P1. A document claim contradicting implementation/evidence is P0. Final `PASS` is prohibited with unresolved P1/P0 documentation pollution.

## Gate 26: Real interaction and reliable guidance

Apply whenever the project has user-facing, operator-facing, reviewer/admin-facing, CLI, API-client, prompt-driven, workflow-driven, or manual validation interactions.

Unit tests, mocks, route-existence checks, toy payloads, direct service calls, and static screenshots are not sufficient real-interaction evidence.

At least one realistic end-to-end path per critical role/flow must be executed with reproducible evidence, realistic input, expected interaction, and verified resulting state.

Acceptable evidence includes browser traces, CLI transcripts, HTTP client collections with realistic payloads, screen recordings, screenshot sequences tied to a script, accessibility snapshots, operator runbook dry runs, or prompt transcripts with expected/actual outputs.

Check modern interaction quality:

```text
clear primary action
clear success continuation
clear failure recovery
loading/progress state
empty state
validation before destructive action
confirmation/cancellation for irreversible action
consistent terminology
accessible keyboard/focus behavior
specific user-facing errors
no internal/agent-like wording
```

Check negative/recovery flows where applicable:

```text
missing/invalid input
permission denied
expired/revoked session
duplicate/replay request
unsupported/large file
dependency/network failure
destructive cancellation
terminal/finalized state
empty results
retry/recovery
```

Verify resulting state, not only status/text: database change, file/artifact change, audit/notification/event, workflow transition, or subsequent read confirming the write.

Required tables:

```text
Flow | Role | Realistic input | Expected interaction | Actual result | State verification | Evidence artifact | Status | Gap
Prompt/copy path | Intended user | Required input | Expected output | Failure/retry guidance | Actual evidence | Status
Negative flow | Trigger | Expected message/recovery | Actual result | Evidence | Status
Evidence item | Real or mock | What it proves | What it does not prove
```

FAIL if mocked/synthetic evidence is reported as real interaction evidence, interaction leaves users stuck, errors are vague/unrecoverable, or critical flows lack state verification.

N/A is permitted only when the original scope truly has no human/operator interaction surface, with a written reason.

## Gate 27: Final verdict

Before the verdict, produce:

```text
scope and target revision/package hash
repository/package inventory
requirement matrix
hard gate table
source/evidence path table
documentation-code consistency table
naming/readability table
comment consistency table
documentation pollution tables
real interaction tables
test and artifact provenance table
repo/package hygiene table
gap severity table
final decision and caveats
```

Verdict rules:

```text
PASS          Every required gate is PASS or justified N/A.
CONDITIONAL   No P0, but at least one required gate is CONDITIONAL or NOT VERIFIED.
FAIL          Any P0 exists or a required core behavior is missing/contradicted.
```

# Required report template

```markdown
# Full Project Acceptance Report

## Scope
## Executive verdict
## Repository/package inventory
## Requirement matrix
## Hard gate results
## Source and evidence path validation
## Documentation-code consistency
## Code readability and naming
## Comment consistency
## Documentation pollution scan
## README/design/question consistency
## Invented obligations and roadmap validation
## Real interaction flows
## Prompt/copy reliability
## Error and recovery interactions
## State verification and mock-vs-real classification
## Test and artifact provenance
## Repository/package hygiene
## Gaps
## Final decision
```

# Anti-false-acceptance checklist

```text
[ ] Original requirements reconstructed
[ ] Current source revision/package hash confirmed
[ ] Repository/package inventory produced
[ ] Requirement matrix complete
[ ] Security and RBAC negative paths checked
[ ] Workflow invalid paths and terminal immutability checked
[ ] Documentation checked against code/tests/evidence
[ ] README/design/question pollution and contradictions checked
[ ] Idiomatic naming/readability checked
[ ] Comments checked against docs and implementation
[ ] File formats and evidence paths validated
[ ] Script permissions and nested invocations checked
[ ] Source-package contamination checked
[ ] Probe, local suite, full regression, CI, and deployment distinguished
[ ] Real interaction flows executed where applicable
[ ] Errors, recovery, prompts, and user guidance tested
[ ] Interaction state changes verified
[ ] Mock/synthetic evidence not presented as real evidence
[ ] Report rendering and links validated
[ ] Reviewer report not used as test evidence
[ ] Every caveat includes required fix/evidence
```

If any required item is unchecked, final `PASS` is prohibited.
