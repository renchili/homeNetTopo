# HomeNetTopo Project Guidance

## Project identity

`homeNetTopo` is a local-first macOS application that discovers network evidence visible from the current Mac, infers a best-effort logical topology, and renders the result as a local interactive web page.

The project must describe inferred links honestly. A single endpoint cannot prove hidden switch ports, VLAN boundaries, wireless controller relationships, firewall-internal segments, or devices that do not respond to local discovery.

## Current product scope

The intended first release has two surfaces:

1. a local discovery service that reads macOS network state and optionally performs bounded host discovery;
2. a browser interface served only on loopback that visualizes devices, subnets, gateways, interfaces, evidence, and inference confidence.

The implementation must remain useful without cloud services, accounts, telemetry, persisted network inventories, or externally hosted frontend assets.

The first release does not include user annotations, persistent naming, online vendor lookup, reverse-DNS enrichment, active IPv6 discovery, or remote multi-user hosting. Those capabilities require an explicit future requirement and coordinated changes to the model, API, UI, privacy rules, and tests.

## Runtime and platform constraints

- Primary platform: macOS.
- Minimum runtime: Python 3.10.
- Backend runtime dependencies: Python standard library unless a dependency is explicitly justified and documented.
- Local HTTP bind: `127.0.0.1` by default.
- Default port: `8765`.
- Frontend: repository-owned static HTML, CSS, and JavaScript; no required CDN.
- Optional discovery dependency: Nmap, invoked only for host discovery by default.
- The normal passive path must not require administrator privileges.
- Shell commands and parsers must account for macOS command formats, including `ifconfig`, `netstat`, `arp`, and `utun` interface output.

## Approved command boundary

The backend must not expose a generic command runner to HTTP or frontend callers.

The first release may execute only these command families through typed constructors and argument arrays:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
<resolved-nmap-path> -sn -n --max-retries 1 --host-timeout <bounded-value> <validated-targets...>
```

Requirements:

- never invoke a shell;
- use absolute paths for macOS system tools;
- resolve Nmap from documented Homebrew or PATH locations, canonicalize the path, and verify that it is executable;
- accept only validated network arguments from the active-discovery validator;
- apply timeouts and captured-output limits;
- terminate timed-out child processes and apply a bounded kill grace period;
- normalize errors before they reach the browser.

## Security and scanning boundary

- Passive discovery is the default source of truth.
- Loading the page may read local operating-system state but must not invoke Nmap or probe target hosts.
- Active discovery must be explicit in the UI and API.
- The default active operation is Nmap host discovery only; do not enable port, service, vulnerability, credential, or internet-wide scanning.
- Active discovery is limited to private IPv4 networks visible on eligible local interfaces.
- Reject loopback, link-local, multicast, unspecified, public, unrelated private, tunnel-only, and oversized target ranges.
- The hard combined address limit is 1024 addresses per request.
- The maximum number of target networks is 32.
- The active request timeout defaults to 30 seconds and must be between 1 and 120 seconds.
- The maximum JSON request body is 16 KiB.
- Captured stdout is limited to 2 MiB and stderr to 64 KiB per command.
- Passive commands time out after 5 seconds.
- Do not expose the service on LAN or public interfaces in the first release.
- Runtime scan results, local addresses, MAC addresses, hostnames, logs, and caches must not be committed.

## Browser request boundary

Every HTTP request must pass a Host allowlist tied to the actual loopback bind and port. The first release accepts only loopback-origin host values such as the configured `127.0.0.1:<port>` and `localhost:<port>` forms.

State-changing discovery requests must also require:

- `Content-Type: application/json`;
- `X-HomeNetTopo-Request: 1`;
- a matching loopback `Origin` when the header is present;
- rejection of cross-site `Sec-Fetch-Site` values when the header is present.

Do not emit permissive CORS headers. Do not implement an API-wide `OPTIONS` success path. Tests must cover invalid Host, cross-origin requests, missing custom request header, and DNS-rebinding-style Host values.

## Collection and concurrency model

- At most one collection operation may run at a time, whether passive or active.
- A second collection request must fail immediately with `409 collection_in_progress`; it must not wait, merge, or start another subprocess.
- `GET /api/v1/topology` performs a passive refresh by default.
- `GET /api/v1/topology?refresh=false` returns the latest in-memory snapshot without collecting; it returns `404 not_found` when no snapshot exists.
- `GET /api/v1/topology/export` never collects and returns `404 not_found` when no snapshot exists.
- A successful or coherent partial collection replaces the latest snapshot atomically.
- A failed collection preserves the previous snapshot.
- Snapshots have no automatic TTL; clients determine freshness from `collected_at`.

## Topology and evidence model

Every node and edge must carry enough provenance to distinguish observed facts from inference.

Required first-release evidence categories:

- interface configuration;
- IPv4 routing table;
- ARP/neighbor cache;
- optional Nmap host discovery;
- deterministic address-membership and route inference.

Names already present in approved command output may be retained as evidence. The first release must not perform separate reverse-DNS queries or online name/vendor lookups.

Minimum node categories:

- local host;
- local interface;
- subnet;
- default or route-specific gateway;
- discovered device;
- upstream or unknown network boundary.

Edges derived directly from local configuration may be marked observed. Device-to-subnet and upstream relationships inferred from address membership or routing must be marked inferred. Confidence and evidence labels must be visible in the API model and UI.

## Ownership and planned layout

Use one repository root. Do not create a nested replacement project.

Planned owners:

```text
server.py                         local HTTP entrypoint and static-file boundary
homenettopo/commands.py           approved command specifications and execution
homenettopo/interfaces.py         macOS interface parsing
homenettopo/routes.py             IPv4 route parsing
homenettopo/neighbors.py          ARP parsing
homenettopo/discovery.py          active-target validation and Nmap adapter
homenettopo/models.py             JSON-serializable domain model
homenettopo/topology.py           topology construction and provenance
web/index.html                    page structure
web/core.mjs                      pure UI state, API mapping, and layout logic
web/app.js                        DOM, SVG, input, and network adapter
web/styles.css                    product visual rules and responsive layout
tests/                            Python deterministic tests
tests/frontend/core.test.mjs      Node built-in tests for pure frontend logic
fixtures/                         sanitized synthetic command-output fixtures
scripts/check.py                  full static regression entrypoint
docs/                             design, API contract, plan, and decisions
README.md                         operator setup and usage
metadata.json                     compact product metadata
```

If implementation evidence establishes a better existing owner, update this guidance and all affected documentation together rather than creating parallel modules.

## API contract constraints

The API is local and JSON-based. It must expose separate passive snapshot and active-discovery operations so loading the page cannot silently trigger target-host probes.

Expected capabilities are defined in `docs/api-spec.md`. Error responses must be structured, must not leak command internals or filesystem details, and must distinguish validation failure, origin/Host rejection, collection conflict, missing optional dependency, command failure, timeout, unsupported platform, and missing snapshot.

## Web interface constraints

The interface must:

- render without external network access;
- show when data was collected and whether active discovery ran;
- distinguish observed and inferred links visually and textually;
- expose node details, addresses, interface names, evidence, and confidence;
- support pan, zoom, fit, reset, node/edge selection, and keyboard focus;
- provide loading, empty, partial-result, missing-Nmap, validation, timeout, collection-conflict, request-error, and unsupported-platform states;
- avoid presenting the graph as a complete physical topology;
- export the current server snapshot without uploading data;
- remain usable at 200 percent browser zoom and under reduced-motion preferences.

The graph uses a deterministic left-to-right layered layout. Visual and interaction rules are owned by `docs/design.md` and `docs/plan.md` until matching source exists.

## Validation ownership

Static implementation work must define tests for:

- macOS interface parsing, including VPN/tunnel formats;
- route and gateway parsing;
- ARP parsing and incomplete entries;
- private-network target validation and exact address-count boundaries;
- approved command construction and executable resolution;
- command timeouts, output limits, and error normalization;
- topology deduplication, conflicts, evidence, and confidence;
- API method, Host, Origin, request-header, content-type, size, cache, concurrency, and error behavior;
- static-file traversal prevention, symlink containment, MIME handling, and security headers;
- frontend state reduction, API mapping, deterministic layout, and representative rendering contracts;
- keyboard, focus, non-gesture controls, and reduced-motion hooks.

The standard Python test command will be:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

Pure frontend logic tests will use the Node 20+ built-in test runner without npm packages:

```text
node --test tests/frontend/core.test.mjs
```

The full static regression owner is `scripts/check.py`, invoked with:

```text
python3 scripts/check.py
```

Production runtime does not require Node. Executed tests, browser checks, CI, and runtime scans must be reported only when there is direct evidence for the exact revision.

## Documentation rules

Documentation must clearly separate:

- implemented behavior;
- planned behavior;
- runtime and development dependencies;
- executed verification;
- known inference limits.

Do not claim complete physical-network reconstruction, reverse-DNS enrichment, user annotations, port scanning, operating-system fingerprinting, CI success, browser validation, or deployment success without matching implementation and evidence.

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
runtime JSON exports
scan logs
local host inventories
packet captures
```

Do not commit real local network identifiers in fixtures. Use documentation-reserved or clearly synthetic addresses and locally administered MAC values.

## Delivery reporting

Repository-work responses must include the branch, exact revision when available, files changed, rules loaded with identifiers, static inspection performed, commands or tests actually run, checks not run, and remaining gaps or risks.
