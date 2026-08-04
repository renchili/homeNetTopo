# HomeNetTopo Design

## Status

This document defines the intended first runnable implementation. It is a design contract, not evidence that the application already runs or deploys successfully.

## Goals

- Discover IPv4 network facts visible from the current macOS host.
- Build a best-effort logical topology with explicit provenance and confidence.
- Serve an interactive loopback-only web page.
- Keep topology data on the Mac and in process memory.
- Avoid mandatory third-party production dependencies and external frontend assets.
- Keep passive collection separate from optional bounded active discovery.
- Provide a repeatable current-user macOS deployment and removal path.
- Define deterministic implementation, UI, deployment, documentation, and test ownership.

## Non-goals

- Proving complete physical topology from one endpoint.
- Identifying hidden switching, VLAN, controller, or firewall-internal structure.
- Public, internet-wide, port, service, vulnerability, credential, or OS scanning.
- Reverse-DNS, online hostname, or MAC-vendor enrichment.
- User annotations or persistent device naming.
- Persistent snapshots, active IPv6 discovery, LAN bind, or multi-user hosting.
- System-wide daemons, administrator-level installation, containers, cloud deployment, or remote-host deployment.

## Runtime and development environment

Production:

- macOS;
- Python 3.10 or newer;
- Python standard library;
- repository-owned HTML, CSS, JavaScript, ES modules, and SVG;
- optional Nmap executable for active discovery.

Development-only frontend tests use Node.js 20+ and the built-in test runner without npm packages. Production startup and deployment do not require Node.

## Module ownership

```text
server.py
  Loopback HTTP server, Host/origin checks, routes, response serialization,
  static-file containment, collection lock, active orchestration, and latest-snapshot state.

homenettopo/commands.py
  Typed approved commands, Nmap executable resolution, shell-free subprocesses,
  total deadlines, output limits, terminate/kill cleanup, normalized results.

homenettopo/interfaces.py
  Parser for `/sbin/ifconfig -a`.

homenettopo/routes.py
  Strict parser for `/usr/sbin/netstat -rn -f inet`, including macOS
  abbreviated destinations, IPv4, link, and MAC gateway forms.

homenettopo/neighbors.py
  Parser for `/usr/sbin/arp -an`, including incomplete records.

homenettopo/discovery.py
  Phase A and Phase B target validation, Nmap XML host-up parsing,
  IPv4/MAC normalization, and effective-target evidence validation.

homenettopo/models.py
  Validated JSON-serializable evidence, source, network, node, edge, warning,
  active-discovery, and snapshot structures.

homenettopo/topology.py
  Deterministic topology construction, conservative merge, warnings,
  confidence, and output ordering.

web/index.html
  Accessible document, controls, status regions, graph, details, and dialog.

web/core.mjs
  Pure UI state, shared collection-in-flight coordination, API/error mapping,
  capability recovery, target presentation, layout, selection, and export naming.

web/app.js
  Fetch, capability recheck, DOM/SVG, pointer and keyboard input, focus,
  dialog, collection guards, and download adapter.

web/styles.css
  Visual tokens, responsive layout, graph states, focus, and reduced motion.

scripts/deploy.py
  Current-user macOS LaunchAgent installation, runtime allowlist copy,
  rollback, loopback health verification, status, restart, and uninstall.

scripts/check.py
  Repository-relative full regression entrypoint, including documentation,
  deployment, contract, asset, test, and hygiene guards.
```

## Approved command model

The service never accepts an executable or argument list from HTTP input.

```text
INTERFACES  /sbin/ifconfig -a
ROUTES      /usr/sbin/netstat -rn -f inet
NEIGHBORS   /usr/sbin/arp -an
DISCOVERY   <canonical-nmap-path> -sn -n --max-retries 1
            --host-timeout 5s -oX - <validated-targets...>
```

Nmap resolution order:

1. explicit startup option;
2. `/opt/homebrew/bin/nmap`;
3. `/usr/local/bin/nmap`;
4. `shutil.which("nmap")`.

The selected path is canonicalized with `realpath` and must reference an executable regular file. The public API reports only the resolution source: `explicit`, `homebrew_arm64`, `homebrew_intel`, `path`, or `unavailable`.

### Command limits

| Limit | Value |
|---|---:|
| Passive command timeout | 5 seconds |
| Active-operation timeout default | 30 seconds |
| Active-operation timeout range | 5–120 seconds |
| Nmap per-host timeout | 5 seconds |
| Child-process kill grace | 2 seconds |
| Captured stdout | 2 MiB |
| Captured stderr | 64 KiB |

`operation_timeout_seconds` is the total Nmap subprocess deadline. `--host-timeout 5s` is a separate fixed per-host Nmap limit.

On timeout, terminate the process, wait up to two seconds, then kill if needed. Truncated output is a normalized failure unless a parser contract explicitly defines a safe warning-only case.

## Passive collection flow

1. validate Host and protected request headers;
2. validate empty JSON request body;
3. acquire the single collection lock or return `409`;
4. confirm the platform is macOS;
5. run interfaces, routes, and ARP commands;
6. parse each source independently and treat nonempty unrecognized output as a source failure;
7. construct a complete or coherent partial passive snapshot;
8. atomically replace the latest snapshot;
9. release the lock;
10. in the browser, re-read capabilities after success so restored Nmap availability can be detected.

One source may fail while the other evidence remains coherent. Failure of all material passive sources returns `collection_failed` and preserves the prior snapshot.

The route parser requires the IPv4 routing-table header and reads destination, gateway, flags, and interface from the first four route columns. It accepts `default`, full or abbreviated IPv4 destinations, IPv4 gateways, `link#N`, and colon-delimited MAC gateways. Optional Expire data is ignored after the interface column. A nonempty table with no recognizable route rows is a parse failure.

No separate hostname, DNS, vendor, or online lookup occurs.

## Active discovery flow

### Phase A: request and absolute safety validation

Before acquiring the collection lock or running commands:

1. validate Host;
2. validate custom header, Origin, and Fetch Metadata;
3. enforce 16 KiB body limit;
4. parse JSON object;
5. require 1–32 network strings;
6. canonicalize IPv4 networks;
7. require every target to be within RFC 1918 space—`10.0.0.0/8`, `172.16.0.0/12`, or `192.168.0.0/16`—and reject public or special address classes;
8. reject an absolute unique-address union above 1024;
9. validate `operation_timeout_seconds` from 5 through 120.

### Phase B: current local-network containment

After Phase A succeeds:

1. acquire the collection lock or return `409`;
2. run fresh passive collection;
3. require usable interface evidence before active containment evaluation;
4. derive eligible RFC 1918 networks assigned to non-tunnel interfaces;
5. require every requested target to be equal to or a subnet of one eligible local network;
6. assign every target to its most-specific containing local network;
7. reject supernets, partial overlaps, adjacent networks, unrelated RFC 1918 networks, non-RFC1918 networks, and tunnel-only networks;
8. remove exact duplicates and contained targets only within the same owner group; adjacent sibling targets remain separate and are never widened;
9. recalculate the final unique-address union and require at most 1024.

Interface evidence failure is not a target validation error:

- interface command timeout returns `504 command_timeout`;
- unavailable or unparseable interface evidence returns `500 collection_failed`;
- successful interface collection with no eligible local RFC 1918 network returns `400 invalid_target`.

Only after both phases pass:

1. resolve Nmap;
2. pass the Phase B effective target set to the fixed command adapter without cross-owner containment reduction;
3. run the fixed XML-output command with the requested total operation deadline;
4. require an `nmaprun` XML root and consider only hosts whose status is `up`;
5. validate each reported IPv4 address and normalize each optional MAC to six lowercase hexadecimal octets;
6. require every accepted IPv4 address to belong to at least one Phase B effective target network;
7. reject malformed or out-of-range Nmap evidence as `500 collection_failed`;
8. merge only validated active evidence into the fresh passive snapshot;
9. atomically replace the latest snapshot;
10. release the lock.

Duplicate reported IPv4 hosts are reduced deterministically. A failed active operation preserves the previous snapshot. Intermediate passive data is not published.

## Target-containment rules

For each requested target `T`, at least one eligible local RFC 1918 network `L` must satisfy:

```text
T == L or T.subnet_of(L)
```

When more than one local network contains `T`, the most-specific containing local network owns that target for Phase B reduction.

These are rejected:

- `T` is a supernet of `L`;
- `T` only partially overlaps `L`;
- `T` is adjacent to `L` but outside it;
- `T` is RFC 1918 but unrelated;
- `T` is outside `10.0.0.0/8`, `172.16.0.0/12`, and `192.168.0.0/16`;
- `T` is available only through a tunnel interface;
- `T` is loopback, link-local, multicast, unspecified, public, or reserved-only documentation space.

Exact duplicates and contained targets may be removed only when they share the same Phase B owner. Adjacent sibling targets and targets owned by different overlapping local networks remain distinct in the Nmap argument list.

Tests must cover equal, contained, duplicate, supernet, partial-overlap, adjacent, unrelated, tunnel-only, overlapping local owners, 1024-address, 1025-address, 32-network, and 33-network cases.

## Snapshot lifecycle and API ownership

Read-only endpoints never run commands:

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

- GET topology returns the latest snapshot or `404`.
- Export downloads the latest snapshot or returns `404`.
- One passive or active collection may run at a time.
- The browser uses a single collection-in-flight field and refuses a second passive or active start until the current operation resolves.
- Stale success or error actions whose operation kind does not match the active collection are ignored.
- A second collection from another client returns `409` immediately.
- Successful and coherent partial passive refreshes replace the snapshot atomically.
- Successful active discovery replaces the snapshot atomically.
- Failed operations preserve the previous snapshot.
- Snapshots have no automatic TTL.

## Browser request boundary

Every request validates Host against the configured port:

```text
127.0.0.1:<port>
localhost:<port>
```

Collection POST requests require:

```text
Content-Type: application/json
X-HomeNetTopo-Request: 1
```

When present, Origin must match an accepted loopback origin, and `Sec-Fetch-Site` must be `same-origin` or `none`. The server emits no permissive CORS headers and rejects API OPTIONS.

This design prevents simple cross-origin GET requests from launching commands because every command-triggering route is a protected POST.

## Unsupported-platform and optional-tool recovery

- Health may return `200` and report the actual normalized platform.
- Capabilities report `passive_collection: false` on unsupported platforms.
- Active discovery reports `available: false` and `unavailable_reason: "unsupported_platform"` when collection is unsupported.
- Collection endpoints return `501 unsupported_platform` without running commands.
- A runtime `424 dependency_unavailable` sets the browser's active capability to unavailable while passive topology remains usable.
- The next successful passive refresh re-reads `/api/v1/capabilities`; if Nmap is restored, active capability and the ready UI state recover without a page reload.

## Current-user macOS deployment

`scripts/deploy.py` installs or updates one current-user LaunchAgent. It is not a system package installer and never requests administrator privileges.

Fixed deployment locations:

```text
runtime  ~/Library/Application Support/HomeNetTopo
plist    ~/Library/LaunchAgents/com.homenettopo.local.plist
logs     ~/Library/Logs/HomeNetTopo
```

The copied runtime is an explicit allowlist:

```text
server.py
metadata.json
scripts/deploy.py
homenettopo/
web/
```

Tests, documentation, Git metadata, caches, reports, topology exports, command logs, and machine-specific network data are not deployed.

### Install and update flow

1. require macOS and Python 3.10+;
2. validate the requested port and optional executable Nmap path;
3. verify every runtime allowlist path exists;
4. copy the allowlist to a temporary sibling staging directory;
5. boot out an existing user LaunchAgent when present;
6. move the existing runtime to a temporary rollback directory;
7. atomically move the staged runtime into the fixed install path;
8. atomically write a mode-`0600` LaunchAgent plist;
9. bootstrap and kickstart `com.homenettopo.local` in `gui/<uid>`;
10. poll only `http://127.0.0.1:<port>/api/v1/health`;
11. delete the rollback directory only after the health response identifies HomeNetTopo as healthy.

If activation or health verification fails, deployment boots out the failed service, restores the prior runtime and plist, and re-bootstrap attempts the prior user service when one existed.

The generated LaunchAgent always passes `--bind 127.0.0.1`. It may pass a validated port and optional canonical Nmap path. It uses `RunAtLoad`, restarts after unexpected failure, writes stdout/stderr to the user log directory, and does not use a shell.

Supported management actions:

```text
python3 scripts/deploy.py install [--port PORT] [--nmap-path PATH]
python3 scripts/deploy.py status
python3 scripts/deploy.py restart
python3 scripts/deploy.py uninstall [--purge-logs]
```

Uninstall removes the current-user LaunchAgent and runtime. Logs remain unless `--purge-logs` is explicitly supplied. The script does not contact remote hosts or change system-wide configuration.

## Topology model

### Snapshot fields

```text
schema_version
snapshot_id
collected_at
mode
platform
partial
warnings[]
sources[]
networks[]
nodes[]
edges[]
active_discovery?
```

### Node fields

```text
id
kind
label
addresses[]
mac_addresses[]
interface_names[]
properties{}
evidence[]
confidence
observed_at
```

### Edge fields

```text
id
source
target
type
observed
confidence
evidence[]
properties{}
```

`observed` means supported by collected local configuration. It does not prove physical cabling or switching.

Confidence:

- `high`: direct configuration or corroborated observations;
- `medium`: reliable observation plus deterministic route/membership inference;
- `low`: incomplete or heuristic association retained with warning.

## Graph construction rules

- One local-host node represents the Mac.
- Interfaces attach the host to subnet nodes.
- Gateways require route and address evidence.
- Neighbor and validated active hosts attach to subnets through explicit address-membership inference.
- Upstream boundaries represent networks beyond local observation.
- Compatible device evidence merges conservatively.
- Conflicting names or MACs remain visible as warnings.
- Active evidence supplements rather than erases passive evidence.
- Output ordering is deterministic.
- Inferred links never become observed physical links.

## Static-file boundary

- Serve only canonical regular files under the canonical `web/` root.
- Decode URL paths exactly once.
- Reject parent segments, encoded traversal, repeated-decoding tricks, NUL bytes, separator ambiguity, directories, and symlink escapes.
- Use an explicit MIME map.
- Disable directory listing.
- Apply the documented security headers.

## Frontend information architecture

```text
header
  product title
  timestamp and mode
  passive refresh
  active discovery
  export JSON
status region
  platform and capability
  logical-topology limitation
  source warnings and errors
main
  graph toolbar
  SVG topology canvas
  selected-item details
active discovery dialog
  eligible target checkboxes
  unique address total
  operation timeout
  confirm/cancel
```

Initial page load calls `POST /api/v1/topology/refresh` with the protected request headers. It does not invoke Nmap. A successful passive refresh also rechecks capabilities.

## Visual system

Typography: system UI stack, 16 px base text, supporting text no smaller than 13 px.

Spacing:

```text
4, 8, 12, 16, 24, 32 px
```

Core tokens:

```text
--surface: #ffffff
--surface-muted: #f5f7fa
--text: #17202a
--text-muted: #52606d
--border: #cbd2d9
--accent: #155eef
--focus: #7c3aed
--warning: #9a6700
--danger: #b42318
--observed-edge: #344054
--inferred-edge: #667085
```

Focus uses a visible 3 px outline with 2 px offset. Selection uses outline/shape as well as color. Dark appearance may follow `prefers-color-scheme` while preserving readable contrast and non-color distinctions.

## Deterministic graph layout

Coordinate convention: each node's `x` and `y` are its top-left world coordinates.

Constants:

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

Each subnet owns a separate expandable vertical lane. Gateway appears first. Devices use three columns by default and four columns when a subnet has more than 30 devices.

For `column_count` device columns:

```text
device_grid_right = device_start_x + (column_count - 1) * column_stride + node_width
upstream_x = max(minimum_upstream_x, device_grid_right + horizontal_gap)
```

Disconnected components receive separate lanes. Fit-to-view adds 48 world units of padding.

Node tests must compare rectangle bounds and prove:

- deterministic coordinates;
- no overlap within a lane;
- no overlap between adjacent lanes;
- no device/upstream overlap for three- and four-column grids;
- stable results under input reordering.

## UI state machine

| State | Entry | Visible result | Actions | Focus/recovery |
|---|---|---|---|---|
| `BOOT` | script starts | application shell | none | status announced |
| `LOADING_PASSIVE` | protected passive POST starts | loading or stale graph | no passive or active duplicate start | focus remains on trigger |
| `PASSIVE_READY` | passive success | graph, timestamp, refreshed capabilities | refresh, discover, export, select | trigger regains focus |
| `PARTIAL_READY` | coherent partial | graph and warnings | same as ready | warnings announced |
| `EMPTY_READY` | no neighbor devices | local structure and explanation | refresh, discover, export | empty heading focusable |
| `ACTIVE_CONFIRM` | discover selected | target and timeout dialog | confirm/cancel | modal focus and return |
| `ACTIVE_RUNNING` | active POST starts | progress and stale prior graph | no passive or active duplicate start | progress announced once |
| `ACTIVE_READY` | active success | merged graph | refresh, rediscover, export | active trigger regains focus |
| `DEPENDENCY_UNAVAILABLE` | Nmap absent or fails at runtime | passive graph and recovery guidance | passive refresh/export | disabled reason visible; refresh rechecks Nmap |
| `VALIDATION_ERROR` | request invalid | summary and field errors | edit/cancel | summary then invalid field |
| `COLLECTION_CONFLICT` | server `409` from another client | prior graph and busy message | retry later | message announced |
| `REQUEST_ERROR` | timeout or request failure | prior graph retained | retry/refresh | recovery reachable |
| `UNSUPPORTED_PLATFORM` | collection unavailable | explanatory state | health/capability details | heading focused |

Pointer pan, bounded pointer-centered zoom, keyboard-selectable nodes/edges, Escape behavior, zoom/fit/reset buttons, reduced motion, 200% zoom usability, and no page-level horizontal overflow are required.

## Code documentation policy

Comments and docstrings explain non-obvious contracts rather than restating syntax. Critical documented boundaries are:

- approved command shape, environment, deadlines, output limits, and process cleanup;
- parser input assumptions, partial-row handling, and whole-source failure conditions;
- Phase A/Phase B ownership and cross-owner target preservation;
- post-parser Nmap evidence validation;
- observed versus inferred topology and deterministic snapshot identifiers;
- HTTP Host/origin protection, collection-lock release, static allowlist, and atomic publication;
- reducer operation ownership, stale response rejection, focus recovery, safe DOM/SVG creation, address-union arithmetic, and lane layout;
- deployment allowlist, current-user limits, atomic replacement, rollback, health checks, and log retention.

Public models, parsers, orchestration functions, deployment actions, and regression stages have concise Python docstrings. Frontend pure-state and DOM owners use JSDoc or section comments at the same material boundaries. `scripts/check.py` statically enforces documentation for the critical owners without requiring comments on obvious assignments.

## Testing design

### Python

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

Coverage includes typed commands, Nmap resolution, XML parsing, IPv4/MAC and effective-target evidence validation, Phase A/B validation, interface-evidence failure classification, exact containment boundaries, overlapping local-owner preservation, strict macOS route parsing, malformed four-column route rejection, topology invariants, protected POST routes, read-only GETs, Host/origin checks, concurrency, snapshot preservation, export, static containment, headers, per-user deployment configuration, deployment runtime allowlisting, and repository hygiene.

### Frontend logic

```text
node --test tests/frontend/core.test.mjs
```

Coverage includes UI transitions, passive/active interleaving denial, stale completion rejection, dependency unavailable-to-available recovery, API errors, target presentation, deterministic coordinates, rectangle overlap, dynamic upstream position, compact mode, sorting, selection, and export filename.

### Full regression

```text
python3 scripts/check.py
```

Full mode requires compile checks, metadata parsing, Python tests, code-documentation guards, contract consistency guards, deployment guards, asset/CSP scans, Node tests, and tracked-path hygiene. Missing Node fails full mode. A Python-only developer mode is not full evidence.

## Separate runtime acceptance

Formal project acceptance later requires exact-revision evidence from supported macOS for startup, current-user LaunchAgent install/update/status/restart/uninstall and rollback, health/capabilities, protected passive refresh, read-only topology/export, invalid Host/origin rejection, Nmap-unavailable and restored-Nmap recovery, one authorized bounded active discovery, timeout behavior, cross-client collection conflict, browser interactions, keyboard/focus, reduced motion, 200% zoom, and representative tunnel/partial/empty cases.

## Privacy and operational limits

Topology remains in process memory unless downloaded. No upload, automatic persistence, annotation storage, DNS enrichment, or vendor lookup occurs.

LaunchAgent logs remain in the current user's Library unless explicitly purged during uninstall. They are runtime artifacts and must not be committed.

Results depend on current routing, ARP state, response behavior, Wi-Fi isolation, VPNs, sleeping devices, filters, and permissions. The UI and README must keep these limitations visible.
