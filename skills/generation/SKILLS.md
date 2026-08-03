---
name: project-generation-workflow
description: Reusable static workflow for generating, repairing, completing, packaging, and reviewing software projects from current requirements and repository evidence without embedding project-specific rules.
---

# Project Generation Workflow

## Purpose

Use this Skill to generate, repair, complete, package, or review a software project from user requirements and current repository evidence.

This is a reusable development workflow. It must not contain product-specific requirements, repository-specific conclusions, named business flows, fixed screens, fixed technologies, fixed document paths, fixed component choices, sample credentials, or assumptions copied from one project.

Project-specific facts belong in the current user request, repository rule files, source, configuration, tests, documentation, and other task-scoped evidence.

A user-provided example reveals a general capability or quality gap. It does not permanently narrow this Skill to that example, platform, framework, or artifact type.

## Skill ownership boundary

This Skill owns project generation and repair methodology.

It does not replace:

- project-specific rule files;
- platform-specific authoritative guidance loaded for the current task;
- a dedicated acceptance or review Skill;
- repository-specific build, test, release, or submission instructions.

Static self-review is part of development. A formal acceptance verdict belongs to the applicable acceptance workflow and must not be invented by this Skill.

## Reusable-content boundary

This Skill may define only reusable concerns such as:

- requirement reconstruction;
- project and surface discovery;
- source-owner mapping;
- architecture and state design;
- implementation sequencing;
- UI and interaction design methodology;
- editable prototype requirements;
- test-definition requirements;
- documentation and handoff quality;
- packaging and migration consistency;
- static consistency review;
- blocker handling and final reporting.

It must not prescribe a concrete language, framework, storage engine, operating system, device, host application, component library, icon library, file path, document name, deployment model, screen set, API, or business rule unless current task evidence establishes it.

When current authoritative platform or framework material is required, resolve it during the task. Do not encode transient platform rules as permanent Skill content.

## Absolute blocker and no-bypass rule

Any execution blocker immediately stops the blocked operation.

A blocker includes, but is not limited to:

- missing repository, file, branch, revision, package, or artifact access;
- insufficient read, write, administrative, publishing, device, account, or workspace permission;
- a connector, tool, API, policy, repository rule, or platform refusing the requested operation;
- an authentication, authorization, installation, connection, or approval requirement the agent cannot satisfy;
- a destructive or publishing action that lacks explicit user approval;
- required source that is absent, unreadable, ambiguous, or inaccessible;
- a required external system or capability that is not available;
- a conflict between controlling rules that cannot be resolved from their stated hierarchy;
- a task whose requested output cannot be produced using the available authorized capabilities.

When a blocker occurs, the agent must immediately:

1. stop the blocked operation;
2. preserve the last confirmed repository or artifact state;
3. state the exact operation that was blocked;
4. state the exact tool, path, resource, permission, policy, or approval involved;
5. state what was completed before the blocker;
6. state what was not performed;
7. give the user one or more explicit actions that would remove the blocker;
8. wait for the user to complete or authorize one of those actions before resuming the blocked operation.

The required user instruction must be concrete, for example:

- grant the named repository permission;
- connect or authorize the named service;
- upload the named missing source;
- provide the exact target path or revision;
- approve the named destructive or publishing action;
- select between two genuinely conflicting controlling rules;
- enable the specific required capability.

The agent must not:

- switch to another account, identity, repository, branch, tool, connector, API, or execution environment to evade the blocker;
- create a temporary workflow, branch, service, proxy, helper, mirror, or generated replacement to bypass access restrictions;
- infer, reconstruct, fabricate, or substitute inaccessible source;
- weaken security, policy, repository, approval, or platform requirements;
- continue with a materially different operation without explicit user instruction;
- claim success, completion, execution, compliance, or validation for the blocked work;
- ask the user to perform unrelated project work merely to compensate for an unavailable authorized capability.

Work that is independent of the blocker may continue only when it does not alter the blocked target, does not imply the blocked operation succeeded, and is explicitly separated from the blocked scope. When the blocker affects correctness, ownership, architecture, security, or required output, stop the entire task.

## Core static-generation rule

Project generation and repair under this Skill are static source-completion tasks.

The agent must complete the strongest implementation that can be derived from current requirements and repository contents without depending on an external execution result.

During generation, repair, validation, or review under this Skill, the agent must not:

- run project code;
- run unit, integration, API, browser, device, regression, or acceptance tests;
- execute repository scripts or generated binaries;
- build packages, applications, images, or containers;
- start services, databases, browsers, emulators, simulators, devices, or deployments;
- trigger, rerun, retry, dispatch, approve, cancel, or wait for CI;
- treat CI, a build, a deployment, a test run, or another external validator as a prerequisite for continuing static implementation;
- stop after a minimum patch, first defect, first stage, first commit, or first green external signal;
- defer statically identifiable work to a later pass, future PR, or external validation step.

Existing logs, reports, screenshots, artifacts, or CI results may be inspected read-only when already available. They are optional context, not generation dependencies.

Missing runtime evidence does not block static completion. Missing required source or permission is a blocker and must follow the no-bypass rule.

## Required pre-work record

Before editing, establish a working record containing:

- target repository or package;
- base revision and working branch;
- loaded rule sources and stable identifiers;
- original requirement source;
- user corrections and non-goals;
- project and surface classifications;
- atomic requirement ledger;
- affected existing files and owners;
- files proposed for creation, normally none;
- exact ownership justification for each proposed new file;
- authorized operations;
- prohibited or unavailable operations;
- expected static checks;
- known blockers.

If this record cannot be established, stop before editing and apply the no-bypass rule.

## Complete-delivery rule

Scope is determined by the complete requirement and repository constraints, not by minimizing files, edits, decisions, or effort.

Before delivery:

1. reconstruct the request into atomic requirements;
2. classify the project and every user-facing or machine-facing surface;
3. inspect every repository area materially affected;
4. locate all production, schema, configuration, API, UI, test, documentation, packaging, migration, and deployment owners expressing the same behavior;
5. resolve every statically identifiable contradiction, omission, unsafe fallback, incomplete state, stale path, disconnected artifact, or documentation mismatch within scope;
6. update all affected owners together;
7. rescan the complete affected surface;
8. continue after finding an ordinary implementation defect so all independent defects are recorded;
9. stop immediately when the issue is an execution blocker covered by the no-bypass rule.

A narrow change is correct only when the requirement itself is narrow.

## Required task inputs

Resolve these values from the current conversation and repository:

- original requirement source;
- target repository or package;
- user goal: generate, repair, extend, package, review, or document;
- requested deliverable and artifact format;
- project type and surface types;
- target runtime, platform, host, device, shell, or execution environment;
- language, framework, package, toolchain, and version evidence;
- design-system and interaction evidence when applicable;
- repository rules and ownership conventions;
- compatibility, security, deployment, accessibility, and submission constraints;
- user corrections and explicit non-goals;
- publication or destructive-action intent.

Do not invent a value that materially affects architecture, compatibility, security, interaction, persistence, or deliverable format.

## Project and surface classification

Classify the project by current evidence rather than assumption.

Possible surface classes include:

- service or backend process;
- browser-delivered interface;
- native application interface;
- desktop application;
- command-line or terminal interface;
- reusable library or SDK;
- plugin, extension, or host-embedded interface;
- data-processing or model workflow;
- infrastructure or deployment project;
- firmware or embedded runtime;
- documentation-only artifact;
- design-only or implementation-guiding prototype;
- multi-surface product.

These are discovery categories, not fixed implementation prescriptions.

For every detected surface, record:

- intended user or caller;
- entry point;
- lifecycle;
- state owner;
- data owner;
- permissions;
- dependencies;
- output or visible result;
- failure and recovery path;
- implementation owner;
- test-definition owner;
- documentation owner.

Do not let one surface erase another. A repository containing multiple languages, runtimes, interfaces, or deployment layers must be mapped by role.

## Atomic requirement ledger

Convert the request into a traceable ledger.

Use this shape:

```text
ID | Requirement | Surface | Source owner | State/data owner | Interaction or contract path | Test/static path | Documentation owner | Status | Gap
```

Include every applicable concern:

- architecture and module boundaries;
- persistence and state transitions;
- API, event, command, or library contracts;
- authentication, authorization, privacy, and security;
- configuration and secrets;
- observability and failure handling;
- deployment, packaging, installation, upgrade, and rollback;
- user experience and interaction behavior;
- accessibility and adaptive behavior;
- documentation and developer handoff;
- positive, negative, boundary, conflict, recovery, and destructive paths;
- repository hygiene and maintainability.

A requirement is incomplete when only its route, type, mock, screenshot, prose, or happy path exists.

## Existing-owner and file-creation rule

Updating an existing owner is the default.

Before creating a file, establish:

- the exact path;
- the requirement that needs it;
- why no existing file can own the content;
- the long-term owner;
- the repository convention supporting it;
- whether an equivalent artifact already exists.

Do not create parallel projects, replacement rule files, duplicate documentation, arbitrary reports, sample applications, placeholder files, alternate prototypes, or competing implementations merely because they are easier to generate.

A requested report or prototype does not automatically authorize adding it to the repository. Use the requested artifact channel or an established repository owner.

## Architecture generation contract

Resolve implementation decisions from task evidence:

- process and module boundaries;
- dependency direction;
- state ownership;
- synchronous and asynchronous flows;
- persistence model;
- transaction or consistency boundaries;
- concurrency and re-entrancy behavior;
- error propagation;
- configuration ownership;
- secret handling;
- logging and observability;
- startup, shutdown, upgrade, migration, and rollback;
- packaging and deployment ownership;
- external dependency and offline assumptions;
- platform-specific lifecycle obligations.

Do not replace repository architecture with a preferred architecture unless the user explicitly requests a migration.

## Data, API, command, and library contract

When applicable, define and implement:

- entities, identifiers, constraints, indexes, versions, and source-of-truth fields;
- request, response, event, command, callback, and library interfaces;
- validation rules and boundaries;
- error types and recovery guidance;
- pagination, ordering, filtering, idempotency, and replay behavior;
- authentication and authorization boundaries;
- compatibility and migration behavior;
- serialization and storage rules;
- transactional side effects;
- generated-contract ownership;
- positive, negative, boundary, and failure-path test definitions.

All consumers and producers must agree statically.

## User-interface design and implementation contract

Apply this section whenever the requested scope contains a production interface, host-embedded interface, native interface, browser interface, desktop interface, interactive terminal surface, or implementation-guiding prototype.

A usable result must allow implementation without forcing another engineer to redesign material visual or interaction decisions.

### Separate environment-owned and product-owned UI

For every surface, distinguish:

- environment, operating-system, browser, device, terminal, or host-owned chrome;
- system dialogs, permissions, input surfaces, safe areas, bars, menus, window controls, and other environment-owned behavior;
- product-owned navigation, content, overlays, controls, and state;
- embedded host navigation and plugin-owned content;
- viewport or window behavior versus content layout;
- system appearance settings versus product theme choices.

Do not draw, implement, or document environment-owned content as though the product owns it. Do not omit environment constraints that materially affect product layout or interaction.

### Discover platform semantics at task time

Determine from current evidence:

- target platform, host, device, form factor, and supported versions;
- native, browser, embedded, hybrid, remote-rendered, or terminal ownership;
- application lifecycle and navigation owner;
- framework and component system;
- design tokens and icon source;
- theme and appearance modes;
- input methods;
- viewport, window, safe-area, keyboard, pointer, touch, focus, orientation, and resizing constraints;
- accessibility model;
- platform review, marketplace, privacy, or submission obligations;
- existing screens, prototypes, components, stories, design files, screenshots, and interaction conventions.

Do not substitute one surface's conventions for another. Do not claim compliance from visual resemblance.

### Information architecture and navigation

For every material flow, define:

- user goal;
- screen, view, panel, route, window, command, or host location;
- entry and exit paths;
- global and local navigation placement;
- deep-link, refresh, restore, back, and resume behavior;
- permission visibility;
- empty and first-use paths;
- interruption and continuation behavior;
- cross-surface handoff where applicable.

Produce a surface map that distinguishes destinations, nested content, transient overlays, system-owned surfaces, and state variants.

### Design-system extraction or creation

Before inventing values, inspect existing design-system evidence and derive:

- typography roles;
- spacing scale;
- color and semantic-color roles;
- borders, radii, elevation, density, and separators;
- component variants;
- icon source and naming;
- theme behavior;
- motion conventions;
- adaptive layout rules.

When no design system exists and design creation is in scope, define the smallest coherent reusable system needed by the product. Do not generate an ornamental token catalog detached from implementation.

Every token or component rule must have an owner and at least one concrete use.

### Component and screen specification

For every material screen or interactive region, resolve:

- purpose and data source;
- component hierarchy;
- reusable boundaries;
- inputs, outputs, events, and state ownership;
- exact component choice from current repository or platform evidence;
- exact icon source and icon identity where icons are used;
- visual icon size, container size, hit target, alignment, state, label, and tooltip behavior;
- dimensions and constraints;
- spacing, typography, color, border, radius, elevation, and density values;
- scrolling, sticky, truncation, wrapping, overflow, zoom, and long-content behavior;
- adaptive and responsive behavior;
- content and localization constraints;
- default, hover, focus, pressed, selected, disabled, loading, empty, success, validation-error, request-error, permission-denied, conflict, stale, destructive, offline, and read-only states where applicable;
- user-visible labels, validation messages, confirmations, errors, and recovery guidance;
- keyboard order, focus placement and return, accessible names, announcements, and non-pointer operation;
- motion trigger, duration, easing source, completion state, interruption, and reduced-motion behavior when motion is required.

Do not use unresolved phrases such as `appropriate icon`, `standard spacing`, `normal modal`, `reasonable size`, `similar`, or `handle errors`.

### Interaction state-machine contract

Every non-trivial interaction must define a state machine rather than only a final picture.

Record:

```text
State | Entry condition | Visible UI | Available actions | Data mutation | Exit condition | Error/recovery | Focus/input behavior
```

For gestures, drag-and-drop, drawing, selection, document manipulation, reordering, inline editing, multi-step forms, command interfaces, virtualized data, media, or other special interactions, define:

- supported input methods;
- activation threshold and start condition;
- active-state feedback;
- coordinate system, snapping, bounds, scrolling, zoom, and selection behavior;
- commit condition and persisted result;
- cancel, escape, pointer-cancel, lost-focus, interruption, and route-change behavior;
- undo, redo, delete, reset, and recovery;
- duplicate-submit and re-entrancy prevention;
- optimistic or pessimistic update choice;
- partial failure, network failure, stale version, conflict, permission loss, and retry behavior;
- keyboard-only and assistive-technology path;
- source state and domain mutation affected.

A static image is not an interaction specification.

### Editable prototype contract

When the user requests a prototype, deliver it in the requested or repository-native editable format.

A valid implementation-guiding prototype must:

- contain reusable components rather than flattened screenshots;
- separate system-owned, host-owned, and product-owned regions;
- include all material destinations and overlays;
- connect navigation and action transitions;
- model loading, empty, validation, failure, conflict, permission, destructive, and recovery states;
- use reusable tokens or styles;
- preserve component names and hierarchy that can map to implementation;
- include annotations or linked specifications for dimensions and state behavior that cannot be encoded directly;
- avoid embedding credentials or private data;
- remain editable and stable for later iteration;
- avoid requiring a developer to infer behavior from image pixels.

A screenshot, mood board, image-only mock, prose-only handoff, or disconnected collection of frames is not a completed interactive prototype.

### Implementation and prototype consistency

When code delivery is in scope, the prototype, source, styles, components, routes, data contracts, permissions, and tests must agree.

Do not stop at a prototype when the user asked for implementation. Do not replace design work with code that leaves material design decisions unresolved.

Use this traceability table:

```text
Requirement | Surface/location | Component | Visual rule | Interaction/state path | Data/API dependency | Permission | Source path | Test/static path
```

## Documentation and reusable development-standard contract

Documentation must be stable project source, not a transcript of the agent's work.

Update the existing documentation owner before creating another file.

For every material implementation area, document the applicable parts:

- scope and non-goals;
- architecture and ownership boundaries;
- state and data flow;
- public contracts;
- configuration and security boundaries;
- component and design-system rules;
- navigation and interaction state machines;
- environment-owned versus product-owned UI;
- accessibility and adaptive behavior;
- error, conflict, recovery, and destructive-action behavior;
- test assertions and static evidence paths;
- packaging, installation, upgrade, migration, and rollback;
- extension and change rules;
- long-term owner and update conditions.

A development standard is reusable only when it defines decisions, ownership, invariants, examples derived from the current project, and concrete acceptance assertions. It must not merely describe visual intent.

Do not create fixed default documentation paths in this Skill. Resolve documentation ownership from the current repository or explicit user request.

Do not place task chronology, tool failures, branch history, assistant corrections, temporary checklists, or unowned future work in permanent project documentation.

## Tests and static evidence contract

For every changed behavior, add or update test definitions in the existing test layout when tests are in scope.

Cover applicable:

- positive paths;
- denial and authorization paths;
- invalid input;
- exact boundaries;
- duplicate and re-entrant actions;
- state transitions;
- terminal states;
- loading, empty, error, conflict, retry, and recovery;
- persistence and migration behavior;
- accessibility and focus behavior;
- adaptive layout and overflow;
- interaction cancellation and interruption;
- platform- or host-specific obligations;
- documentation and generated-contract consistency.

A test name, fixture, type, or placeholder is not evidence unless its assertions cover the required result and side effects.

Do not claim execution. Static completion means the implementation and test definitions are present and consistent.

## Configuration, packaging, deployment, and migration contract

Trace each required value and artifact through all applicable owners:

- application configuration;
- environment or installation configuration;
- package manifests and lock ownership;
- build and generated-source ownership;
- image, bundle, archive, installer, or release configuration;
- service, process, device, host, or deployment manifests;
- migration and rollback definitions;
- startup and shutdown behavior;
- persistent state and upgrade compatibility;
- secrets and permissions;
- offline and external-dependency assumptions;
- documentation and test definitions.

Reject disconnected configuration, undocumented fallbacks, fixed machine identity, unowned generated output, or migration claims without implementation.

## Security, privacy, and safety contract

Map security and privacy requirements across:

- trust boundaries;
- authentication and authorization;
- object and field visibility;
- secret and credential handling;
- local and remote storage;
- transport and inter-process communication;
- logging, analytics, telemetry, and diagnostics;
- user consent and system permissions;
- destructive operations;
- import, export, backup, and recovery;
- dependency and update behavior;
- UI masking and copy;
- tests and documentation.

Do not rely on UI hiding as authorization. Do not invent security claims unsupported by implementation.

## Logging and observability contract

Use the repository's existing observability model.

When applicable, cover:

- startup and shutdown;
- request or operation identity;
- actor and resource context;
- state transitions;
- authorization denial;
- validation failure;
- dependency and persistence failure;
- background work;
- retries and recovery;
- duration and outcome;
- privacy and redaction.

Do not log credentials, secrets, protected content, complete sensitive payloads, or private environment values.

## Repository hygiene rules

When a repository is involved:

- treat the resolved repository root as the only project root;
- preserve existing language, architecture, design, package, and test conventions;
- do not create parallel projects, sample applications, placeholder files, noop files, duplicate roots, or unrelated outputs;
- keep source in established owners;
- exclude runtime databases, caches, build output, logs, temporary files, secrets, generated reports, and unrelated artifacts;
- inspect paths for portability, case-only collisions, accidental spaces, control characters, locale dependence, and ambiguous near-duplicates;
- preserve exact existing paths unless a rename is explicitly required;
- do not create replacement rule files or invent rule paths.

## Static development workflow

For repository changes:

1. load controlling rules and current requirements;
2. resolve target, base revision, branch, permissions, and allowed actions;
3. stop immediately on any blocker and follow the no-bypass rule;
4. classify project and surfaces;
5. build the atomic requirement ledger;
6. map every requirement to all affected existing owners;
7. justify every proposed new file;
8. implement the complete mapped surface;
9. add or update positive, negative, boundary, failure, interaction, accessibility, and recovery test definitions;
10. update configuration, schemas, migrations, packaging, UI assets, comments, and documentation consistently;
11. inspect the complete changed source statically;
12. review the complete diff for unrelated changes and unresolved rows;
13. repeat until every in-scope row is statically complete, blocked, or explicitly unresolved;
14. report without waiting for external execution.

Do not create artificial stages whose purpose is to postpone known work.

## Submission rules

When publication is explicitly requested and authorized:

- use the existing repository workflow;
- keep the branch and change set purpose-specific;
- exclude unrelated cleanup and generated state;
- do not merge, force-update, delete, release, publish, or perform another destructive action without explicit approval;
- stop immediately when permission, policy, review, or approval blocks publication;
- give the exact action required from the user;
- do not bypass the blocker through another account, branch, tool, workflow, or repository.

## Static evidence model

Use this order for implementation decisions:

1. original requirement and explicit user corrections;
2. controlling repository and workflow rules;
3. current production source, schema, configuration, manifests, UI assets, and public contracts;
4. current test definitions and static guards;
5. current documentation and comments;
6. pre-existing external artifacts, read-only and optional;
7. summaries and claims.

A missing external result does not demote a complete static implementation. A green external result does not excuse a static contradiction.

## Completion criteria

Before delivery, answer from current source and artifacts:

1. Is every atomic requirement mapped to an implementation owner?
2. Do all affected source, schema, configuration, API, UI, packaging, test, and documentation owners agree?
3. Can a maintainer extend the implementation without reverse-engineering unstated architecture or interaction decisions?
4. Can an engineer implement every required UI flow without redesigning material components, states, navigation, or platform behavior?
5. Is every requested prototype editable, connected, reusable, and state-complete?
6. Are environment-owned and product-owned surfaces correctly separated?
7. Are positive, negative, boundary, failure, conflict, destructive, and recovery paths defined?
8. Are accessibility, adaptive behavior, permissions, and security boundaries explicit where applicable?
9. Are new files necessary, owned, and repository-conventional?
10. Were all blockers handled by stopping and giving explicit instructions rather than bypassing?

If any required answer is no, the task is not complete.

## Final response contract

The final response must include:

- target repository or package and exact base revision;
- working branch when repository changes were made;
- exact existing files changed;
- exact files created, normally none, with justification;
- loaded rule paths and identifiers;
- complete requirement summary;
- repository reads and writes actually performed;
- external execution performed: `none` under this Skill;
- CI triggered or awaited: `none`;
- blockers encountered and exact user actions requested;
- remaining static defects, unresolved requirements, inaccessible sources, or risks.

Do not claim formal acceptance unless the applicable acceptance workflow was explicitly requested and loaded.
