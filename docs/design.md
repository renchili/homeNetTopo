# HomeNetTopo Design

## Status

This document defines the intended first runnable implementation. It is a design contract, not evidence that the application already runs.

## Goals

- Discover IPv4 network facts visible from the current macOS host.
- Build a best-effort logical topology with explicit provenance and confidence.
- Serve an interactive local-only web page.
- Keep network data on the Mac and in process memory.
- Avoid mandatory third-party runtime and frontend dependencies.
- Make optional active host discovery bounded, visible, and separate from passive inspection.
- Provide deterministic implementation and test ownership.

## Non-goals

- Proving complete physical topology from one endpoint.
- Identifying switch ports, hidden VLANs, controller-managed wireless paths, or firewall-internal networks without additional evidence.
- Scanning public address space.
- Inspecting ports, services, vulnerabilities, credentials, or operating systems.
- Reverse-DNS, online hostname, or vendor enrichment.
- User annotations or persistent device naming.
- Active IPv6 discovery.
- Remote or multi-user hosting.

## Runtime and development environment

Production runtime:

- macOS;
- Python 3.10 or newer;
- Python standard library;
- repository-owned HTML, CSS, JavaScript, SVG, and ES modules;
- optional Nmap executable for active discovery.

Development-only frontend logic tests use Node 20 or newer and its built-in test runner. No npm packages are required. Production startup does not require Node.

## Surfaces

### Local discovery service

The service reads local operating-system state, validates optional discovery targets, invokes approved commands through typed argument constructors, normalizes results, constructs snapshots, and exposes JSON to the loopback browser client.

### Browser interface

The browser interface requests a passive snapshot on initial load. Active host discovery requires a separate dialog and explicit confirmation. It renders topology with local HTML, CSS, JavaScript, ES modules, and SVG.

## Module ownership

```text
server.py
  Creates the loopback HTTP server, validates browser request boundaries,
  routes API requests, serializes responses, serves web assets, owns the
  collection lock and latest snapshot, applies limits and security headers,
  and prevents path traversal.

homenettopo/commands.py
  Defines approved command specifications, resolves executable paths, invokes
  subprocesses without a shell, enforces timeout/output limits, terminates
  timed-out processes, and returns normalized results.

homenettopo/interfaces.py
  Parses `/sbin/ifconfig -a` output into interface and address facts.

homenettopo/routes.py
  Parses `/usr/sbin/netstat -rn -f inet` output into IPv4 route and gateway facts.

homenettopo/neighbors.py
  Parses `/usr/sbin/arp -an` output, including incomplete records.

homenettopo/discovery.py
  Calculates network eligibility, validates active requests, resolves Nmap,
  constructs the fixed host-discovery argument array, and parses host-up output.

homenettopo/models.py
  Defines validated JSON-serializable evidence, source status, network,
  node, edge, warning, active-discovery, and snapshot structures.

homenettopo/topology.py
  Deduplicates normalized evidence and creates topology nodes, edges,
  confidence, warnings, and deterministic ordering.

web/index.html
  Owns document structure and accessible control/dialog regions.

web/core.mjs
  Owns pure API mapping, state reduction, graph filtering, deterministic layout,
  selection helpers, and export filename logic.

web/app.js
  Owns fetch requests, DOM/SVG rendering, pointer/keyboard input, focus movement,
  dialog behavior, and file download initiation.

web/styles.css
  Owns product visual tokens, responsive layout, graph states, focus treatment,
  and reduced-motion behavior.

scripts/check.py
  Owns the repository-relative full static regression entrypoint.
```

Each responsibility has one primary owner. Changes to ownership require updates to this document, `AGENT.md`, `docs/plan.md`, tests, and README paths in the same change.

## Approved command model

The service does not accept arbitrary command names or argument lists from HTTP input.

Approved specifications:

```text
INTERFACES  /sbin/ifconfig -a
ROUTES      /usr/sbin/netstat -rn -f inet
NEIGHBORS   /usr/sbin/arp -an
DISCOVERY   <canonical-nmap-path> -sn -n --max-retries 1
            --host-timeout <timeout>s <validated-targets...>
```

Nmap resolution order:

1. explicit documented startup option, when supplied;
2. `/opt/homebrew/bin/nmap`;
3. `/usr/local/bin/nmap`;
4. `shutil.which("nmap")`.

The selected path is canonicalized with `realpath` and must reference an executable regular file. Homebrew symlinks are allowed only after canonicalization. The resolved path is reported as capability metadata without exposing unrelated filesystem data.

Command limits:

| Limit | Value |
|---|---:|
| Passive command timeout | 5 seconds |
| Active timeout default | 30 seconds |
| Active timeout range | 1–120 seconds |
| Child-process kill grace | 2 seconds |
| Captured stdout | 2 MiB |
| Captured stderr | 64 KiB |

On timeout, the runner terminates the child, waits up to the kill grace, then kills it if necessary. Truncated output is a normalized command failure unless the parser contract explicitly permits a partial warning.

## Passive collection flow

1. Confirm the runtime platform.
2. Acquire the single collection lock.
3. Run the interface command.
4. Run the IPv4 route command.
5. Run the ARP command.
6. Parse each source independently.
7. Normalize and deduplicate available evidence.
8. Construct a passive topology snapshot.
9. Atomically replace the latest snapshot when the result is complete or coherently partial.
10. Release the collection lock.

A failure in one passive source produces a source-status failure and warning when remaining evidence can form a coherent snapshot. Failure of all material passive sources returns `collection_failed` and preserves the previous snapshot.

No separate hostname, reverse-DNS, vendor, or online lookup occurs. Hostnames already present in approved command output may be retained with their source evidence.

## Active discovery flow

1. Validate HTTP Host and request-origin controls.
2. Parse a body no larger than 16 KiB.
3. Acquire the collection lock or return `409 collection_in_progress`.
4. Perform a fresh passive collection.
5. Calculate eligible non-tunnel private IPv4 networks.
6. Validate all requested networks, timeout, network count, and unique address count.
7. Resolve the Nmap executable.
8. Invoke the fixed Nmap host-discovery command.
9. Parse host-up records without port or service data.
10. Merge active evidence into the fresh passive snapshot.
11. Atomically replace the latest snapshot.
12. Release the collection lock.

Validation always completes before Nmap is invoked. A failed active operation preserves the previous snapshot; the intermediate passive result is not published as the active request result.

## Target validation

An active request must satisfy all conditions:

- body is valid JSON and no larger than 16 KiB;
- `networks` contains 1–32 strings;
- every item parses as a canonical IPv4 network;
- every target is private;
- no target is loopback, link-local, multicast, unspecified, public, or reserved-only documentation space;
- every target overlaps an eligible private IPv4 network assigned to a non-tunnel local interface;
- overlapping targets are collapsed before counting;
- the union contains no more than 1024 unique addresses;
- `timeout_seconds` is an integer from 1 through 120, defaulting to 30;
- only validated canonical CIDRs reach command construction.

Tunnel interface networks remain visible in passive topology but are not eligible active targets in the first release.

## Collection concurrency and snapshot lifecycle

The server owns one non-reentrant collection lock shared by passive and active operations.

- A second collection request returns `409 collection_in_progress` immediately.
- It does not wait, enqueue, merge, or spawn another child process.
- `GET /api/v1/topology` and `refresh=true` perform a passive collection.
- `refresh=false` returns the current snapshot without collection or `404 not_found` when absent.
- Export returns the current snapshot without collection or `404 not_found` when absent.
- Complete and coherent partial snapshots replace the previous snapshot atomically.
- Failed collections leave the previous snapshot unchanged.
- Snapshots have no automatic TTL and expose `collected_at` for freshness decisions.

## Browser request boundary

The service validates the request before routing.

### Host validation

Accepted Host values are derived from the configured loopback port:

```text
127.0.0.1:<port>
localhost:<port>
```

A missing, malformed, non-loopback, alternate-domain, or DNS-rebinding-style Host returns `400 invalid_host`.

### State-changing request validation

`POST /api/v1/discover` requires:

- valid Host;
- `Content-Type: application/json`;
- `X-HomeNetTopo-Request: 1`;
- when `Origin` is present, an exact origin matching an accepted loopback Host;
- when `Sec-Fetch-Site` is present, value `same-origin` or `none`.

Cross-site or mismatched-origin requests return `403 cross_origin_request`. The server emits no `Access-Control-Allow-Origin` header and does not accept API preflight as an alternative path.

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

`observed` means the relationship is directly supported by collected local configuration. It does not prove cabling or switching paths.

Confidence values:

- `high`: direct local configuration or corroborated observations;
- `medium`: one reliable observation plus deterministic routing or membership inference;
- `low`: incomplete or heuristic association retained for inspection.

## Graph construction rules

- One local-host node represents the current Mac.
- Each interface connects the local host to assigned subnet nodes.
- A gateway joins a subnet only when route and address evidence support the relationship.
- A neighbor joins a subnet through explicit address-membership inference.
- An upstream boundary may connect to a gateway when the next network is not locally observable.
- Compatible device evidence is merged conservatively using canonical address and MAC relationships.
- A gateway may merge with a discovered device when evidence is compatible.
- Conflicting MAC or hostname evidence remains visible as a warning.
- Active evidence supplements rather than erases passive evidence.
- All output collections use deterministic sorting.
- Inferred edges never become observed physical links.

## API behavior summary

| Endpoint | Collection | Latest snapshot effect |
|---|---|---|
| `GET /api/v1/health` | none | none |
| `GET /api/v1/capabilities` | platform and executable checks only | none |
| `GET /api/v1/topology` | passive by default | atomically replaces on success/partial success |
| `GET /api/v1/topology?refresh=false` | none | returns current or `404` |
| `POST /api/v1/discover` | passive plus validated active | atomically replaces on success |
| `GET /api/v1/topology/export` | none | downloads current or `404` |

The exact schemas and status codes are owned by `docs/api-spec.md`.

## Static-file boundary

- Static content is served only from the canonical `web/` root.
- URL decoding occurs exactly once before validation.
- Reject parent segments, encoded traversal, NUL bytes, separator ambiguity, directory requests, and directory listing.
- Resolve candidate paths canonically and require containment under the canonical web root.
- Reject symlink escapes.
- Serve only regular files with an explicit MIME map.
- Unknown paths return structured API errors for API routes and minimal HTML/text `404` responses for static routes.
- Apply the documented security headers to HTML, static assets, and API responses where applicable.

## Frontend information architecture

```text
header
  product title
  snapshot timestamp and mode
  passive refresh
  active discovery
  export JSON
status region
  platform/capability status
  limitation notice
  partial and source warnings
main
  graph toolbar
  SVG topology canvas
  selected-item details panel
active discovery dialog
  eligible networks
  unique address total
  timeout field
  confirm/cancel
```

## Visual system

Typography uses the system UI stack. Base text size is 16 px and the minimum supporting text size is 13 px.

Spacing scale:

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

Dark appearance may follow `prefers-color-scheme`, but both modes must preserve readable contrast and non-color distinctions. Focus uses a visible 3 px outline with 2 px offset. Selected items use outline and shape treatment, not color alone.

## Deterministic graph layout

The first release uses a left-to-right layered layout in world coordinates.

Columns:

```text
local host          x = 0
interfaces          x = 240
subnets             x = 520
gateways/devices    x = 820 and onward
upstream boundaries x = 1160
```

Rules:

- node box: 180 × 72 world units;
- horizontal gap: at least 48 units;
- vertical gap: at least 28 units;
- interfaces and subnets are sorted by interface name then CIDR;
- each subnet owns a vertical lane;
- gateway appears first in its subnet lane;
- devices use a deterministic grid, three columns by default;
- lanes expand vertically to prevent node overlap;
- more than 30 devices in one subnet uses four-column compact mode with shortened canvas labels and full details text;
- disconnected components receive separate lanes after connected components;
- fit-to-view includes 48 units of world padding;
- layout is pure data-to-coordinate logic in `web/core.mjs` and is covered by Node tests.

## Graph interaction

- Initial render fits all nodes.
- Background pointer drag pans.
- Wheel or trackpad input zooms around the pointer with bounded scale.
- Zoom-in, zoom-out, fit, and reset controls provide non-gesture alternatives.
- Nodes and selectable edges are keyboard focus targets with accessible names.
- Enter or Space selects the focused item.
- Escape clears selection or closes the active dialog.
- Observed edges are solid; inferred edges are dashed and described textually in details.
- Reduced-motion preference disables nonessential transitions.
- Graph zoom does not cause horizontal page overflow.
- Dialog and controls remain usable at 200 percent browser zoom.

## UI state machine

| State | Entry | Visible result | Actions | Focus and recovery |
|---|---|---|---|---|
| `BOOT` | script starts | application shell and loading status | none | status is announced |
| `LOADING_PASSIVE` | initial or manual refresh | previous graph marked stale or loading placeholder | no duplicate refresh | focus stays on trigger |
| `PASSIVE_READY` | complete passive snapshot | graph, timestamp, passive mode | refresh, discover, export, select | trigger regains focus after update |
| `PARTIAL_READY` | partial snapshot | graph and warning summary | same as ready | warning is announced |
| `EMPTY_READY` | no neighbor devices | local structure and explanation | refresh, discover, export | empty heading is focusable |
| `ACTIVE_CONFIRM` | discover selected | eligible targets, count, timeout | confirm/cancel | focus trapped in dialog and restored on close |
| `ACTIVE_RUNNING` | confirmed | progress with previous graph stale | duplicate submit disabled | progress announced once |
| `ACTIVE_READY` | success | merged graph and active metadata | refresh, rediscover, export | active trigger regains focus |
| `DEPENDENCY_UNAVAILABLE` | Nmap absent | passive graph and local install guidance | refresh/export | disabled reason is visible |
| `VALIDATION_ERROR` | request rejected | summary and field error | edit/cancel | error summary then invalid field |
| `COLLECTION_CONFLICT` | `409` | previous graph and busy message | retry after operation completes | message announced |
| `REQUEST_ERROR` | request/timeout/parse failure | prior graph retained when available | retry or passive refresh | recovery controls remain reachable |
| `UNSUPPORTED_PLATFORM` | collection unsupported | explanatory non-graph state | health/details | main heading receives focus |

## Testing design

### Python tests

Use `unittest` and synthetic fixtures. Automated tests must not inspect the test machine's actual LAN.

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

Coverage includes parsers, validators, approved command construction, executable resolution, timeout/output behavior, topology invariants, server routing, Host/Origin checks, cache semantics, concurrency, export, static containment, headers, and repository hygiene.

### Frontend logic tests

Pure UI logic resides in `web/core.mjs` and is tested with Node's built-in runner:

```text
node --test tests/frontend/core.test.mjs
```

Tests cover state transitions, API-error mapping, eligible-target calculations, deterministic layout, overlap prevention, compact mode, sorting, selection helpers, and export filename logic.

### Full static regression

```text
python3 scripts/check.py
```

The script runs repository-relative compile checks, Python tests, JSON parsing, documentation/path consistency guards, external-asset scans, and Node frontend tests when Node 20+ is available. Missing Node is reported as `NOT RUN` and causes a non-zero result in release/acceptance mode; a documented Python-only developer mode may skip it without claiming full regression.

### Separate real evidence

Formal acceptance later requires exact-revision evidence from a supported Mac for service startup, API flows, browser interactions, keyboard/focus behavior, 200-percent zoom, Nmap-unavailable behavior, one authorized bounded active discovery, and representative tunnel/partial/empty states.

## Privacy and operational limits

Topology data stays in process memory unless the user downloads an export. The first release does not upload results, persist snapshots, store annotations, perform reverse DNS, or query online vendor services.

Results depend on routing state, ARP cache state, device response behavior, Wi-Fi isolation, VPNs, sleep states, local filters, configured DNS names already present in command output, and permissions. The UI and README must keep these limitations visible.
