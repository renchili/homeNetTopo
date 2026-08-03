# Home Net Topology

Home Net Topology (`homeNetTopo`) is a planned local-first macOS tool that collects network evidence visible from the current Mac, infers a best-effort logical topology, and renders it as an interactive local web page.

## Repository status

**Bootstrap only.** This revision contains project rules, product metadata, architecture, API design, implementation planning, and decision records. It does not yet contain a runnable server, discovery implementation, web interface, or test suite.

Do not treat the design documents as executed behavior or runtime evidence.

## Intended first release

The first implementation is expected to:

- read macOS interfaces and addresses;
- read routes and identify gateways;
- read the ARP or neighbor cache;
- optionally run bounded Nmap host discovery after an explicit user action;
- build nodes and edges with evidence and confidence;
- distinguish observed facts from inferred relationships;
- serve a repository-owned HTML, CSS, JavaScript, and SVG interface on `127.0.0.1`;
- support pan, zoom, selection, details, warnings, refresh, and JSON export;
- work without a cloud account, telemetry, or external frontend CDN.

## Important limitation

A single Mac cannot prove the entire physical network. Hidden switches, VLANs, wireless infrastructure, isolated clients, sleeping devices, filtered responses, VPN paths, and networks behind other routers may be incomplete or invisible.

The product must present inferred links as inference rather than certainty.

## Safety and privacy defaults

- The local service binds to loopback by default.
- Loading the page performs passive collection only.
- Active discovery requires a separate action.
- Active targets are limited to eligible private IPv4 networks visible on local interfaces.
- The initial design limit is 1024 addresses per active request.
- The default active mode is host discovery only.
- Network results are not uploaded or automatically persisted.
- Real local network identifiers must not be committed to fixtures or documentation.

## Planned architecture

```text
server.py                 loopback HTTP server and static-file boundary
homenettopo/              macOS discovery, parsing, validation, and topology logic
web/                      local browser interface and assets
tests/                    deterministic parser, API, topology, and security tests
fixtures/                 sanitized macOS command-output fixtures
docs/                     design, API contract, implementation plan, and decision register
AGENT.md                  project-specific repository guidance
metadata.json             compact product metadata
```

This layout is a design target, not an implementation claim. See [docs/design.md](docs/design.md) for ownership and flow details.

## Documentation

- [Project-specific rules](AGENT.md)
- [Architecture and interaction design](docs/design.md)
- [Implementation plan and requirement ledger](docs/plan.md)
- [Planned local API contract](docs/api-spec.md)
- [Decisions and open questions](docs/questions.md)
- [Product metadata](metadata.json)

## Intended operator flow

Once implementation files exist, the expected operator flow is:

1. run the local server with Python 3 on macOS;
2. open the loopback URL in a browser;
3. inspect the passive topology snapshot;
4. optionally install Nmap and explicitly request bounded host discovery;
5. inspect evidence and confidence for nodes and edges;
6. export JSON locally when needed.

Exact commands will be added only when matching scripts and source are committed.

## Development and verification status

At this bootstrap revision:

- source implementation: not present;
- automated tests: not present;
- local runtime checks: not run;
- browser checks: not run;
- CI workflows: not present;
- release artifacts: not present.

Future verification claims must identify the exact commit and the commands or evidence used.

## Contribution constraints

Before editing, read `AGENTS.md`, `AGENT.md`, and the task-routed workflow under `skills/`. Keep implementation, tests, documentation, and security boundaries consistent. Do not add generated runtime inventories, local logs, caches, or real network data to source control.
