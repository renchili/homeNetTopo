# Home Net Topology

Home Net Topology (`homeNetTopo`) is a planned local-first macOS tool that collects network evidence visible from the current Mac, infers a best-effort logical topology, and renders it as an interactive local web page.

## Repository status

**Bootstrap only.** This revision contains project rules, metadata, architecture, API design, implementation planning, and decisions. It does not yet contain a runnable server, discovery implementation, web interface, tests, regression script, or release artifact.

Planning documents are not runtime evidence.

## Intended first release

The planned implementation will:

- run on macOS with Python 3.10 or newer;
- read `/sbin/ifconfig -a`, `/usr/sbin/netstat -rn -f inet`, and `/usr/sbin/arp -an` through typed command specifications;
- expose only read-only GET endpoints and protected POST endpoints for collection;
- perform passive collection through `POST /api/v1/topology/refresh`;
- optionally run Nmap XML host discovery through `POST /api/v1/discover` after explicit confirmation;
- restrict every active target to a network equal to or contained by an eligible non-tunnel local network;
- reject supernets, partial overlaps, adjacent networks, tunnel-only networks, unrelated private ranges, and public/special ranges;
- limit requests to 32 networks and 1024 unique addresses;
- distinguish a total Nmap operation deadline from a fixed five-second Nmap per-host timeout;
- build topology nodes and edges with evidence, warnings, observed/inferred markers, and confidence;
- serve repository-owned HTML, CSS, JavaScript, ES modules, and SVG on `127.0.0.1:8765`;
- serialize collection with one lock and preserve the previous snapshot on failure;
- render deterministic non-overlapping graph lanes with dynamic upstream positioning;
- support pan, zoom, fit, reset, keyboard selection, details, warnings, refresh, and JSON export;
- work without cloud accounts, telemetry, persistence, production Node, npm packages, CDNs, or external frontend assets.

## Endpoint model

Read-only endpoints never execute collection commands:

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

Both collection POSTs require JSON, `X-HomeNetTopo-Request: 1`, an accepted loopback Host, and same-origin browser metadata when those headers are present.

## Active discovery plan

The fixed Nmap command shape is:

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <validated-targets...>
```

Nmap XML stdout is parsed with the Python standard library. Port, service, OS, script, and name-resolution data are not used.

Validation has two phases:

1. request syntax and absolute safety checks before lock or commands;
2. local-network containment checks after fresh passive collection.

Nmap is not resolved or invoked until both phases pass.

## Fixed limits

- JSON body: 16 KiB maximum.
- Requested networks: 1–32.
- Unique active addresses: at most 1024.
- Active-operation timeout: default 30 seconds, range 5–120 seconds.
- Nmap per-host timeout: fixed 5 seconds.
- Passive command timeout: 5 seconds.
- Captured stdout: 2 MiB.
- Captured stderr: 64 KiB.
- Process terminate/kill grace: 2 seconds.

## First-release exclusions

The first release does not include:

- reverse-DNS enrichment;
- online hostname or MAC-vendor lookup;
- user annotations or persistent device naming;
- snapshot persistence across restarts;
- configurable LAN bind;
- active IPv6 discovery;
- port, service, vulnerability, credential, or operating-system scanning.

Names already present in approved command output may be displayed with source evidence.

## Important limitation

A single Mac cannot prove an entire physical network. Hidden switches, VLANs, wireless infrastructure, isolated clients, sleeping devices, filtered responses, VPN paths, and networks behind other routers may be incomplete or invisible.

The product must present inferred relationships as inference rather than certainty.

## Safety and privacy defaults

- The service binds to IPv4 loopback only.
- All GET routes are read-only.
- Initial page load explicitly triggers protected passive refresh; it never invokes Nmap.
- Active discovery requires a separate confirmation flow.
- One passive or active collection may run at a time.
- Failed operations preserve the previous snapshot.
- Topology data remains in process memory unless downloaded by the user.
- No results are uploaded or automatically persisted.
- Real local addresses, hostnames, MACs, logs, and exports must not be committed.

## Planned architecture

```text
server.py                         loopback HTTP/API, browser boundary, lock, snapshot, static delivery
homenettopo/                      commands, parsers, validation, XML discovery, models, topology
web/index.html                    accessible page structure
web/core.mjs                      pure UI state and deterministic graph layout
web/app.js                        fetch, DOM/SVG, input, focus, and download adapter
web/styles.css                    visual tokens and responsive behavior
tests/                            deterministic Python tests
tests/frontend/core.test.mjs      Node built-in frontend logic tests
fixtures/                         sanitized macOS and Nmap XML fixtures
scripts/check.py                  full static regression entrypoint
docs/                             design, API, plan, and decisions
AGENT.md                          project-specific constraints
metadata.json                     compact fixed contract
```

This is a design target, not an implementation claim.

## Documentation

- [Project guidance](AGENT.md)
- [Architecture and interaction design](docs/design.md)
- [Implementation plan and requirement ledger](docs/plan.md)
- [Local API contract](docs/api-spec.md)
- [Resolved and deferred decisions](docs/questions.md)
- [Product metadata](metadata.json)

## Intended operator flow

After matching source exists:

1. start the local Python service on macOS;
2. open the loopback URL;
3. let the page issue a protected passive refresh;
4. inspect the latest logical topology and source warnings;
5. optionally install Nmap and confirm bounded discovery;
6. inspect evidence and confidence;
7. download the latest snapshot as JSON.

Exact startup options will be documented as executable instructions only when their source exists.

## Planned verification entrypoints

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

Node.js 20+ is development-only. Full regression requires both Python and Node stages. These commands are planned, not evidence that tests currently exist or pass.

## Current verification status

- Source implementation: not present.
- Automated tests: not present.
- Regression script: not present.
- Runtime checks: not run.
- Browser checks: not run.
- Real-network checks: not run.
- CI workflows: not present.
- Release artifacts: not present.

Future verification claims must identify the exact commit and evidence used.

## Contribution constraints

Before editing, read `AGENTS.md`, `AGENT.md`, the routed workflow under `skills/`, and `docs/plan.md`. Keep source, tests, API behavior, graph layout, limits, security boundaries, metadata, and documentation consistent. Do not commit generated inventories, runtime exports, logs, caches, packet captures, or real network identifiers.
