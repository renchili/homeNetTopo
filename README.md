# Home Net Topology

Home Net Topology (`homeNetTopo`) is a planned local-first macOS tool that collects network evidence visible from the current Mac, infers a best-effort logical topology, and renders it as an interactive local web page.

## Repository status

**Bootstrap only.** This revision contains project rules, product metadata, architecture, API design, implementation planning, and decision records. It does not yet contain a runnable server, discovery implementation, web interface, test suite, regression script, or release artifact.

Do not treat planning documents as implemented behavior or runtime evidence.

## Intended first release

The first implementation is planned to:

- run on macOS with Python 3.10 or newer;
- read `/sbin/ifconfig -a`, `/usr/sbin/netstat -rn -f inet`, and `/usr/sbin/arp -an` through typed approved command constructors;
- optionally run bounded Nmap `-sn -n` host discovery after explicit confirmation;
- limit active requests to at most 32 eligible private IPv4 networks and 1024 unique addresses;
- build nodes and edges with source evidence, warnings, and confidence;
- distinguish observed facts from inferred relationships;
- serve repository-owned HTML, CSS, JavaScript, ES modules, and SVG on `127.0.0.1:8765`;
- validate loopback Host values and protect active POST requests with same-origin controls;
- serialize one passive or active collection at a time and preserve the previous snapshot on failure;
- support deterministic layout, pan, zoom, fit, reset, selection, details, warnings, refresh, and JSON export;
- work without cloud accounts, telemetry, persistent inventories, runtime Node, npm packages, or external frontend assets.

## First-release exclusions

The first release does not include:

- reverse-DNS enrichment;
- online hostname or MAC-vendor lookup;
- user annotations or persistent device naming;
- snapshot persistence across process restarts;
- configurable LAN bind;
- active IPv6 discovery;
- port, service, vulnerability, credential, or operating-system scanning.

Names already present in approved local command output may be displayed with their evidence source.

## Important limitation

A single Mac cannot prove the entire physical network. Hidden switches, VLANs, wireless infrastructure, isolated clients, sleeping devices, filtered responses, VPN paths, and networks behind other routers may be incomplete or invisible.

The product must present inferred links as inference rather than certainty.

## Safety and privacy defaults

- The local service binds to IPv4 loopback only.
- Loading or passively refreshing the page never invokes Nmap.
- Active discovery requires a separate confirmation flow.
- Active targets are limited to eligible private IPv4 networks on non-tunnel local interfaces.
- The active timeout defaults to 30 seconds and is bounded from 1 to 120 seconds.
- The JSON request body limit is 16 KiB.
- Only one passive or active collection may run at a time.
- `refresh=false` and export never trigger collection.
- Network results are not uploaded or automatically persisted.
- Real local network identifiers must not be committed to fixtures or documentation.

## Planned architecture

```text
server.py                         loopback HTTP server, API, collection lock, and static boundary
homenettopo/                      command, parser, validation, model, and topology modules
web/index.html                    accessible page structure
web/core.mjs                      pure UI state and deterministic layout logic
web/app.js                        browser, SVG, fetch, input, and focus adapter
web/styles.css                    visual tokens and responsive behavior
tests/                            Python deterministic tests
tests/frontend/core.test.mjs      Node built-in tests for pure frontend logic
fixtures/                         sanitized macOS command-output fixtures
scripts/check.py                  full static regression entrypoint
docs/                             design, API contract, implementation plan, and decisions
AGENT.md                          project-specific repository guidance
metadata.json                     compact product metadata and fixed limits
```

This layout is a design target, not an implementation claim.

## Documentation

- [Project-specific rules](AGENT.md)
- [Architecture and interaction design](docs/design.md)
- [Implementation plan and requirement ledger](docs/plan.md)
- [Planned local API contract](docs/api-spec.md)
- [Decisions and deferred questions](docs/questions.md)
- [Product metadata](metadata.json)

## Intended operator flow

Once matching implementation files exist, the expected operator flow is:

1. start the local server with Python 3.10+ on macOS;
2. open the loopback URL;
3. inspect a fresh passive topology snapshot;
4. optionally install Nmap and explicitly request bounded host discovery;
5. inspect evidence, confidence, source warnings, and topology limitations;
6. export the latest in-memory snapshot as JSON.

Exact startup, test, and regression commands will be documented as executable instructions only when their source owners exist.

## Planned verification entrypoints

The implementation plan fixes these future commands:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

Node 20+ is a development-only test runtime and is not required to run the product. These commands are plans, not evidence that tests currently exist or pass.

## Development and verification status

At this bootstrap revision:

- source implementation: not present;
- automated tests: not present;
- local runtime checks: not run;
- browser checks: not run;
- real network checks: not run;
- CI workflows: not present;
- release artifacts: not present.

Future verification claims must identify the exact commit and the commands or evidence used.

## Contribution constraints

Before editing, read `AGENTS.md`, `AGENT.md`, and the task-routed workflow under `skills/`. Keep implementation, tests, documentation, public limits, browser request boundaries, and privacy behavior consistent. Do not add generated runtime inventories, local logs, caches, real network data, packet captures, or exported snapshots to source control.
