# HomeNetTopo Implementation Plan

## Status and ownership

This document is the implementation plan for the first runnable HomeNetTopo release.

- Status: `PLANNED`
- Long-term owner: `docs/plan.md`
- Product authority: `AGENT.md` and `docs/questions.md`
- Architecture authority: `docs/design.md`
- Public contract authority: `docs/api-spec.md`
- Update condition: change this plan whenever scope, ownership, public behavior, limits, or completion criteria change

This plan is not runtime evidence and does not assert that planned source already exists.

## Release outcome

The first runnable release must let a macOS user start a loopback-only Python service, open a local web page, inspect a passive logical IPv4 topology, explicitly request bounded private-network host discovery when Nmap is available, inspect evidence and confidence, and export the latest in-memory snapshot as JSON.

The release must remain useful without Nmap, cloud services, accounts, telemetry, persisted inventories, reverse-DNS enrichment, annotations, online vendor data, external frontend assets, or administrator privileges in the normal passive path.

## Fixed first-release decisions

- Supported platform: macOS.
- Minimum Python: 3.10.
- Runtime Python dependencies: standard library only.
- Development-only frontend logic tests: Node 20+ built-in test runner, no npm packages.
- Bind: `127.0.0.1` only.
- Default port: `8765`.
- Page load and passive refresh never invoke Nmap.
- Active discovery requires explicit confirmation.
- Active mode: Nmap `-sn -n` host discovery only.
- Eligible targets: locally visible private IPv4 networks on non-tunnel interfaces.
- Maximum requested networks: 32.
- Maximum unique addresses: 1024.
- Active timeout: default 30 seconds, valid range 1–120 seconds.
- Maximum request body: 16 KiB.
- Passive command timeout: 5 seconds.
- Captured output: stdout 2 MiB, stderr 64 KiB.
- Timed-out process kill grace: 2 seconds.
- One passive or active collection at a time.
- Default topology GET performs passive collection.
- `refresh=false` and export never collect.
- Snapshots remain in process memory with no automatic TTL.
- Failed collection preserves the previous snapshot.
- No reverse-DNS, online hostname, vendor lookup, user annotations, or persistent naming.
- Observed facts and inferred relationships remain distinct in API and UI.
- The UI states that the graph is a best-effort logical view, not a proven physical topology.

## Planned repository layout

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
  core.mjs
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
  frontend/
    core.test.mjs
fixtures/
  macos/
    arp_all.txt
    arp_incomplete.txt
    ifconfig_multi_interface.txt
    ifconfig_utun_point_to_point.txt
    nmap_host_discovery.txt
    route_default.txt
    route_specific.txt
scripts/
  check.py
README.md
docs/
  api-spec.md
  design.md
  plan.md
  questions.md
metadata.json
```

No nested application root, generated scan output, runtime inventory, real network identifier, package cache, compiled artifact, test report, or local export belongs in source control.

## Atomic requirement ledger

Plan status vocabulary:

- `PLANNED`: required and mapped, source not yet present.
- `BLOCKED`: implementation cannot proceed without a controlling decision or permission.
- `DONE`: source, test definitions, and documentation are statically consistent; this is not runtime acceptance.

| ID | Requirement | Surface | Primary owner | Test/static owner | Documentation owner | Status |
|---|---|---|---|---|---|---|
| HT-001 | Start with Python 3.10+ on macOS and bind to IPv4 loopback | Service | `server.py` | `tests/test_server.py` | `README.md` | PLANNED |
| HT-002 | Return coherent health on any host and structured unsupported-platform errors for collection | API | `server.py` | `tests/test_server.py` | `docs/api-spec.md` | PLANNED |
| HT-003 | Execute only typed approved commands without a shell | Backend | `homenettopo/commands.py` | `tests/test_commands.py` | `AGENT.md`, `docs/design.md` | PLANNED |
| HT-004 | Resolve and canonicalize Nmap safely while using absolute macOS system-tool paths | Backend | `homenettopo/commands.py`, `homenettopo/discovery.py` | `tests/test_commands.py`, `tests/test_discovery.py` | `docs/design.md` | PLANNED |
| HT-005 | Enforce command timeouts, output limits, process cleanup, and normalized errors | Backend | `homenettopo/commands.py` | `tests/test_commands.py` | `docs/design.md`, `docs/api-spec.md` | PLANNED |
| HT-006 | Parse macOS interfaces, IPv4 addresses, prefixes, flags, and `utun` point-to-point output | Passive discovery | `homenettopo/interfaces.py` | `tests/test_interfaces.py`, interface fixtures | `docs/design.md` | PLANNED |
| HT-007 | Parse default and route-specific IPv4 gateways from `netstat` output | Passive discovery | `homenettopo/routes.py` | `tests/test_routes.py`, route fixtures | `docs/design.md` | PLANNED |
| HT-008 | Parse complete and incomplete ARP entries without fabricating devices | Passive discovery | `homenettopo/neighbors.py` | `tests/test_neighbors.py`, ARP fixtures | `docs/design.md` | PLANNED |
| HT-009 | Retain names present in approved evidence without separate DNS or online lookup | Evidence | parsers and `homenettopo/topology.py` | parser/topology tests | `AGENT.md`, `docs/api-spec.md` | PLANNED |
| HT-010 | Produce coherent partial snapshots when one passive source fails | Backend/API | collectors, `homenettopo/topology.py`, `server.py` | parser, topology, and server tests | `docs/api-spec.md` | PLANNED |
| HT-011 | Validate active targets, timeout, network count, and unique address count before Nmap | Active discovery | `homenettopo/discovery.py` | `tests/test_discovery.py` | `docs/design.md`, `docs/api-spec.md` | PLANNED |
| HT-012 | Exclude tunnel, public, special, unrelated, and oversized targets | Active discovery | `homenettopo/discovery.py` | `tests/test_discovery.py` | `docs/questions.md` | PLANNED |
| HT-013 | Invoke only fixed Nmap host-discovery arguments and parse only host-up evidence | Active discovery | `homenettopo/discovery.py` | `tests/test_discovery.py` | `docs/design.md` | PLANNED |
| HT-014 | Build stable nodes, edges, sources, warnings, confidence, and snapshot metadata | Topology | `homenettopo/models.py`, `homenettopo/topology.py` | `tests/test_models.py`, `tests/test_topology.py` | `docs/api-spec.md` | PLANNED |
| HT-015 | Merge compatible observations conservatively and retain conflicts as warnings | Topology | `homenettopo/topology.py` | `tests/test_topology.py` | `docs/design.md` | PLANNED |
| HT-016 | Implement health, capabilities, passive topology, active discovery, and export endpoints | API | `server.py` | `tests/test_server.py` | `docs/api-spec.md` | PLANNED |
| HT-017 | Implement one collection lock, immediate `409` conflicts, and atomic snapshot replacement | Service state | `server.py` | `tests/test_server.py` | `docs/design.md`, `docs/api-spec.md` | PLANNED |
| HT-018 | Implement default refresh, read-only `refresh=false`, side-effect-free export, and no snapshot TTL | API/cache | `server.py` | `tests/test_server.py` | `docs/api-spec.md` | PLANNED |
| HT-019 | Validate Host for every request and reject non-loopback/DNS-rebinding-style values | HTTP security | `server.py` | `tests/test_static_security.py`, `tests/test_server.py` | `AGENT.md`, `docs/api-spec.md` | PLANNED |
| HT-020 | Protect active POST with content type, custom header, Origin, Fetch Metadata, and no permissive CORS | HTTP security | `server.py`, `web/app.js` | `tests/test_server.py`, `tests/test_web_contract.py` | `docs/api-spec.md` | PLANNED |
| HT-021 | Enforce body limits, methods, structured errors, and no raw command or filesystem leakage | API | `server.py` | `tests/test_server.py` | `docs/api-spec.md` | PLANNED |
| HT-022 | Serve local static assets without traversal, symlink escape, directory listing, or external dependency | Web delivery | `server.py`, `web/` | `tests/test_static_security.py`, `tests/test_web_contract.py` | `docs/design.md` | PLANNED |
| HT-023 | Render deterministic layered SVG topology with pan, zoom, fit, reset, selection, details, evidence, and confidence | Browser UI | `web/core.mjs`, `web/app.js`, `web/styles.css` | Node logic tests and web contract tests | `docs/design.md` | PLANNED |
| HT-024 | Implement complete loading, empty, partial, dependency, validation, conflict, timeout, request-error, and unsupported states | Browser UI | `web/core.mjs`, `web/app.js`, `web/index.html` | frontend logic and contract tests | `docs/design.md` | PLANNED |
| HT-025 | Provide keyboard operation, visible focus, dialog focus management, non-gesture graph controls, 200% zoom support, and reduced motion | Accessibility/UI | `web/index.html`, `web/app.js`, `web/styles.css` | frontend contract tests; later browser evidence | `docs/design.md` | PLANNED |
| HT-026 | Keep network identifiers, logs, caches, exports, and generated output out of source control | Repository/privacy | `.gitignore`, all modules | `scripts/check.py`, repository inspection | `AGENT.md`, `README.md` | PLANNED |
| HT-027 | Provide deterministic Python and Node tests plus a repository-relative full regression entrypoint | Verification | `tests/`, `scripts/check.py` | self-verifying test entrypoint | `README.md`, `docs/design.md` | PLANNED |
| HT-028 | Document exact startup, Nmap setup, limits, security behavior, inference limits, and verification only after source exists | Operator docs | `README.md` | documentation consistency guards | `README.md` | PLANNED |
| HT-029 | Explicitly exclude annotations, reverse DNS, online vendor lookup, persistent cache, LAN bind, and active IPv6 from first release | Scope control | all owners | requirements/documentation guards | `AGENT.md`, `docs/questions.md` | PLANNED |

No requirement is currently blocked. Deferred questions use the fixed first-release behavior in `docs/questions.md`.

## Package 1: repository foundation and domain model

Create:

- `.gitignore` covering macOS, Python, environment, cache, log, export, local inventory, Node cache, and generated-output paths;
- `homenettopo/__init__.py` with application version;
- `homenettopo/models.py` with validated dataclasses and enums;
- `tests/__init__.py`, fixture directories, and initial model tests;
- `scripts/check.py` skeleton that fails clearly until required test owners exist.

Model owners:

```text
Evidence
SourceStatus
NetworkDescriptor
Warning
Node
Edge
ActiveDiscoveryMetadata
TopologySnapshot
```

Model rules:

- RFC 3339 UTC timestamps;
- schema version independent from application version;
- deterministic node and edge identifiers;
- deterministic serialization order;
- validated kinds, edge types, confidence, and source statuses;
- every edge endpoint must exist;
- no annotation fields in schema version `1`;
- names are evidence-backed strings only, not enrichment results.

Completion gate:

- every public field in `docs/api-spec.md` has one model or serialization owner;
- tests cover valid serialization, enum rejection, duplicate IDs, missing edge endpoints, timestamp shape, and deterministic output;
- fixtures contain only documentation-reserved addresses and locally administered synthetic MACs.

## Package 2: approved command runner and passive collectors

Implement typed command specifications in `homenettopo/commands.py`.

Approved commands:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
```

The command API accepts a typed specification, not caller-defined executable and arguments. It disables shell execution, bounds environment influence, enforces timeout/output limits, canonicalizes executable paths, and normalizes missing executable, non-zero exit, timeout, termination, truncation, and decoding failures.

Implement pure parsers:

- `interfaces.py`: interface blocks, flags, IPv4 addresses, hexadecimal netmasks, point-to-point peers, and `utun` output;
- `routes.py`: destination, gateway, flags, interface, default route, and route-specific evidence;
- `neighbors.py`: address, optional name from ARP text, MAC normalization, interface, incomplete entry, duplicates, and malformed-line warnings.

No parser initiates DNS or online lookup.

Completion gate:

- parser and invocation logic are separable;
- incomplete lines produce warnings rather than fabricated facts;
- tests cover multiple addresses, physical/virtual/tunnel interfaces, missing route, incomplete ARP, duplicate ARP, malformed text, timeout, kill escalation, output truncation, absolute system paths, and generic-command rejection.

## Package 3: active target validator and Nmap adapter

Implement two layers in `homenettopo/discovery.py`:

1. pure target eligibility and request validation;
2. Nmap resolution, fixed argument construction, and host-up parsing.

Validation order:

1. validate body structure;
2. require 1–32 network strings;
3. parse canonical IPv4 networks;
4. reject loopback, link-local, multicast, unspecified, public, reserved-only, unrelated private, and tunnel-only networks;
5. collapse overlaps;
6. calculate unique addresses;
7. reject more than 1024 addresses;
8. validate timeout from 1 through 120 seconds, default 30;
9. resolve Nmap;
10. construct arguments only from canonical validated values.

Nmap resolution order and canonicalization follow `docs/design.md`. Arguments are fixed to host discovery without name, port, or service resolution.

Completion gate:

- exact 1024 and 1025 address boundaries tested;
- exact 32 and 33 network boundaries tested;
- overlapping network deduplication tested;
- tunnel and unrelated private networks rejected;
- missing, non-executable, and canonicalized Nmap paths tested;
- approved arguments tested exactly;
- malformed output and timeout normalized;
- no HTTP path bypasses the validator.

## Package 4: topology construction and provenance

Implement deterministic transformation in `homenettopo/topology.py`.

Construction order:

1. local-host node;
2. interface nodes and host-to-interface edges;
3. subnet nodes and interface-to-subnet edges;
4. gateway nodes from route evidence;
5. neighbor and active device nodes;
6. inferred address-membership edges;
7. upstream boundary nodes and route edges;
8. compatible evidence merge;
9. conflict and partial-source warnings;
10. confidence calculation;
11. deterministic sorting.

Required invariants:

- every edge endpoint exists;
- inferred membership remains inferred;
- gateway/device identities merge only with compatible evidence;
- conflicting names and MACs remain inspectable;
- active evidence supplements passive evidence;
- no reverse-DNS or annotation fields appear;
- repeated construction from the same normalized input produces identical JSON apart from explicit snapshot identity/time fields.

Completion gate:

- tests cover empty neighbors, multi-interface, multiple subnet, tunnel, gateway merge, active/passive merge, conflicting evidence, partial sources, disconnected components, and deterministic order;
- every confidence value maps to an evidence rule documented in code and design.

## Package 5: loopback HTTP service

Implement `server.py` using the Python standard library.

Startup responsibilities:

- parse documented port and optional Nmap path;
- reject non-loopback bind configuration;
- create actual-port Host allowlist;
- initialize one collection lock and latest-snapshot owner;
- serve API and static routes;
- stop cleanly on interruption.

Request pipeline:

1. assign local request ID;
2. validate Host;
3. route path and method;
4. for active POST, validate content type, custom header, Origin, and Fetch Metadata;
5. enforce request-body limit;
6. acquire collection lock when collection is required;
7. execute collection and atomically publish success/partial result;
8. normalize response and release the lock.

Endpoint behavior:

| Endpoint | Collection | Snapshot behavior |
|---|---|---|
| `GET /api/v1/health` | none | none |
| `GET /api/v1/capabilities` | platform and executable checks | none |
| `GET /api/v1/topology` | passive | replace on success/partial success |
| `GET /api/v1/topology?refresh=true` | passive | replace on success/partial success |
| `GET /api/v1/topology?refresh=false` | none | current or `404` |
| `POST /api/v1/discover` | fresh passive plus active | replace only on full active success |
| `GET /api/v1/topology/export` | none | download current or `404` |

Concurrency behavior:

- one collection at a time;
- second collection returns `409 collection_in_progress` immediately;
- no waiting or queue;
- failed requests preserve previous snapshot;
- active failure does not publish intermediate passive data.

Completion gate:

- tests cover every documented success and error status;
- passive endpoint proves Nmap is never invoked;
- active endpoint proves validation occurs before lock-owned process invocation;
- invalid Host, mismatched Origin, cross-site Fetch Metadata, missing custom header, CORS preflight, wrong content type, large body, invalid query, concurrency, snapshot preservation, and export behavior are tested;
- error payloads contain no raw command, stderr, environment, or filesystem leakage.

## Package 6: static delivery and browser interface

### Static delivery

`server.py` serves only canonical regular files from `web/`.

Tests cover:

- raw and encoded traversal;
- repeated decoding attempts;
- NUL bytes and alternate separators;
- symlink escape;
- directory paths and listing;
- missing files;
- explicit MIME types;
- required security headers;
- absence of permissive CORS.

### Page structure

```text
header
  product title
  snapshot timestamp and mode
  passive refresh
  active discovery
  export JSON
status region
  capability and source status
  topology limitation
  warning/error summary
main
  graph toolbar
  SVG topology canvas
  details panel
active discovery dialog
  eligible network checkboxes
  unique address total
  timeout input
  confirm/cancel
```

### Pure frontend owner

`web/core.mjs` owns:

- UI state reducer;
- API response/error mapping;
- network eligibility presentation;
- deterministic graph layout;
- selection state;
- label truncation;
- compact-mode choice;
- export filename logic.

Node built-in tests execute these functions directly.

### Deterministic layout

Left-to-right columns:

```text
local host          x = 0
interfaces          x = 240
subnets             x = 520
gateways/devices    x = 820+
upstream boundaries x = 1160
```

Rules:

- node size 180 × 72 world units;
- minimum gaps 48 horizontal and 28 vertical;
- stable interface/CIDR/address sorting;
- one expandable vertical lane per subnet;
- gateway first, then devices in a three-column grid;
- more than 30 devices uses four-column compact mode;
- disconnected components receive separate lanes;
- fit view adds 48 world units padding;
- layout test asserts determinism and no node overlap.

### Visual rules

- system UI font;
- base text 16 px, supporting text no smaller than 13 px;
- spacing scale 4/8/12/16/24/32 px;
- visible 3 px focus outline with 2 px offset;
- solid observed edges;
- dashed inferred edges plus textual explanation;
- selected state uses outline/shape as well as color;
- responsive graph/details split with stacked narrow layout;
- no horizontal page overflow at 200 percent zoom;
- reduced-motion preference disables nonessential transitions.

### UI states

Required states:

```text
BOOT
LOADING_PASSIVE
PASSIVE_READY
PARTIAL_READY
EMPTY_READY
ACTIVE_CONFIRM
ACTIVE_RUNNING
ACTIVE_READY
DEPENDENCY_UNAVAILABLE
VALIDATION_ERROR
COLLECTION_CONFLICT
REQUEST_ERROR
UNSUPPORTED_PLATFORM
```

State transitions and focus behavior follow `docs/design.md`. Duplicate active submit is disabled; Escape closes dialog or clears selection; Enter/Space selects focused graph items; zoom and fit have buttons in addition to gestures.

Completion gate:

- no required asset or request leaves loopback origin;
- frontend adds `X-HomeNetTopo-Request: 1` to active POST;
- copy distinguishes logical inference from physical certainty;
- all controls have names, visible focus, disabled reasons, and keyboard paths;
- long labels, addresses, warnings, and evidence wrap or scroll in their owner;
- Python static contract tests verify local assets, CSP compatibility, IDs/hooks, labels, and external URL absence;
- Node tests verify state transitions, error mapping, layout, selection, and compact mode;
- browser interaction remains separately executed acceptance evidence.

## Package 7: regression, documentation, and repository hygiene

Implement `scripts/check.py` as the repository-relative full static regression entrypoint.

Normal command:

```text
python3 scripts/check.py
```

Required stages:

1. compile Python source with non-zero failure behavior;
2. parse `metadata.json`;
3. run Python `unittest` suite;
4. run repository/documentation path and public-contract consistency guards;
5. scan frontend assets for external URLs and inline CSP violations;
6. run `node --test tests/frontend/core.test.mjs` with Node 20+;
7. scan tracked paths for prohibited runtime and private artifacts;
8. print a stage summary and exit non-zero on any required failure.

A documented `--python-only` developer mode may skip Node but must print `NOT RUN` and cannot be used as full-regression or release evidence.

Update `README.md`, `metadata.json`, `docs/design.md`, `docs/api-spec.md`, and `docs/questions.md` to match exact implementation.

README after source exists must include:

- supported macOS and Python versions;
- production runtime versus development test dependencies;
- exact startup options and loopback URL;
- optional Nmap setup and resolution behavior;
- passive versus active behavior;
- fixed request, timeout, network, and address limits;
- Host/origin boundary at an operator-appropriate level;
- snapshot refresh and export behavior;
- privacy, no enrichment, no annotation, and no persistence behavior;
- topology inference limitations;
- exact Python, Node, and full regression commands;
- manual browser and real-network checks labeled as manual evidence.

Completion gate:

- no real addresses, hostnames, MACs, logs, exports, caches, generated reports, or build output committed;
- documentation has no implemented or verified claim without matching path/evidence;
- `metadata.json.status` changes from `bootstrap` only when runnable source exists;
- repository-relative commands and paths work independent of current directory where documented;
- CI, browser, runtime, or release success is not claimed without exact-revision evidence.

## API implementation matrix

| Contract area | Source owner | Required tests |
|---|---|---|
| Host boundary | `server.py` | valid loopback forms; missing, malformed, alternate-domain, and DNS-rebinding-style Host |
| Origin boundary | `server.py`, `web/app.js` | custom header, matching/mismatched Origin, Fetch Metadata, no CORS, OPTIONS rejection |
| Error envelope | `server.py` | each status/error code, request ID, no sensitive leakage |
| Health | `server.py` | no collection and cross-platform platform reporting |
| Capabilities | `server.py`, `discovery.py` | Nmap present/absent, exact public limits, unsupported platform |
| Passive topology | collectors, `topology.py`, `server.py` | success, coherent partial, total failure, no Nmap, collection conflict |
| Cached topology | `server.py` | `refresh=false` hit/miss, no collection, no TTL mutation |
| Active discovery | `discovery.py`, `topology.py`, `server.py` | success, all validation failures, dependency absence, timeout, conflict, snapshot preservation |
| Export | `server.py` | latest download, no snapshot, headers, no collection |
| Static assets | `server.py` | containment, MIME, headers, listing/traversal/symlink rejection |
| Node/edge model | `models.py`, `topology.py` | exact fields, references, evidence, confidence, deterministic order |

## Verification strategy

### Python deterministic suite

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

Tests use injected command adapters, synthetic normalized evidence, fixture text, and ephemeral local ports. They must not inspect or probe the test machine's real LAN.

### Frontend logic suite

```text
node --test tests/frontend/core.test.mjs
```

No npm package install is required. The suite covers pure state, error mapping, graph layout, overlap avoidance, compact mode, selection, and deterministic sorting.

### Full regression

```text
python3 scripts/check.py
```

A successful full regression requires all required stages, including Node tests, to complete with a zero exit status.

### Separate acceptance evidence

Formal project acceptance later requires exact-revision evidence for:

- startup on supported macOS;
- health, capabilities, passive refresh, cached read, export, and errors;
- invalid Host and cross-origin active request rejection;
- Nmap-unavailable behavior;
- one authorized bounded active discovery on an eligible test network;
- collection conflict behavior;
- graph pan, zoom, fit, reset, selection, details, keyboard operation, dialog focus, error recovery, reduced motion, and 200-percent zoom;
- representative Wi-Fi/Ethernet, tunnel, empty-neighbor, partial-source, and timeout states where environments permit.

The plan defines these checks but does not claim they have run.

## Risk register

| Risk | Impact | Planned control |
|---|---|---|
| macOS output varies by release and interface | missed evidence | fixture families, tolerant parsers, source warnings |
| ARP cache is incomplete or stale | missing devices | timestamps, source labels, no completeness claim |
| Tunnel routes resemble local LANs | unintended remote discovery | passive-only tunnel policy and validator rejection |
| Large private ranges cause long operations | delay or broad discovery | 32-network and 1024-address limits, bounded timeout |
| Browser reaches loopback through malicious origin/Host | unauthorized discovery request | Host allowlist, custom header, Origin/Fetch Metadata checks, no CORS |
| Concurrent collection corrupts or races snapshot | inconsistent output | one collection lock and atomic replacement |
| Nmap absent | active discovery unavailable | passive-first product and capability state |
| Child process hangs or produces large output | resource exhaustion | timeout, output caps, terminate/kill sequence |
| Device evidence conflicts | wrong identity merge | conservative keys and visible warnings |
| SVG becomes unreadable with many nodes | poor usability | deterministic lanes, compact mode, pan/zoom/fit |
| Static server exposes unintended files | local data exposure | canonical web root, symlink containment, no listing |
| CSP and assets diverge | broken or weakened page | external/inline asset guards and header tests |
| Documentation overstates readiness | false acceptance | planned/bootstrap status and exact-evidence rules |

## Static completion criteria

Generation work is statically complete only when:

1. every ledger row is `DONE` or explicitly `BLOCKED` by a controlling decision;
2. every planned source owner exists with one clear responsibility;
3. models, collectors, topology, API, static delivery, frontend, tests, scripts, and documentation agree;
4. page load and passive refresh cannot invoke Nmap;
5. all active paths pass Host/origin and target validation before process invocation;
6. one collection lock and atomic snapshot semantics are implemented and tested;
7. refresh, cache, failure preservation, and export behavior exactly match the API contract;
8. topology provenance and confidence remain visible from evidence through JSON and UI;
9. reverse DNS, online enrichment, annotations, persistence, LAN bind, and active IPv6 remain absent;
10. every documented API and UI state has source and test ownership;
11. static containment and security headers are implemented and tested;
12. keyboard, focus, non-gesture graph controls, responsive layout, and reduced motion are implemented;
13. Python tests, Node tests, and `scripts/check.py` are defined and consistent;
14. repository hygiene excludes private and generated runtime data;
15. README commands correspond to source that exists;
16. runtime, browser, CI, and real-network evidence gaps are reported without being presented as passed.

Static completion under the generation workflow is not formal acceptance or release readiness.
