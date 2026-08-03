# HomeNetTopo Project Guidance

## Project identity

`homeNetTopo` is a local-first macOS application that discovers the network visible from the current Mac, infers a best-effort logical topology, and renders the result as a local interactive web page.

The project must describe inferred links honestly. A single endpoint cannot prove hidden switch ports, VLAN boundaries, wireless controller relationships, firewall-internal segments, or devices that do not respond to local discovery.

## Current product scope

The intended first release has two surfaces:

1. a local discovery service that reads macOS network state and optionally performs bounded host discovery;
2. a browser interface served only on loopback that visualizes devices, subnets, gateways, interfaces, evidence, and inference confidence.

The implementation must remain useful without cloud services, accounts, telemetry, or externally hosted frontend assets.

## Runtime and platform constraints

- Primary platform: macOS.
- Primary runtime: Python 3 using the standard library unless a dependency is explicitly justified and documented.
- Local HTTP bind: `127.0.0.1` by default.
- Frontend: repository-owned static HTML, CSS, and JavaScript; no required CDN.
- Optional discovery dependency: Nmap, invoked only for host discovery by default.
- The project must not require administrator privileges for its normal read-only discovery path.
- Shell commands and parsers must account for macOS command formats, including `ifconfig`, `route`, `arp`, and `utun` interface output.

## Security and scanning boundary

- Passive discovery is the default source of truth where available.
- Active discovery must be explicit in the UI or request path.
- The default active operation is host discovery only; do not enable port, service, vulnerability, credential, or internet-wide scanning by default.
- Active discovery is limited to private IPv4 networks visible on local interfaces.
- Reject loopback, link-local, multicast, unspecified, public, and oversized target ranges.
- Apply a configurable hard address-count limit; the initial default is 1024 addresses per request.
- Never construct shell commands through string interpolation. Use argument arrays and validate every network target before invocation.
- Do not expose the local service on LAN or public interfaces unless a future explicit requirement defines authentication, authorization, CSRF protection, and deployment controls.
- Runtime scan results, local addresses, MAC addresses, hostnames, logs, and caches must not be committed.

## Topology and evidence model

Every node and edge must carry enough provenance to distinguish observed facts from inference.

Minimum node categories:

- local host;
- local interface;
- subnet;
- default or route-specific gateway;
- discovered device;
- upstream or unknown network boundary.

Minimum evidence categories:

- interface configuration;
- routing table;
- ARP/neighbor cache;
- optional Nmap host discovery;
- reverse DNS or local hostname lookup;
- user-supplied annotation.

Edges derived directly from local configuration may be marked observed. Device-to-subnet and upstream relationships inferred from address membership or routing must be marked inferred. Confidence and evidence labels must be visible in the API model and UI.

## Ownership and planned layout

Use one repository root. Do not create a nested replacement project.

Planned owners:

```text
server.py                 local HTTP entrypoint and static-file boundary
homenettopo/              discovery, parsing, validation, and topology modules
web/                      static browser interface and repository-owned assets
tests/                    parser, validation, topology, API, and security tests
fixtures/                 sanitized macOS command-output fixtures used by tests
docs/                     design, API contract, and project decisions
README.md                 operator setup and usage
metadata.json             compact product metadata
```

If implementation evidence establishes a better existing owner, update this guidance and the affected documentation together rather than creating parallel modules.

## API contract constraints

The API is local and JSON-based. It must expose separate passive snapshot and active-discovery operations so loading the page cannot silently trigger network probes.

Expected capabilities are defined in `docs/api-spec.md`. Error responses must be structured, must not leak command internals unnecessarily, and must distinguish validation failure, missing optional dependency, command failure, timeout, and unsupported platform.

## Web interface constraints

The interface must:

- render without external network access;
- show when data was collected and whether active discovery ran;
- distinguish observed and inferred links visually and textually;
- expose node details, addresses, interface names, evidence, and confidence;
- support pan, zoom, node selection, and usable keyboard focus;
- provide meaningful empty, loading, partial-result, error, and missing-Nmap states;
- avoid presenting the graph as a complete physical topology;
- provide JSON export without uploading data.

Prefer native SVG and browser APIs unless repository evidence justifies a dependency.

## Validation ownership

Static implementation work must define tests for:

- macOS interface parsing, including VPN/tunnel formats;
- route and gateway parsing;
- ARP parsing and incomplete entries;
- private-network target validation and address-count limits;
- command argument construction;
- topology deduplication and evidence/confidence assignment;
- API method, content-type, and error behavior;
- static-file traversal prevention and security headers;
- frontend data handling and representative rendering states.

Executed tests, browser checks, CI, and runtime scans must be reported only when there is direct evidence for the exact revision.

## Documentation rules

Documentation must clearly separate:

- implemented behavior;
- planned behavior;
- optional dependencies;
- executed verification;
- known inference limits.

Do not claim complete physical-network reconstruction, port scanning, operating-system fingerprinting, CI success, browser validation, or deployment success without matching implementation and evidence.

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

Do not commit real local network identifiers in fixtures. Use documentation-reserved or clearly synthetic addresses and MAC values.

## Delivery reporting

Repository-work responses must include the branch, exact revision when available, files changed, rules loaded with identifiers, static inspection performed, commands or tests actually run, checks not run, and remaining gaps or risks.
