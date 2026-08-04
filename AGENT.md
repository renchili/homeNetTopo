# HomeNetTopo Project Guidance

## Project identity

`homeNetTopo` is a local-first macOS application that discovers network evidence visible from the current Mac, infers a best-effort logical topology, and renders the result as a local interactive web page.

The product must describe inferred links honestly. A single endpoint cannot prove hidden switch ports, VLAN boundaries, wireless-controller relationships, firewall-internal segments, or devices that do not respond to local discovery.

## First-release scope

The first release has two product surfaces:

1. a local discovery service that reads macOS network state and optionally performs bounded host discovery;
2. a browser interface served only on IPv4 loopback that visualizes devices, subnets, gateways, interfaces, source evidence, warnings, and confidence.

It must remain useful without cloud services, accounts, telemetry, persisted inventories, externally hosted frontend assets, or administrator privileges in the normal passive path.

The first release excludes:

- reverse-DNS enrichment;
- online hostname or MAC-vendor lookup;
- user annotations or persistent device naming;
- snapshot persistence across restarts;
- configurable LAN bind;
- active IPv6 discovery;
- port, service, vulnerability, credential, or operating-system scanning.

Names already present in approved command output may be retained with source evidence. No separate resolver or online enrichment request is allowed.

## Runtime and dependencies

- Supported platform: macOS.
- Minimum runtime: Python 3.10.
- Production Python dependencies: standard library only unless an approved coordinated change documents another dependency.
- Browser assets: repository-owned HTML, CSS, JavaScript, ES modules, and SVG; no required CDN.
- Optional active-discovery executable: Nmap.
- Development-only frontend logic tests: Node.js 20 or newer using the built-in test runner; no npm packages.
- Bind: `127.0.0.1` only.
- Default port: `8765`.

## Approved command boundary

The backend must not expose a generic command runner to HTTP or frontend callers. Commands are created only by typed specifications.

Approved command families:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <validated-targets...>
```

Requirements:

- never invoke a shell;
- use absolute paths for macOS system tools;
- resolve Nmap in this order: explicit startup option, `/opt/homebrew/bin/nmap`, `/usr/local/bin/nmap`, then `shutil.which("nmap")`;
- canonicalize the selected Nmap path and require an executable regular file;
- report only the Nmap resolution source, never the full path, through the public capability API;
- pass only canonical targets that completed both validation phases;
- parse Nmap XML from stdout with the Python standard library;
- accept only valid IPv4 and canonical MAC evidence from up hosts;
- require every reported up-host IPv4 address to remain inside the Phase B effective target set before publishing it;
- apply total subprocess deadlines, captured-output limits, and bounded terminate/kill cleanup;
- normalize failures before they reach the browser.

## Fixed limits

| Limit | Value |
|---|---:|
| Maximum JSON body | 16 KiB |
| Maximum requested networks | 32 |
| Maximum unique target addresses | 1024 |
| Active-operation timeout default | 30 seconds |
| Active-operation timeout range | 5–120 seconds |
| Nmap per-host timeout | 5 seconds |
| Passive command timeout | 5 seconds |
| Captured stdout per command | 2 MiB |
| Captured stderr per command | 64 KiB |
| Timed-out process kill grace | 2 seconds |

`operation_timeout_seconds` is the total Nmap subprocess deadline. It is not the Nmap per-host timeout.

## Active-target containment rule

An active target is eligible only when it is equal to or a subnet of one eligible RFC 1918 IPv4 network assigned to a non-tunnel local interface.

A target must be rejected when it is:

- a supernet of an eligible local network;
- merely overlapping an eligible local network;
- adjacent to but outside an eligible local network;
- unrelated RFC 1918 space;
- outside `10.0.0.0/8`, `172.16.0.0/12`, and `192.168.0.0/16`;
- loopback, link-local, multicast, unspecified, public, or reserved-only documentation space;
- associated only with a tunnel interface;
- above the fixed network-count or unique-address limits.

After every requested target passes containment validation, exact duplicates and contained targets may be removed only within the same containing eligible local network. Adjacent sibling targets must not be merged into a broader network.

## Two-phase active validation

Active discovery uses two explicit validation phases.

### Phase A: before passive commands

Validate:

- Host and browser-origin boundary;
- content type and custom request header;
- body size and JSON object shape;
- 1–32 network strings;
- canonical IPv4 syntax;
- RFC 1918 membership and disallowed address classes;
- absolute unique-address limit;
- `operation_timeout_seconds` integer range.

Phase A failure must not acquire the collection lock or start any command.

### Phase B: after fresh passive collection

Under the collection lock:

1. run the approved passive commands;
2. require successful interface evidence before active containment can be evaluated;
3. derive eligible non-tunnel local RFC 1918 networks;
4. require every requested target to be equal to or contained by one eligible local network;
5. group targets by their most-specific containing local network;
6. remove only exact duplicates and contained targets within each group, without merging adjacent siblings;
7. recalculate the final unique-address union;
8. reject any target that is a supernet, partial overlap, adjacent network, tunnel-only network, unrelated RFC 1918 network, or non-RFC1918 network.

Interface command timeout is `504 command_timeout`; unavailable or unparseable interface evidence is `500 collection_failed`. A successful interface collection with no eligible local RFC 1918 network is `400 invalid_target`.

Only after Phase A and Phase B succeed may the service resolve and invoke Nmap. The rule is **no Nmap invocation before final validation**, not “no passive command before validation.”

### Nmap evidence validation

Before active evidence is merged or a snapshot is published:

1. require an `nmaprun` XML root;
2. accept only hosts whose status is `up`;
3. validate every reported IPv4 address;
4. normalize and validate every reported MAC address;
5. require every accepted IPv4 address to belong to at least one Phase B effective target network;
6. reject malformed or out-of-range evidence as `500 collection_failed`;
7. preserve the previous snapshot on every failure.

## Browser request boundary

Every HTTP request must pass a Host allowlist derived from the configured loopback port. Accepted forms are:

```text
127.0.0.1:<port>
localhost:<port>
```

Missing, malformed, non-loopback, alternate-domain, IPv6-literal, or DNS-rebinding-style Host values are rejected.

Both collection-triggering endpoints require:

```text
Content-Type: application/json
X-HomeNetTopo-Request: 1
```

Protected collection endpoints:

```text
POST /api/v1/topology/refresh
POST /api/v1/discover
```

When `Origin` is present, it must exactly match an accepted loopback origin. When `Sec-Fetch-Site` is present, it must be `same-origin` or `none`.

Do not emit permissive CORS headers. Do not implement API preflight as an authorization path. Read-only GET endpoints must never start commands or replace snapshots.

## API and snapshot lifecycle

Read-only endpoints:

```text
GET /api/v1/health
GET /api/v1/capabilities
GET /api/v1/topology
GET /api/v1/topology/export
```

Collection endpoints:

```text
POST /api/v1/topology/refresh
POST /api/v1/discover
```

Rules:

- `GET /api/v1/topology` returns the latest in-memory snapshot or `404 not_found`; it never collects.
- `POST /api/v1/topology/refresh` performs passive collection only.
- `POST /api/v1/discover` performs Phase A validation, fresh passive collection, Phase B containment validation, then optional Nmap discovery.
- Export never collects or mutates state.
- At most one passive or active collection runs at a time.
- The browser maintains one shared collection-in-flight state and suppresses a second passive or active start until the first finishes.
- A collection request from another client while the server lock is held returns `409 collection_in_progress` immediately; it is not queued or merged.
- A successful or coherent partial passive refresh replaces the latest snapshot atomically.
- A successful active operation replaces the latest snapshot atomically.
- Failed collection preserves the previous snapshot.
- Intermediate passive data from a failed active operation is not published.
- Snapshots have no automatic TTL; clients use `collected_at` to judge freshness.

## Unsupported-platform and optional-tool capability behavior

Health may return `200` on a non-macOS host and report the normalized platform.

Capabilities on an unsupported platform must report:

- `passive_collection: false`;
- active discovery `available: false`;
- active discovery `unavailable_reason: "unsupported_platform"`;
- no command collection is attempted.

When Nmap becomes unavailable during an active request, the browser disables active discovery while preserving passive use. A later passive refresh re-reads `/api/v1/capabilities`; restored Nmap availability returns the UI to the ready state without requiring a page reload.

## Topology and evidence model

Required evidence categories:

- interface configuration;
- IPv4 routing table;
- ARP/neighbor cache;
- optional Nmap XML host-discovery evidence;
- deterministic address-membership and route inference.

Minimum node kinds:

- `local_host`;
- `interface`;
- `subnet`;
- `gateway`;
- `device`;
- `upstream_boundary`.

Every node and edge must carry enough provenance to distinguish observed facts from inference. Device-to-subnet and upstream relationships inferred from addresses or routes must remain inferred. Confidence and evidence labels must remain visible in the API and UI.

## Current ownership

```text
server.py                         HTTP routes, browser boundary, collection lock, active orchestration, snapshot owner, static delivery
homenettopo/commands.py           typed approved commands, Nmap resolution, and bounded subprocess execution
homenettopo/interfaces.py         macOS interface parser
homenettopo/routes.py             IPv4 route parser
homenettopo/neighbors.py          ARP parser
homenettopo/discovery.py          Phase A/B target validation, Nmap XML parsing, active-evidence validation
homenettopo/models.py             validated JSON-serializable domain model
homenettopo/topology.py           topology construction, merge, confidence, deterministic order
web/index.html                    accessible page structure
web/core.mjs                      pure UI state, collection coordination, API mapping, and deterministic layout
web/app.js                        fetch, capability recovery, DOM/SVG, pointer/keyboard, focus, download adapter
web/styles.css                    visual tokens, responsive layout, focus, reduced motion
tests/                            deterministic Python tests with short synthetic parser inputs inline
tests/frontend/core.test.mjs      Node built-in tests for pure frontend logic
scripts/check.py                  repository-relative full regression entrypoint
docs/                             design, API, ownership, and decisions
README.md                         operator setup and usage
metadata.json                     compact fixed product contract
```

A path listed here records the current owner only. It does not authorize creation of additional files or directories. Short single-use parser inputs remain inline in their owning test modules. A separate fixture or sample file requires a demonstrated format, size, reuse, readability, or tooling need plus explicit authorization for the exact path.

## Deterministic graph-layout boundary

The graph uses top-left world coordinates.

Fixed columns:

```text
local host       x = 0
interfaces       x = 240
subnets          x = 520
device grid      starts at x = 820
```

Node size is `180 × 72`; minimum horizontal gap is `48`; minimum vertical gap is `28`. Device-column stride is therefore `228` world units.

The upstream column is dynamic:

```text
device_grid_right = device_start_x + (column_count - 1) * 228 + 180
upstream_x = max(1160, device_grid_right + 48)
```

Each subnet owns a separate vertical lane. Three device columns are used by default and four when a subnet has more than 30 devices. Tests must prove deterministic coordinates and no rectangle overlap, including the dynamic upstream column.

## Verification ownership

Python tests:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

Frontend logic tests:

```text
node --test tests/frontend/core.test.mjs
```

Full regression:

```text
python3 scripts/check.py
```

Full regression requires Node 20+ and fails if frontend tests cannot run. A Python-only developer mode may report Node as `NOT RUN` but cannot be presented as full-regression or release evidence.

Executed tests, browser checks, CI, runtime scans, and release readiness may be claimed only with exact-revision evidence.

## Repository hygiene

Keep these out of source control:

```text
.DS_Store
__pycache__/
*.pyc
.venv/
.env
node_modules/
coverage output
test reports
runtime JSON exports
scan logs
local host inventories
packet captures
```

Test data must be clearly synthetic. Tests that do not depend on private-address semantics should prefer documentation-reserved IPv4 ranges. Tests for RFC 1918 eligibility, containment, owner grouping, address-union limits, or active-discovery evidence may use explicitly synthetic RFC 1918 addresses because those address classes are the behavior under test. Synthetic MAC values must use locally administered addresses. Short single-use inputs stay inline. Do not commit real local network identifiers, command logs, packet captures, scan exports, or user runtime data.
