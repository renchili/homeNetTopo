# Agent Execution Bootstrap

This file is the repository entry point for agents working on `renchili/homeNetTopo`.

It defines rule loading, hierarchy, task routing, and reporting boundaries. Project-specific product and architecture constraints belong in `AGENT.md`. Reusable workflows remain under `skills/`.

## Rule hierarchy

Apply compatible instructions in this order:

1. the user's current request and explicit corrections;
2. this `AGENTS.md` bootstrap and routing file;
3. `AGENT.md` project-specific guidance;
4. the task-routed workflow under `skills/`;
5. current planning, source, configuration, tests, documentation, and exact-revision evidence.

The current file tree is evidence of the current state, not proof that the state is architecturally correct. When project guidance conflicts with an explicit user correction or stronger product evidence, correct the guidance and every affected implementation or documentation owner together.

## Required reading order

Before planning, editing, generating, reviewing, validating, committing, or reporting repository work, read:

1. `AGENTS.md`;
2. `AGENT.md`;
3. `skills/generation/SKILLS.md` for generation, implementation, repair, extension, packaging, or documentation work;
4. `skills/full-project-acceptance-hard-gates/SKILL.md` for validation, acceptance, readiness, or verdict work;
5. `README.md`;
6. `metadata.json`;
7. `docs/design.md`, `docs/api-spec.md`, `docs/plan.md`, and `docs/questions.md` when planning or implementation behavior is relevant;
8. affected source, tests, scripts, workflows, deployment files, configuration, and existing evidence.

If a required rule source is missing or unreadable, stop the blocked operation and report the exact path and operation. Do not continue from memory or invent an inaccessible rule. Creating or repairing a rule file is allowed only when the user explicitly requests missing rule generation or rule repair.

## Task routing

| Task intent | Required workflow |
|---|---|
| Generate, implement, repair, extend, package, or document project source | `skills/generation/SKILLS.md` |
| Review, verify, validate, audit, accept, reject, assess readiness, or issue a completion verdict | `skills/full-project-acceptance-hard-gates/SKILL.md` |
| Implement changes and then issue an independent verdict | Use generation rules while editing, then restart evaluation under the acceptance workflow |

A generation summary or static self-review is not independent acceptance evidence.

## Project identity

HomeNetTopo is a local-first macOS network-discovery and topology-visualization project. It collects evidence visible from the current Mac, infers a best-effort logical topology, and serves a local interactive web page.

The project must not claim complete physical visibility from a single endpoint. Product-specific runtime, scanning, privacy, API, UI, ownership, and testing constraints are defined in `AGENT.md`. Current implementation ownership and artifact policy are recorded in `docs/plan.md`; that document is not an automatic file-creation authorization or a substitute for a task-scoped requirement ledger and approved artifact manifest.

## Working record

Before repository changes, establish:

- repository, base revision, branch, and target revision;
- loaded and missing rule sources with stable identifiers when available;
- user requirement and explicit corrections;
- routed workflow and reason;
- affected existing owners;
- files proposed for creation and why no existing owner is sufficient;
- authorized and prohibited operations;
- expected static checks and known evidence gaps.

## Output boundary

Create or update only files required by the user's request, `AGENT.md`, `docs/plan.md`, the routed workflow, or established repository ownership.

Do not create a second project root, unrelated demo, duplicate rule system, arbitrary report, generated runtime inventory, local scan output, cache, log, credential file, compiled output, or real environment data.

Runtime topology JSON, local addresses, MAC addresses, hostnames, packet data, and machine-specific logs must stay out of source control. Short single-use synthetic test inputs stay inline in their owning tests. A separate fixture, sample, example, report, or generated-data path requires a demonstrated necessity and explicit authorization for the exact path.

## Evidence rules

Every repository-work response must distinguish:

- files changed;
- static inspection performed;
- commands or tests actually executed;
- CI or workflow evidence inspected;
- checks not run and why;
- remaining defects, evidence gaps, or risks.

Do not claim runtime correctness, browser validation, CI success, deployment success, release readiness, or full acceptance without direct evidence for the exact revision.

## Final response requirements

For repository work, include:

- branch name;
- commit SHA or PR number when applicable;
- exact files changed or inspected;
- loaded rule files and identifiers when available;
- selected workflow and routing reason;
- checks run;
- checks not run;
- remaining evidence gaps or risks.