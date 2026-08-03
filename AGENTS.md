# Agent Execution Bootstrap

This is the repository entrypoint for agents. It defines rule loading, deterministic Skill routing, missing-rule behaviour, working-record requirements, and final reporting.

Project-specific constraints belong in `AGENT.md`. Reusable workflows belong in `.agents/skills/**/SKILL.md`.

## Mandatory base loading

Before planning, editing, generating files, reviewing, accepting, committing, opening a PR, or reporting completion, load:

1. `AGENTS.md` — this bootstrap and routing file;
2. `AGENT.md` — project-adapted product, architecture, implementation, test, and delivery constraints;
3. the Skill or Skills selected by the mandatory routing table below;
4. `README.md` and relevant `docs/`, when present;
5. the affected source, tests, scripts, CI, deployment, migrations, configuration, and artifacts.

If a required rule source cannot be read, stop before editing or verdict formation. Report the exact path and failed operation. Do not continue from memory, invent a replacement, or return a raw tool error.

## Mandatory Skill routing

Skill selection is deterministic. Do not choose a weaker workflow because it is shorter or already loaded.

| Task intent | Mandatory Skill |
|---|---|
| Generate, implement, repair, extend, package, or document project source | `.agents/skills/project-generation/SKILL.md` |
| Review, verify, validate, audit, accept, reject, assess readiness, or decide whether work is complete/correct | `.agents/skills/full-acceptance-hard-gate/SKILL.md` |
| Issue `PASS`, `CONDITIONAL`, `FAIL`, `NOT VERIFIED`, approval, merge-ready, production-ready, or equivalent verdict | `.agents/skills/full-acceptance-hard-gate/SKILL.md` |
| Inspect a repository, package, ZIP, branch, commit, pull request, or generated project as a finished deliverable | `.agents/skills/full-acceptance-hard-gate/SKILL.md` |
| Generate or repair frontend, prototype, UI, UX, or interaction source | `.agents/skills/project-generation/SKILL.md` |
| Accept or review frontend, prototype, UI, UX, screenshots, Figma, Storybook, or interactions | `.agents/skills/full-acceptance-hard-gate/SKILL.md`, including its frontend reference |
| Implement fixes and then independently accept them in one task | Use project generation while editing, then restart verification under full acceptance before any verdict |

A generation Skill's static self-review is not independent acceptance. A generator's completion statement, summary, screenshot, or test definition is not acceptance evidence.

## Mixed implementation and acceptance

When a task includes both implementation and a final acceptance decision:

1. load the project-generation Skill for implementation;
2. complete the implementation pass and fix the exact target revision;
3. load the full-acceptance Skill and its required references;
4. reconstruct requirements independently rather than trusting the implementation summary;
5. perform all applicable hard gates;
6. issue the verdict only from the acceptance workflow.

During the acceptance phase, the full-acceptance Skill controls evidence, runtime interaction, prototype quality, and verdict rules. The project-generation Skill remains relevant only as an implementation contract and cannot prohibit acceptance checks required by the acceptance Skill.

## Frontend and prototype acceptance activation

Frontend acceptance is mandatory when any requirement, artifact, documentation claim, or changed path includes or implies a frontend, screen, view, page, route, UI, UX, prototype, mockup, wireframe, Figma, Storybook, HTML/CSS, screenshot, browser flow, mobile/desktop UI, plugin UI, gesture, or interactive control.

Prototype acceptance is mandatory whenever a prototype, mockup, wireframe, Figma file, Storybook story, screenshot set, HTML prototype, design specification, or implementation-guiding visual artifact is requested, supplied, referenced, generated, or used as evidence.

When activated, the acceptance agent must load:

```text
.agents/skills/full-acceptance-hard-gate/SKILL.md
.agents/skills/full-acceptance-hard-gate/references/full-hard-gates.md
.agents/skills/full-acceptance-hard-gate/references/frontend-acceptance.md
```

The agent must:

- validate the prototype itself before comparing production implementation;
- reconstruct all frontend functions and user goals into a requirement matrix;
- check every material flow, state, branch, role, result, and recovery path;
- verify the prototype resolves implementation-critical visual, interaction, responsive, content, accessibility, and data decisions;
- inspect artifact integrity, links, components, assets, contradictions, and placeholders;
- verify the prototype can drive a materially consistent and testable generated implementation;
- issue a separate prototype verdict;
- inventory the complete frontend surface rather than selected examples.

Prototype checks must not be skipped because the artifact is static, design-only, non-executable, or not yet implemented. `SKIP` is not an allowed acceptance status. Missing required prototype functionality or unresolved design decisions are `FAIL`; inaccessible evidence is `NOT VERIFIED`.

A polished image, clickable demo, or visually similar generated screen is not sufficient for `PASS`.

## Rule-file handling

Treat `AGENT.md`, `AGENTS.md`, and `.agents/skills/**/SKILL.md` as checked-in rule sources.

- Read and obey existing rule files.
- Do not generate, replace, summarise over, or synthesise alternate rule files during ordinary work.
- Modify rule files only when the user explicitly asks to change rules, workflow, evidence, validation, acceptance, or repository-operation behaviour.
- Keep reusable Skills under `.agents/skills/<skill-name>/SKILL.md`.
- Do not fall back to `skills/...` or `.chatgpt/skills/...`.
- Do not invent Skill paths.

If `AGENT.md` or a mandatory Skill is missing or unreadable, stop and report the exact path. Do not create a substitute unless the user explicitly requested rule-file creation or repair.

## Rule metadata integrity

Before editing or acceptance inspection, record for every loaded, missing, skipped, or blocked rule source:

```text
Path
Role
Required status
Read status
Blob SHA, commit SHA, checksum, or exact ref
Reason it applies
```

A bare statement such as `read the rules` is insufficient.

Every final response and PR body must include loaded rule paths and identifiers when available, plus every missing, unreadable, skipped, or blocked rule source.

## Rule precedence

Obey the user's current explicit request and all compatible loaded repository rules.

Within repository rules:

- `AGENT.md` controls project-specific constraints;
- `AGENTS.md` controls loading and routing;
- the task-routed Skill controls its workflow;
- during independent acceptance, the full-acceptance Skill controls evidence and verdict rules;
- its frontend reference controls prototype and production UI acceptance;
- stricter evidence requirements override weaker sampling or summary language.

When two rules truly require mutually exclusive actions and this precedence does not resolve them, stop and ask the user. Do not silently choose.

## Required pre-work record

Before repository changes or acceptance conclusions, establish a working record containing:

- repository, base revision, and current branch;
- exact target revision or package hash;
- loaded rules and stable identifiers;
- routed task intent and selected Skill;
- whether frontend acceptance is activated and why;
- whether prototype acceptance is activated and why;
- atomic requirement ledger;
- complete affected-file or inspected-surface map;
- files expected to change;
- checks and evidence expected;
- checks that cannot run in the environment;
- open user feedback that constrains the task.

If the working record cannot be established, stop before editing or verdict formation.

## Allowed output boundary

For repository work, generate or update only files required by the user request, `AGENT.md`, loaded Skills, or repository convention.

Allowed categories include production source, tests, migrations, configuration, workflow files, validation scripts, required documentation, PR notes, and acceptance evidence in established paths.

Unless explicitly requested or required, do not create duplicate project roots, sample applications, placeholders, noop files, unrelated demos, arbitrary reports, runtime databases, caches, compiled output, logs, secrets, or generated state.

## Documentation and evidence boundary

Documentation must follow the routed Skill and current implementation.

- Do not invent document names when a Skill or repository convention defines them.
- Do not merge distinct document purposes into a loose summary.
- Do not claim implemented or verified behaviour without matching source and evidence.
- Distinguish test definitions from executed tests, CI from local execution, screenshots from interaction traces, mocks from real evidence, and reviewer reports from generated artifacts.
- Every evidence claim must identify the inspected revision and existing paths.

## Context continuation

After compaction, model switch, long pause, continuation, or loss of working memory, do not continue from memory. Re-read:

1. `AGENTS.md`;
2. `AGENT.md`;
3. the task-routed Skill and mandatory references;
4. current branch, target revision, and changed files;
5. requirement and evidence sources.

Then rebuild the working record before editing or reporting completion.

## Final response requirements

Every final response for repository work must include:

- exact files changed or inspected;
- branch name, commit, and PR number when applicable;
- loaded rule files with identifiers when available;
- selected Skill and routing reason;
- frontend and prototype acceptance activation decisions when acceptance is involved;
- checks and evidence inspected or executed;
- checks not run and the exact reason;
- remaining defects, evidence gaps, or risks;
- a verdict only when the routed acceptance workflow permits one.

Do not describe files or artifacts under names different from their actual paths.
