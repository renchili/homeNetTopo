# HomeNetTopo Implementation Plan

## Status and authority

This document is the implementation plan for the first runnable HomeNetTopo release.

- Status: `PLANNED`
- Long-term owner: `docs/plan.md`
- Product authority: `AGENT.md` and `docs/questions.md`
- Architecture authority: `docs/design.md`
- Public API authority: `docs/api-spec.md`
- Metadata authority: `metadata.json`

This plan is not runtime evidence and does not assert that planned source already exists.

## Release outcome

A macOS user can start a loopback-only Python service, explicitly request a passive topology refresh, inspect a logical IPv4 topology, optionally confirm bounded Nmap host discovery, inspect evidence and confidence, and download the latest in-memory snapshot as JSON.

The release remains useful without Nmap, cloud services, accounts, telemetry, persistence, annotations, online enrichment, production Node, npm packages, external frontend assets, or administrator privileges in the normal passive path.

## Fixed first-release decisions

- macOS, Python 3.10+, standard-library production runtime.
- Repository-owned HTML, CSS, JavaScript, ES modules, and SVG.
- Node.js 20+ built-in test runner for development-only frontend tests.
- Bind `127.0.0.1`; default port `8765`.
- Every GET endpoint is read-only and executes no collection command.
- Passive refresh: protected `POST /api/v1/topology/refresh`.
- Active discovery: protected `POST /api/v1/discover`.
- Both collection POSTs require JSON, `X-HomeNetTopo-Request: 1`, accepted Host, matching Origin when present, and non-cross-site Fetch Metadata when present.
- One collection at a time; a second collection returns `409 collection_in_progress`.
- Nmap command: `-sn -n --max-retries 1 --host-timeout 5s -oX -`.
- Nmap XML is parsed from stdout with `xml.etree.ElementTree`.
- `operation_timeout_seconds` is the total Nmap process deadline: default 30, range 5–120.
- Nmap per-host timeout is separately fixed at five seconds.
- Maximum body 16 KiB, maximum 32 requested networks, maximum 1024 unique addresses.
- Active targets must equal or be subnets of eligible non-tunnel local networks.
- Supernets, partial overlaps, adjacent networks, tunnel-only networks, and unrelated private networks are rejected.
- Snapshots remain in process memory without TTL.
- Failed operations preserve the previous snapshot.
- No reverse DNS, online vendor lookup, annotations, persistence, LAN bind, active IPv6, port scan, service scan, or OS scan.
- Graph node coordinates are top-left world coordinates.
- The upstream graph column is computed dynamically after the device grid.

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
    nmap_host_discovery.xml
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

No nested project root, real network inventory, runtime export, scan log, cache, test report, compiled output, or secret belongs in source control.

## Atomic requirement ledger

Status vocabulary:

- `PLANNED`: required and mapped; source is not present yet.
- `BLOCKED`: cannot proceed without a controlling decision or permission.
- `DONE`: source, tests, and documentation are statically consistent; this does not mean runtime acceptance passed.

| ID | Requirement | Primary owner | Test/static owner | Documentation owner | Status |
|---|---|---|---|---|---|
| HT-001 | Start with Python 3.10+ on macOS and bind to IPv4 loopback | `server.py` | `tests/test_server.py` | `README.md` | PLANNED |
| HT-002 | Health works without collection and capabilities define exact unsupported-platform behavior | `server.py` | `tests/test_server.py` | `docs/api-spec.md` | PLANNED |
| HT-003 | Execute only typed approved commands with no shell or caller-defined executable | `homenettopo/commands.py` | `tests/test_commands.py` | `AGENT.md`, `docs/design.md` | PLANNED |
| HT-004 | Resolve Nmap safely and expose only resolution source, never full path | `commands.py`, `discovery.py` | command/discovery tests | `docs/api-spec.md` | PLANNED |
| HT-005 | Enforce passive deadlines, Nmap operation deadline, output limits, and terminate/kill cleanup | `commands.py` | `tests/test_commands.py` | design/API | PLANNED |
| HT-006 | Parse macOS interfaces, IPv4 addresses, masks, flags, and `utun` point-to-point output | `interfaces.py` | interface fixtures/tests | design | PLANNED |
| HT-007 | Parse default and route-specific IPv4 gateways from `netstat` | `routes.py` | route fixtures/tests | design | PLANNED |
| HT-008 | Parse complete and incomplete ARP records without fabricating devices | `neighbors.py` | ARP fixtures/tests | design | PLANNED |
| HT-009 | Retain names already present in approved evidence without separate resolution | parsers, `topology.py` | parser/topology tests | AGENT/API | PLANNED |
| HT-010 | Produce coherent partial passive snapshots while total passive failure preserves prior state | collectors, `topology.py`, `server.py` | parser/topology/server tests | API | PLANNED |
| HT-011 | Perform Phase A validation before lock or commands | `discovery.py`, `server.py` | discovery/server negative tests | design/API | PLANNED |
| HT-012 | Perform Phase B containment validation after fresh passive collection | `discovery.py`, `server.py` | exact containment tests | design/API | PLANNED |
| HT-013 | Reject supernets, partial overlaps, adjacent networks, unrelated private space, tunnels, and special/public ranges | `discovery.py` | boundary matrix | AGENT/questions | PLANNED |
| HT-014 | Enforce 32-network and 1024-address union limits before Nmap | `discovery.py` | 32/33 and 1024/1025 tests | API | PLANNED |
| HT-015 | Invoke fixed Nmap XML command only after both validation phases | `discovery.py`, `commands.py` | exact arguments and no-bypass tests | design/API | PLANNED |
| HT-016 | Parse only host-up address/status evidence from Nmap XML | `discovery.py` | XML fixtures and malformed XML tests | design | PLANNED |
| HT-017 | Keep total operation timeout separate from fixed Nmap per-host timeout | `discovery.py`, `commands.py` | timeout construction and deadline tests | API/metadata | PLANNED |
| HT-018 | Build stable nodes, edges, sources, networks, warnings, confidence, and active metadata | `models.py`, `topology.py` | model/topology tests | API | PLANNED |
| HT-019 | Merge compatible evidence conservatively and retain conflicts visibly | `topology.py` | conflict and determinism tests | design | PLANNED |
| HT-020 | Implement read-only health, capabilities, topology, and export GET endpoints | `server.py` | prove no command invocation | API | PLANNED |
| HT-021 | Implement protected passive-refresh POST that never invokes Nmap | `server.py`, collectors | server tests | API/README | PLANNED |
| HT-022 | Implement protected active-discovery POST with Phase A, passive collection, Phase B, then Nmap | `server.py`, `discovery.py` | server/discovery tests | API | PLANNED |
| HT-023 | Serialize collection with one lock and immediate `409` conflicts | `server.py` | concurrency tests | design/API | PLANNED |
| HT-024 | Atomically replace successful snapshots and preserve prior state on every failure path | `server.py` | snapshot lifecycle tests | design/API | PLANNED |
| HT-025 | Validate Host for every request and reject DNS-rebinding-style values | `server.py` | static-security/server tests | AGENT/API | PLANNED |
| HT-026 | Protect both collection POSTs with custom header, Origin, Fetch Metadata, content type, and no CORS/preflight bypass | `server.py`, `web/app.js` | positive/negative browser-boundary tests | API | PLANNED |
| HT-027 | Enforce body limits, methods, error envelopes, and no sensitive command/path leakage | `server.py` | server tests | API | PLANNED |
| HT-028 | Serve only contained local assets with traversal, decoding, symlink, MIME, and listing protection | `server.py` | static-security tests | design | PLANNED |
| HT-029 | Render deterministic layered SVG topology with dynamic upstream placement and no rectangle overlap | `web/core.mjs`, `web/app.js` | Node layout tests | design | PLANNED |
| HT-030 | Implement complete loading, empty, partial, unavailable, validation, conflict, timeout, request-error, and unsupported states | `core.mjs`, `app.js`, `index.html` | Node and contract tests | design | PLANNED |
| HT-031 | Provide keyboard operation, focus management, non-gesture controls, 200% zoom support, and reduced motion | web owners | contract tests plus later browser evidence | design | PLANNED |
| HT-032 | Provide deterministic Python and Node tests and a full repository-relative regression entrypoint | `tests/`, `scripts/check.py` | self-verifying entrypoint | README/design | PLANNED |
| HT-033 | Keep runtime/private/generated data out of source control | `.gitignore`, all owners | regression hygiene stage | AGENT/README | PLANNED |
| HT-034 | Document exact implementation only after matching source exists | README and docs | consistency guards | README | PLANNED |
| HT-035 | Enforce first-release exclusions across metadata, model, API, UI, and tests | all owners | requirements/contract guards | AGENT/questions | PLANNED |

No requirement is currently blocked.

## Package 1: repository foundation and model

Create `.gitignore`, package/test roots, `models.py`, initial synthetic fixtures, and `scripts/check.py` skeleton.

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
- deterministic IDs and serialization order;
- validated node kinds, edge types, confidence, and source statuses;
- every edge endpoint exists;
- no annotation or enrichment fields in schema version `1`;
- active metadata distinguishes operation timeout, host timeout, requested targets, and effective collapsed targets.

Completion gate:

- every API field has one owner;
- tests reject invalid enum values, duplicate IDs, missing endpoints, malformed timestamps, and unstable ordering;
- fixtures use documentation-reserved IPs and synthetic locally administered MACs.

## Package 2: commands and passive collectors

Implement typed command specifications:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
```

The runner accepts only typed specifications, disables shell execution, bounds environment influence, enforces deadlines and output caps, performs terminate/kill cleanup, and normalizes missing executable, non-zero exit, timeout, truncation, and decoding failures.

Parsers remain pure over fixture text where practical.

Completion gate:

- caller-defined executable/arguments are impossible through the public command API;
- tests cover physical, virtual, and tunnel interfaces; multiple addresses; missing route; incomplete and duplicate ARP; malformed lines; timeouts; kill escalation; truncation; and absolute paths.

## Package 3: active validation and Nmap XML

### Phase A

Pure validation before lock or commands:

- request object and body size;
- 1–32 strings;
- canonical IPv4 syntax;
- disallowed address classes;
- absolute union limit;
- total operation timeout range.

### Phase B

After fresh passive collection under lock:

- derive eligible non-tunnel local networks;
- require each target to be equal to or a subnet of one eligible local network;
- reject supernets, partial overlaps, adjacent ranges, tunnel-only ranges, and unrelated private ranges;
- collapse duplicate and contained targets;
- recalculate final union.

### Nmap

Resolution order follows `docs/design.md`. Public capabilities expose resolution source only.

Fixed command:

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <effective-targets...>
```

The subprocess runner applies `operation_timeout_seconds` as the total deadline. XML is parsed with `xml.etree.ElementTree`; only up-host status and address elements become evidence.

Completion gate:

- equal and contained targets pass;
- supernet, partial-overlap, adjacent, unrelated, tunnel, public, special, 1025-address, and 33-network cases fail;
- no Nmap resolution or invocation occurs before both phases pass;
- XML success, malformed XML, missing status/address, timeout, and unavailable executable cases are covered.

## Package 4: topology construction

Construction order:

1. local host;
2. interfaces and host-to-interface edges;
3. subnets and interface-to-subnet edges;
4. gateways from route evidence;
5. passive and active devices;
6. inferred address membership;
7. upstream boundaries;
8. conservative merges;
9. conflict and source warnings;
10. confidence;
11. deterministic ordering.

Invariants:

- every edge endpoint exists;
- inferred membership remains inferred;
- gateway/device merge requires compatible evidence;
- conflicting names and MACs remain inspectable;
- active evidence supplements passive evidence;
- repeated normalized input yields identical JSON apart from explicit snapshot ID/time.

## Package 5: loopback HTTP service

Startup:

- parse port and optional Nmap path;
- reject non-loopback bind;
- create Host allowlist from actual port;
- initialize collection lock and snapshot owner;
- serve API/static routes;
- stop cleanly.

Request pipeline for collection POSTs:

1. request ID;
2. Host validation;
3. method/path routing;
4. custom header, Origin, Fetch Metadata, content type;
5. body limit and JSON parse;
6. endpoint-specific pre-command validation;
7. acquire collection lock;
8. run collection flow;
9. atomically publish success/partial result;
10. release lock and serialize response.

Endpoint matrix:

| Endpoint | Commands | State mutation |
|---|---|---|
| `GET /api/v1/health` | none | none |
| `GET /api/v1/capabilities` | executable metadata check only; no discovery | none |
| `GET /api/v1/topology` | none | none |
| `POST /api/v1/topology/refresh` | passive only | replace on success/coherent partial |
| `POST /api/v1/discover` | passive then validated Nmap | replace only on active success |
| `GET /api/v1/topology/export` | none | none |

Completion gate:

- tests prove every GET is command-free;
- both POSTs enforce browser boundary;
- passive refresh never calls Nmap;
- active request cannot reach Nmap before Phase A and Phase B;
- active failure does not publish intermediate passive data;
- invalid Host/origin/header/content type/body/method/query, concurrency, unsupported platform, timeout, and export cases are covered.

## Package 6: static delivery and browser UI

### Static delivery

Tests cover raw and encoded traversal, repeated decoding, NUL bytes, separator ambiguity, symlink escape, directories, missing files, MIME types, security headers, and no CORS.

### Page structure

```text
header
  title, timestamp/mode, passive refresh, active discover, export
status region
  capability, limitation, source warnings, error summary
main
  graph toolbar, SVG canvas, details panel
active dialog
  eligible targets, address total, operation timeout, confirm/cancel
```

Initial load calls protected passive-refresh POST.

### Pure frontend owner

`web/core.mjs` owns state reduction, API mapping, target display, deterministic graph layout, selection, truncation, compact mode, and export filename.

### Coordinate system and layout

All node coordinates are top-left world coordinates.

```text
node_width = 180
node_height = 72
horizontal_gap = 48
vertical_gap = 28
column_stride = 228
host_x = 0
interface_x = 240
subnet_x = 520
device_start_x = 820
minimum_upstream_x = 1160
```

Three device columns are used by default and four for more than 30 devices in a subnet.

```text
device_grid_right = device_start_x + (column_count - 1) * column_stride + node_width
upstream_x = max(minimum_upstream_x, device_grid_right + horizontal_gap)
```

Each subnet has an expandable vertical lane. Disconnected components receive separate lanes. Fit adds 48 units padding.

Node tests prove deterministic output and non-overlapping rectangles for normal, compact, disconnected, reordered-input, and upstream-node cases.

### Visual and interaction rules

- system UI font;
- 16 px base text, 13 px minimum supporting text;
- spacing 4/8/12/16/24/32 px;
- visible 3 px focus outline with 2 px offset;
- observed edges solid, inferred edges dashed plus textual explanation;
- selection not color-only;
- desktop split and narrow stacked layout;
- no horizontal page overflow at 200% zoom;
- reduced motion disables nonessential transitions;
- pan and pointer-centered bounded zoom;
- zoom-in/out, fit, and reset buttons;
- focused graph items selectable with Enter/Space;
- Escape closes dialog or clears selection.

Required UI states:

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

## Package 7: verification, documentation, and hygiene

### Python suite

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

### Frontend suite

```text
node --test tests/frontend/core.test.mjs
```

### Full regression

```text
python3 scripts/check.py
```

Required stages:

1. compile Python source;
2. parse `metadata.json`;
3. run Python tests;
4. run path and public-contract consistency guards;
5. scan frontend assets for external URLs and CSP violations;
6. run Node tests with Node 20+;
7. scan tracked paths for prohibited runtime/private artifacts;
8. print stage summary and exit non-zero on any required failure.

A `--python-only` developer mode may report Node as `NOT RUN` but cannot be used as full-regression or release evidence.

README after implementation must include exact startup, optional Nmap setup, resolution-source behavior, protected passive refresh, active confirmation, containment rule, operation and host timeout distinction, limits, snapshot lifecycle, privacy, exclusions, topology limitations, and exact verification commands.

## API implementation matrix

| Area | Source owner | Required tests |
|---|---|---|
| Host boundary | `server.py` | accepted loopback forms; missing, malformed, alternate-domain, IPv6-literal, rebinding-style values |
| Collection origin boundary | `server.py`, `app.js` | header, Origin, Fetch Metadata, no CORS, OPTIONS rejection for both POSTs |
| Health/capabilities | `server.py`, `discovery.py` | supported/unsupported platform; Nmap present/absent; source without full path |
| Read-only topology/export | `server.py` | hit/miss, no command, no state mutation |
| Passive refresh | collectors, topology, server | success, coherent partial, total failure, timeout, conflict, no Nmap |
| Phase A | discovery/server | malformed body, count, syntax, special/public, absolute union, timeout |
| Phase B | discovery/server | equal, contained, supernet, partial overlap, adjacent, unrelated, tunnel |
| Nmap | discovery/commands | exact XML arguments, total deadline, host timeout, XML parsing, unavailable/malformed/timeout |
| Snapshot lifecycle | server | atomic replacement, prior-state preservation, no intermediate active publication |
| Static assets | server | containment, decoding, MIME, headers, listing/symlink rejection |
| Graph | core.mjs | coordinate convention, dynamic upstream, no overlap, compact mode, deterministic order |

## Risk register

| Risk | Impact | Planned control |
|---|---|---|
| macOS output variation | missed evidence | fixture families, tolerant parsers, warnings |
| Stale/incomplete ARP | missing devices | timestamps, evidence labels, no completeness claim |
| Target supernet or partial overlap | discovery outside attached LAN | explicit subnet containment and negative tests |
| Tunnel route resembles LAN | unintended remote probe | tunnel exclusion in Phase B |
| Large request | delay/broad probe | count, union, body, and timeout limits |
| Cross-origin loopback trigger | unauthorized command execution | all collection routes protected POSTs; GETs read-only |
| Nmap human-output variation | parser instability | XML stdout and standard-library parser |
| Timeout ambiguity | misleading deadline | total operation timeout separate from fixed host timeout |
| Concurrent collection | snapshot race | one lock and atomic replacement |
| Device/upstream layout overlap | unusable graph | top-left convention and dynamic upstream calculation |
| Static-file escape | local exposure | canonical root and negative tests |
| Documentation overclaim | false readiness | bootstrap/planned status and exact-evidence rules |

## Static completion criteria

Generation is statically complete only when:

1. every ledger row is `DONE` or explicitly `BLOCKED`;
2. every source/test/document owner exists;
3. all GET routes are read-only and command-free;
4. both collection POSTs enforce Host and origin boundary;
5. Phase A runs before lock/commands and Phase B runs after fresh passive evidence;
6. target containment rejects supernets, partial overlaps, adjacent ranges, tunnels, and unrelated ranges;
7. no Nmap resolution/invocation occurs before both validation phases pass;
8. Nmap uses XML and timeout semantics remain distinct;
9. collection lock and snapshot replacement/preservation are implemented and tested;
10. topology evidence and confidence remain visible through API and UI;
11. graph coordinates are top-left, upstream is dynamic, and rectangle overlap tests pass statically;
12. every UI state and accessibility rule has source and tests;
13. static containment and restrictive headers are implemented and tested;
14. Python, Node, and full-regression entrypoints agree;
15. first-release exclusions remain absent from model/API/UI;
16. README commands correspond to existing source;
17. runtime, browser, CI, and real-network evidence gaps are not presented as passed.

Static completion is not formal runtime acceptance or release readiness.
