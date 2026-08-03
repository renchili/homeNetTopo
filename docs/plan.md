# HomeNetTopo Implementation Plan

## Status and ownership

This document is the implementation plan for the first runnable HomeNetTopo release.

- Status: `PLANNED`
- Long-term owner: `docs/plan.md`
- Product and architecture authority: `AGENT.md`, `docs/design.md`, `docs/api-spec.md`, and `docs/questions.md`
- Update condition: change this plan whenever implementation ownership, public behavior, release scope, or completion criteria change

This plan is not runtime evidence and does not assert that listed files or behavior already exist.

## Release outcome

The first runnable release must let a macOS user start a loopback-only Python service, open a local web page, inspect a passive logical topology, explicitly request bounded private-IPv4 host discovery when Nmap is available, inspect evidence and confidence, and export the current snapshot as JSON.

The release must remain useful without Nmap, cloud services, accounts, telemetry, persisted inventories, external frontend assets, or administrator privileges in the normal passive path.

## Controlling product defaults

The following decisions are fixed for the first release unless the controlling documents are updated together:

- macOS is the supported host platform.
- Python 3 standard library is the default backend dependency posture.
- The service binds to `127.0.0.1` on port `8765` by default.
- Page load performs passive collection only.
- Active discovery requires an explicit user action.
- Active discovery uses Nmap host-discovery mode only.
- Active targets must be eligible locally visible private IPv4 networks.
- The combined active target limit is 1024 addresses per request.
- Tunnel networks are visible passively but are not automatically active-discovery targets.
- Topology data remains in process memory unless the user exports JSON.
- Observed facts and inferred relationships are distinct in the API and UI.
- The UI must state that it is a best-effort logical view, not a proven physical topology.

## Planned repository ownership

```text
.gitignore
server.py
homenettopo/
  __init__.py
  commands.py
  discovery.py
  interfaces.py
  models.py
  neighbors.py
  routes.py
  topology.py
web/
  index.html
  app.js
  styles.css
tests/
  __init__.py
  test_commands.py
  test_discovery.py
  test_interfaces.py
  test_models.py
  test_neighbors.py
  test_routes.py
  test_server.py
  test_static_security.py
  test_topology.py
  test_web_contract.py
fixtures/
  macos/
    arp_all.txt
    arp_incomplete.txt
    ifconfig_multi_interface.txt
    ifconfig_utun_point_to_point.txt
    nmap_host_discovery.txt
    route_default.txt
    route_specific.txt
README.md
docs/
  api-spec.md
  design.md
  plan.md
  questions.md
metadata.json
```

No nested application root, generated scan output, runtime inventory, real network identifier, package cache, or compiled artifact belongs in source control.

## Atomic requirement ledger

Status vocabulary for this plan:

- `PLANNED`: required and mapped, but source is not yet present.
- `BLOCKED`: cannot be implemented without a missing controlling decision or permission.
- `DONE`: source, test definitions, and documentation are statically consistent. This does not mean runtime acceptance passed.

| ID | Requirement | Surface | Primary owner | Test/static owner | Documentation owner | Status |
|---|---|---|---|---|---|---|
| HT-001 | Start on macOS with Python 3 and bind to loopback by default | Service | `server.py` | `tests/test_server.py` | `README.md` | PLANNED |
| HT-002 | Reject unsupported platforms with a structured error | API | `server.py` | `tests/test_server.py` | `docs/api-spec.md` | PLANNED |
| HT-003 | Execute only approved commands through argument arrays with timeouts and bounded output | Backend | `homenettopo/commands.py` | `tests/test_commands.py` | `docs/design.md` | PLANNED |
| HT-004 | Parse macOS interfaces, IPv4 addresses, prefixes, flags, and tunnel formats | Passive discovery | `homenettopo/interfaces.py` | `tests/test_interfaces.py` and `fixtures/macos/ifconfig_*` | `docs/design.md` | PLANNED |
| HT-005 | Parse default and route-specific gateway evidence | Passive discovery | `homenettopo/routes.py` | `tests/test_routes.py` and route fixtures | `docs/design.md` | PLANNED |
| HT-006 | Parse complete and incomplete ARP entries without fabricating devices | Passive discovery | `homenettopo/neighbors.py` | `tests/test_neighbors.py` and ARP fixtures | `docs/design.md` | PLANNED |
| HT-007 | Produce usable partial snapshots when one passive source fails coherently | Backend/API | `server.py`, discovery modules, `homenettopo/topology.py` | parser and server tests | `docs/api-spec.md` | PLANNED |
| HT-008 | Keep passive collection separate from active discovery | API/UI | `server.py`, `web/app.js` | `tests/test_server.py`, `tests/test_web_contract.py` | `docs/api-spec.md` | PLANNED |
| HT-009 | Validate active targets as eligible private IPv4 networks and enforce the 1024-address combined limit | Active discovery | `homenettopo/discovery.py` | `tests/test_discovery.py` | `docs/design.md`, `docs/api-spec.md` | PLANNED |
| HT-010 | Invoke only approved Nmap host discovery and normalize missing-tool, timeout, and command failures | Active discovery | `homenettopo/discovery.py`, `homenettopo/commands.py` | `tests/test_discovery.py`, `tests/test_commands.py` | `docs/api-spec.md`, `README.md` | PLANNED |
| HT-011 | Build stable nodes, edges, evidence, warnings, confidence, and snapshot metadata | Topology | `homenettopo/models.py`, `homenettopo/topology.py` | `tests/test_models.py`, `tests/test_topology.py` | `docs/design.md`, `docs/api-spec.md` | PLANNED |
| HT-012 | Merge duplicate observations conservatively and retain conflicts as warnings | Topology | `homenettopo/topology.py` | `tests/test_topology.py` | `docs/design.md` | PLANNED |
| HT-013 | Implement health, capabilities, passive topology, active discovery, and JSON export endpoints | API | `server.py` | `tests/test_server.py` | `docs/api-spec.md` | PLANNED |
| HT-014 | Enforce methods, JSON content type, body limits, structured errors, and no raw command leakage | API | `server.py` | `tests/test_server.py` | `docs/api-spec.md` | PLANNED |
| HT-015 | Serve repository-owned static assets without traversal, directory listing, CDN, or permissive cross-origin behavior | Web delivery | `server.py`, `web/` | `tests/test_static_security.py`, `tests/test_web_contract.py` | `docs/design.md` | PLANNED |
| HT-016 | Render an interactive SVG topology with pan, zoom, fit, selection, details, evidence, and confidence | Browser UI | `web/index.html`, `web/app.js`, `web/styles.css` | `tests/test_web_contract.py`; later browser evidence | `docs/design.md` | PLANNED |
| HT-017 | Provide loading, empty, partial, error, missing-Nmap, validation, timeout, and unsupported-platform states | Browser UI | `web/app.js`, `web/index.html` | `tests/test_web_contract.py`; later browser evidence | `docs/design.md` | PLANNED |
| HT-018 | Make controls and graph selections keyboard reachable with visible focus and reduced-motion behavior | Browser UI | `web/index.html`, `web/app.js`, `web/styles.css` | `tests/test_web_contract.py`; later browser evidence | `docs/design.md` | PLANNED |
| HT-019 | Export the latest in-memory snapshot without server-side persistence or upload | API/UI | `server.py`, `web/app.js` | `tests/test_server.py`, `tests/test_web_contract.py` | `docs/api-spec.md`, `README.md` | PLANNED |
| HT-020 | Keep real local identifiers, logs, caches, and runtime exports out of source control | Repository/privacy | `.gitignore`, all modules | repository inspection | `AGENT.md`, `README.md` | PLANNED |
| HT-021 | Supply deterministic synthetic fixtures and positive, negative, boundary, and recovery tests | Tests | `tests/`, `fixtures/` | test suite definitions | `README.md` | PLANNED |
| HT-022 | Document exact startup, optional Nmap setup, limitations, and verification only after matching source exists | Operator docs | `README.md` | documentation consistency inspection | `README.md` | PLANNED |

No requirement is currently blocked. Open questions Q-101 through Q-105 use the safe behaviors recorded in `docs/questions.md`.

## Implementation sequence

The work packages below are dependency ordered. A package is complete only when its source, tests, and affected documentation are updated together. Known requirements must not be deferred merely to obtain an earlier runnable demo.

### Package 1: repository foundation and stable data model

Create:

- `.gitignore` with macOS, Python, environment, cache, log, runtime export, and local inventory exclusions;
- `homenettopo/__init__.py` with the package version;
- `homenettopo/models.py` with JSON-serializable structures for evidence, source status, network eligibility, nodes, edges, warnings, active-discovery metadata, and snapshots;
- initial synthetic fixtures and test package structure.

Data-model decisions:

- use standard-library `dataclasses`, `enum`, `ipaddress`, and `datetime` where appropriate;
- emit RFC 3339 UTC timestamps;
- keep snapshot identifiers unique per collection;
- keep node and edge identifiers deterministic inside a snapshot;
- validate confidence and kind values before serialization;
- exclude `None` fields only when the API contract permits omission;
- keep schema version independent from application version.

Completion gate:

- all public JSON fields in `docs/api-spec.md` have one source owner;
- model tests cover valid serialization and invalid enum, identifier, and endpoint references;
- fixtures contain only clearly synthetic addresses, names, and locally administered MAC values.

### Package 2: approved command runner and passive macOS collectors

Implement `homenettopo/commands.py`:

- allow only caller-provided argument arrays;
- disable shell execution;
- apply per-command timeout and maximum captured output;
- decode output predictably;
- normalize missing executable, non-zero exit, timeout, and malformed output cases;
- retain diagnostic context for local logging without exposing arbitrary command output through the API.

Implement passive parsers:

- `interfaces.py`: parse interface blocks, flags, IPv4 addresses, netmasks or prefixes, point-to-point peers, and `utun` output;
- `routes.py`: parse default route and route-specific gateway/interface evidence;
- `neighbors.py`: parse ARP entries, incomplete entries, interface association, MAC normalization, and duplicate lines.

Completion gate:

- every parser is a pure function over fixture text where practical;
- command invocation and parsing are separable;
- incomplete or unknown lines produce warnings rather than fabricated facts;
- tests cover ordinary Wi-Fi/Ethernet, multiple addresses, tunnel interfaces, missing gateway, incomplete ARP, malformed lines, command timeout, and output limit behavior.

### Package 3: active-discovery validator and Nmap adapter

Implement `homenettopo/discovery.py` in two layers:

1. pure target validation and eligibility calculation;
2. optional Nmap adapter using the approved command runner.

Validation order:

1. parse each target as an IPv4 network;
2. reject loopback, link-local, multicast, unspecified, public, and malformed targets;
3. require overlap with an eligible private network assigned to a local interface;
4. reject automatically selected tunnel targets;
5. calculate the combined unique address count;
6. reject requests above the configured limit;
7. validate bounded timeout values;
8. construct the final Nmap argument array only from validated values.

The Nmap adapter must use host-discovery-only arguments and parse host-up evidence without introducing port or service data into the model.

Completion gate:

- tests cover exact address-limit boundaries, overlapping target deduplication, public and special ranges, unrelated private ranges, tunnel eligibility, invalid timeout, missing Nmap, command timeout, malformed output, and approved argument construction;
- no HTTP request path can bypass the validator.

### Package 4: topology construction and provenance

Implement `homenettopo/topology.py` as a deterministic transformation from normalized evidence to a snapshot.

Construction order:

1. create the local-host node;
2. create interface nodes and host-to-interface edges;
3. create subnet nodes and interface-to-subnet edges;
4. create gateway nodes from route evidence;
5. create neighbor/device nodes from passive and optional active evidence;
6. attach devices to subnets through explicit address-membership inference;
7. create upstream boundary nodes where routes leave locally visible networks;
8. merge compatible observations;
9. retain conflicts and partial-source failures as warnings;
10. calculate confidence from evidence type and corroboration.

Required invariants:

- every edge endpoint exists;
- inferred membership never becomes an observed physical link;
- a gateway can also be a discovered device without duplicate identity when evidence supports merging;
- conflicting MAC or hostname data remains inspectable;
- active evidence supplements rather than erases passive evidence;
- sorting is deterministic for reproducible tests and exports.

Completion gate:

- topology tests cover no-neighbor, multi-interface, multiple subnet, gateway merge, active/passive merge, conflicting evidence, partial-source, tunnel, and deterministic ordering cases;
- every confidence value has an evidence-based rule documented in code and design documentation.

### Package 5: loopback HTTP service and static-file boundary

Implement `server.py` with the Python standard library.

Responsibilities:

- parse startup options with safe defaults;
- refuse non-macOS collection while keeping health behavior coherent with the API contract;
- bind to loopback by default;
- route only documented API and static paths;
- keep a latest in-memory snapshot behind a concurrency-safe owner;
- collect passive snapshots without invoking Nmap;
- invoke active discovery only through `POST /api/v1/discover`;
- enforce method, content type, body size, timeout, and target validation;
- emit the documented error envelope and response headers;
- prevent decoded traversal, parent traversal, symlink escape, directory listing, and serving outside `web/`;
- shut down cleanly on normal process interruption.

Initial endpoint behavior:

| Endpoint | Collection behavior | Snapshot behavior |
|---|---|---|
| `GET /api/v1/health` | none | none |
| `GET /api/v1/capabilities` | dependency/platform checks only | none |
| `GET /api/v1/topology` | passive only | replace latest snapshot |
| `POST /api/v1/discover` | passive refresh plus validated active discovery | replace latest snapshot |
| `GET /api/v1/topology/export` | none when a snapshot exists | download latest; return documented `404` when absent |

The export endpoint will use `404` when no snapshot exists. This avoids an export action unexpectedly collecting data; `docs/api-spec.md` must be updated from its current either/or wording during implementation.

Completion gate:

- API tests cover all documented success and failure status codes;
- passive topology tests prove Nmap is not called;
- active tests prove validation occurs before process invocation;
- static-file tests cover raw and encoded traversal, symlink escape, missing assets, unsupported methods, MIME types, no directory listing, and required headers;
- concurrent requests cannot corrupt the latest snapshot.

### Package 6: local browser interface

Implement a single-page interface with no external assets.

Page structure:

```text
header
  product title
  collection timestamp and mode
  passive refresh button
  active discovery button
  export JSON button
status region
  capability, partial-result, warning, and limitation messages
main
  SVG topology canvas
  details aside for selected node or edge
active discovery dialog
  eligible network checkboxes
  address-count summary
  timeout input
  explicit confirmation and cancel actions
```

Responsive behavior:

- desktop: graph and a fixed-width details column;
- narrow viewport: graph above details, with controls wrapping without horizontal page overflow;
- graph remains zoomable independently from page scrolling;
- dialogs and panels remain usable at browser zoom up to 200 percent.

Graph behavior:

- initial render fits all nodes with bounded padding;
- background pointer drag pans;
- wheel or trackpad input zooms around the pointer with min/max limits;
- dedicated zoom-in, zoom-out, fit, and reset buttons provide non-gesture alternatives;
- nodes are SVG focus targets with accessible names;
- Enter or Space selects a focused node or edge;
- Escape clears selection or closes the active dialog;
- selected items remain visually distinct without relying on color alone;
- observed edges use a solid treatment and inferred edges use a dashed treatment plus text in details;
- reduced-motion preference disables nonessential transitions.

UI state machine:

| State | Entry condition | Visible result | Available actions | Focus and recovery |
|---|---|---|---|---|
| `BOOT` | page script starts | shell and loading message | none | status region receives announced update |
| `LOADING_PASSIVE` | initial load or refresh | existing graph dimmed or loading placeholder | cancel is not offered for short passive collection | focus stays on triggering control |
| `PASSIVE_READY` | complete passive response | graph, timestamp, passive mode | refresh, active discovery, export, select | focus returns to trigger after update |
| `PARTIAL_READY` | response has warnings or `partial=true` | graph plus prominent warnings | same as ready; inspect warning details | warning summary is announced |
| `EMPTY_READY` | valid snapshot with no neighbor devices | local host, interfaces, subnets, explanation | refresh, active discovery when eligible, export | empty-state heading is focusable |
| `ACTIVE_CONFIRM` | active button selected | eligible networks and address total | confirm or cancel | focus moves into dialog and returns on close |
| `ACTIVE_RUNNING` | confirmed active request | progress state; prior graph retained but marked stale | no duplicate submit; cancel dialog action disabled after request dispatch | progress announced once |
| `ACTIVE_READY` | active response succeeds | merged graph and active metadata | refresh, rediscover, export, select | focus returns to active trigger |
| `DEPENDENCY_UNAVAILABLE` | Nmap unavailable | passive graph plus install guidance | passive refresh, export | active control remains disabled with explanation |
| `VALIDATION_ERROR` | active request rejected | field and summary errors | edit request or cancel | focus moves to error summary, then invalid field |
| `REQUEST_ERROR` | API, timeout, or parse failure | prior usable graph retained when available | retry, passive refresh, inspect details | error summary announced; retry is focused only on explicit user action |
| `UNSUPPORTED_PLATFORM` | platform error | explanatory non-graph state | health/details only | main heading receives focus |

Completion gate:

- no required asset or request leaves the loopback origin;
- UI copy distinguishes logical inference from physical certainty;
- all controls have programmatic names, visible focus, disabled reasons, and keyboard operation;
- long labels, IPv4 lists, warnings, and evidence entries wrap or scroll within their owner;
- static frontend tests verify no external asset URLs, documented element IDs/data hooks, CSP-compatible script/style ownership, accessibility attributes, and representative state templates;
- real browser interaction remains a separately reported acceptance requirement.

### Package 7: operator documentation and release hygiene

Update `README.md`, `metadata.json`, `docs/design.md`, `docs/api-spec.md`, and `docs/questions.md` to match the exact implementation.

Required README content after source exists:

- supported macOS and Python assumptions;
- exact startup command and options;
- loopback URL;
- optional Nmap installation and missing-Nmap behavior;
- passive versus active behavior;
- active target and address limits;
- JSON export behavior;
- privacy and non-persistence behavior;
- topology inference limitations;
- exact automated test command when the test suite exists;
- manual browser and real-network checks clearly labeled as manual evidence.

Repository hygiene completion gate:

- no real local addresses, hostnames, MAC addresses, logs, exports, caches, or build output are committed;
- scripts and commands are repository-relative and macOS-compatible;
- documentation contains no implementation claim without a matching path;
- `metadata.json.status` changes from `bootstrap` only when runnable source exists;
- no CI, browser, runtime, or release claim appears without exact-revision evidence.

## API implementation matrix

| Contract area | Source owner | Required tests |
|---|---|---|
| Error envelope and request IDs | `server.py` | malformed JSON, wrong content type, method mismatch, internal normalization |
| Health | `server.py` | success without collection; platform field behavior |
| Capabilities | `server.py`, `homenettopo/discovery.py` | Nmap present/absent; limit and bind reporting |
| Passive topology | all passive collectors, `topology.py`, `server.py` | success, partial source failure, unsupported platform, no active invocation |
| Active discovery | `discovery.py`, `topology.py`, `server.py` | valid request, all validation failures, dependency absence, timeout, normalized command failure |
| Export | `server.py` | latest snapshot download, `404` without snapshot, headers, no new collection |
| Node and edge schemas | `models.py`, `topology.py` | exact required fields, valid references, confidence and evidence |
| Security headers | `server.py` | API and static responses; CSP matches asset model |

## Test strategy

The automated suite must be deterministic and must not discover the test machine's actual network.

### Unit and fixture tests

- pure parser tests over sanitized macOS command output;
- pure network eligibility and address-count tests;
- command argument and error-normalization tests using mocked subprocess boundaries;
- topology construction tests from normalized evidence;
- model serialization and invariant tests.

### Local service tests

Use an in-process or ephemeral-port server with injected collectors and command adapters. Do not invoke the real local network or Nmap in the automated suite.

Cover:

- endpoints, methods, media types, status codes, response shapes, headers, and body limits;
- passive and active operation separation;
- in-memory snapshot replacement and export;
- partial results and normalized errors;
- static asset MIME types and path containment;
- concurrency and duplicate active request behavior.

### Frontend static contract tests

Without adding a mandatory frontend toolchain, verify:

- required local assets exist;
- HTML references only repository-owned assets;
- no inline script or style violates the planned CSP;
- expected controls, status regions, dialog, graph, and details owners exist;
- keyboard and accessibility hooks are present;
- UI state names and error-code mappings remain aligned with the API contract.

### Separate acceptance evidence

The implementation plan defines but does not execute these later checks:

- start the service on a supported Mac;
- inspect health, capabilities, passive topology, and export;
- verify Nmap-unavailable behavior;
- run an authorized bounded discovery against an eligible local test network;
- interact with graph pan, zoom, fit, selection, keyboard controls, dialog focus, error recovery, and 200-percent browser zoom;
- inspect behavior with Wi-Fi/Ethernet, tunnel interfaces, empty ARP cache, and partial command failure where environments are available.

Formal acceptance, readiness, or `PASS` requires the repository acceptance workflow and exact-revision evidence; it is outside this generation plan.

## Risk register

| Risk | Impact | Planned control |
|---|---|---|
| macOS output varies by release, hardware, and interface type | missed or malformed evidence | fixture families, tolerant line parsing, warnings, and pure parser tests |
| ARP cache is incomplete or stale | missing devices or misleading recency | timestamps, source labels, no completeness claim, explicit limitations |
| VPN/tunnel routes look like local LANs | probing a remote network unintentionally | passive display, explicit tunnel exclusion, eligibility reason in API/UI |
| Large private ranges cause long operations | delay and accidental broad discovery | combined address limit, timeout bounds, explicit confirmation |
| Nmap is absent | active discovery unavailable | passive-first product and capability state |
| Device evidence conflicts across sources | incorrect identity merge | conservative merge keys and visible conflict warnings |
| SVG layout becomes unreadable with many nodes | poor usability | subnet grouping, deterministic initial placement, pan/zoom/fit, label truncation with full details |
| Static server exposes unintended files | local data exposure | fixed web root, canonical path checks, symlink containment, no listing, tests |
| Browser CSP and implementation diverge | page failure or weakened boundary | no inline assets, shared header tests, documentation synchronization |
| Documentation overstates verification | false readiness claim | explicit bootstrap/planned status and exact-evidence reporting rules |

## Open-question handling

The first release uses the safe defaults from `docs/questions.md`:

- no active IPv6 discovery;
- no annotation persistence;
- no LAN bind;
- no mandatory vendor database or online lookup;
- no cache across process restarts.

If one of these decisions changes, update the requirement ledger, architecture, API, tests, privacy behavior, and operator documentation in the same change.

## Static completion criteria

Generation work for the first runnable release is statically complete only when:

1. every `PLANNED` ledger row is `DONE` or explicitly `BLOCKED` with a controlling decision;
2. every listed source owner exists and has one unambiguous responsibility;
3. models, collectors, topology, API, frontend, tests, fixtures, and documentation agree;
4. passive page load cannot invoke active discovery;
5. every active path passes through target and size validation before process invocation;
6. topology provenance and confidence remain visible from source evidence through JSON and UI;
7. all documented error and UI states have source and test definitions;
8. the local static-file boundary and restrictive headers are implemented and covered by tests;
9. accessibility and non-gesture graph controls are implemented, not merely documented;
10. repository hygiene excludes generated and private runtime data;
11. README commands correspond to files that exist;
12. remaining runtime, browser, CI, and real-network evidence gaps are reported without being presented as passed.

Static completion under the generation workflow is not formal acceptance or release readiness.