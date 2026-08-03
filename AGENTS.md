# Agent Execution Bootstrap

This file is the repository entry point for agents working on `renchili/infoScreen`.

It defines only the rule-loading order, hierarchy, and safe operating boundary. It must not independently invent or freeze the InfoScreen directory layout. Project-specific architecture and ownership belong in `AGENT.md`, which is the InfoScreen-specialized form of these bootstrap rules.

## Rule hierarchy and derivation

Use the following relationship:

1. the user's current request and explicit corrections define the requested outcome;
2. `AGENTS.md` defines how repository rules are loaded and how evidence is handled;
3. `AGENT.md` specializes those rules for InfoScreen after reading current project planning and repository evidence;
4. `skills/SKILL.md` defines the reusable repository-work workflow and evidence boundary;
5. source, configuration, deployment definitions, tests, documentation, and current runtime evidence establish implementation facts.

`AGENT.md` is generated project guidance, not an authority above the user or the project plan. The current file tree is evidence of the current state, not proof that the current state is architecturally correct.

When `AGENT.md` conflicts with an explicit user correction, the product plan, or a stronger ownership boundary:

- do not use the conflicting `AGENT.md` sentence to justify the existing implementation;
- identify the incorrect specialization and every enforcement or documentation owner that repeats it;
- correct the project-specific rule and the affected owners together;
- distinguish the intended architecture from temporary legacy paths that still require migration.

## Required reading order

Before planning, editing, reviewing, validating, or reporting repository work, read these files in order:

1. `AGENTS.md` — this bootstrap entrypoint and rule hierarchy.
2. `AGENT.md` — the InfoScreen project-specific specialization.
3. `skills/SKILL.md` — repository workflow, evidence, validation, and delivery rules.
4. `skills/full-project-acceptance-hard-gates` — full-project acceptance rules when the task is validation, acceptance, or release readiness.
5. `README.md` — operator-facing project overview and verification commands.
6. `metadata.json` — compact product metadata and natural-language product prompt.
7. `docs/design.md`, `docs/api-spec.md`, and `docs/questions.md` when relevant.
8. Relevant source, tests, scripts, deployment files, CI workflows, and configuration files.

If a required rule source cannot be read, stop and ask the user. Do not continue from memory or guess missing rules.

## Project identity

InfoScreen is a local-first personal information screen for an always-on Surface or Ubuntu display. The repository root is `~/infoscreen`.

Do not create another project root, duplicate app, placeholder implementation, unrelated demo, or generated runtime output in source control.

## Output boundary

Create or update only files required by the current request and owned by the project-specific layout defined in `AGENT.md`.

This bootstrap file deliberately does not authorize generic root-level `deploy/`, `scripts/`, `tests/`, tool configuration, or any other project path. Their correct location must be derived from InfoScreen ownership in `AGENT.md` and the current task.

Runtime JSON, local environment files, logs, local photos, generated photo outputs, caches, compiled files, and test output must stay out of source control.

## Evidence rules

Every repository-work response must distinguish:

- code or documentation changed;
- static inspection performed;
- local commands executed;
- CI or workflow evidence available;
- checks not run;
- remaining gaps or risks.

Do not claim full acceptance, CI success, browser validation, deployment success, or runtime correctness unless there is direct evidence for the exact commit being discussed.

## Final response requirements

For repository work, include:

- branch name;
- commit SHA or PR number when applicable;
- exact files changed;
- checks run;
- checks not run;
- remaining evidence gaps or risks.
