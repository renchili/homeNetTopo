# HomeNetTopo Design

## Status

This document defines the intended first implementation. At the bootstrap revision, it is a design contract rather than evidence that the application already runs.

## Goals

- Discover network facts visible from the current macOS host.
- Build a best-effort logical topology with explicit provenance and confidence.
- Serve an interactive local-only web page.
- Keep network data on the Mac.
- Avoid mandatory third-party Python or frontend dependencies.
- Make optional active host discovery bounded, visible, and separate from passive inspection.

## Non-goals

- Proving the complete physical topology from one endpoint.
- Identifying switch ports, hidden VLANs, controller-managed wireless paths, or firewall-internal networks without additional evidence.
- Scanning public address space.
- Inspecting ports or services in the default workflow.
- Remote multi-user hosting in the first release.

## Surfaces

### Local discovery service

The service reads local operating-system state, validates optional discovery targets, invokes approved commands through argument arrays, normalizes results, and exposes JSON to the loopback browser client.

### Browser interface

The browser interface fetches passive data on load. Active host discovery requires a separate user action. It renders the topology using repository-owned HTML, CSS, JavaScript, and SVG.

## Planned module ownership

```text
server.py
  Creates the loopback HTTP server, routes API requests, serves web assets,
  applies request-size limits and security headers, and prevents path traversal.

homenettopo/commands.py
  Runs approved subprocesses with argument arrays, timeouts, bounded output,
  and normalized command errors.

homenettopo/interfaces.py
  Parses macOS ifconfig output and derives address/prefix/interface facts.

homenettopo/routes.py
  Parses routing evidence and identifies default or route-specific gateways.

homenettopo/neighbors.py
  Parses ARP/neighbor entries, including incomplete records.

homenettopo/discovery.py
  Validates private IPv4 targets and performs optional nmap -sn discovery.

homenettopo/topology.py
  Deduplicates facts and creates topology nodes, edges, evidence, confidence,
  warnings, and collection metadata.

homenettopo/models.py
  Defines stable JSON-serializable structures and validation helpers.

web/index.html
web/app.js
web/styles.css
  Own the local browser surface and SVG graph behavior.
```

The exact layout may change before implementation, but each responsibility must have one clear owner and documentation must change with it.

## Collection flow

1. Confirm the runtime is macOS or return an unsupported-platform error.
2. Read interface configuration.
3. Read routing information and identify gateways.
4. Read ARP/neighbor cache.
5. Normalize and deduplicate passive evidence.
6. Construct topology nodes and edges.
7. Return a passive snapshot without running Nmap.
8. On explicit active-discovery request, validate selected private networks and size limits.
9. Run `nmap -sn` with a timeout and parse host-up results.
10. Merge active evidence into a new snapshot and record that probing occurred.

Partial command failure should produce warnings and usable partial data when the remaining evidence is coherent.

## Target validation

An active target must:

- parse as an IPv4 network;
- be private according to the runtime IP library;
- overlap a private network assigned to an eligible local interface;
- not be loopback, link-local, multicast, unspecified, or public;
- contain no more than the configured address-count limit;
- be passed to the process runner as one validated argument.

VPN and tunnel networks may be shown passively. Their eligibility for active discovery must be explicit because a tunnel can represent a remote network rather than the physical home LAN.

## Topology model

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

`observed` means the relationship is directly supported by collected local configuration. It does not mean the physical cabling or switching path is proven.

Suggested confidence values:

- `high`: direct local configuration or multiple independent observations;
- `medium`: one reliable observation plus deterministic address or routing inference;
- `low`: heuristic association or incomplete evidence.

## Graph construction rules

- One local-host node represents the current Mac.
- Each eligible interface can connect the local host to one or more subnet nodes.
- A gateway joins the subnet supported by route and address evidence.
- A neighbor joins a subnet when its address belongs to that subnet.
- An upstream boundary may connect to a gateway when the next network is not locally observable.
- Duplicate device evidence is merged conservatively by stable address and MAC relationships.
- Conflicting hostnames or MAC evidence remains visible as a warning; it is not silently overwritten.
- Inferred edges must render differently from directly observed local relationships.

## API and request safety

- Bind to `127.0.0.1` by default.
- Accept only documented methods and JSON content types for state-changing operations.
- Enforce request-body and target-count limits.
- Do not reflect raw command lines or arbitrary command error output to the browser.
- Add restrictive response headers suitable for a local static application.
- Prevent parent-directory escape, encoded traversal, symlink escape, and directory listing in static-file handling.
- Do not add permissive cross-origin access by default.

## Frontend interaction

The topology canvas should support:

- initial fit-to-view;
- pan and zoom;
- selecting a node or edge;
- a details panel with evidence and confidence;
- keyboard-reachable controls;
- reset-view action;
- passive refresh;
- explicit active discovery;
- JSON export;
- status and warning presentation.

Required states include loading, passive success, partial success, no neighbors, Nmap unavailable, active-discovery validation error, command timeout, and unsupported platform.

## Privacy

Topology data stays in process memory unless the user exports it. The first release must not upload discovery results or automatically persist local network identifiers. Logs should avoid recording full local inventories unless a future explicit diagnostic mode is defined.

## Testing design

Use sanitized text fixtures for macOS command outputs. Tests should be deterministic and must not require access to the test machine's real LAN.

Planned test groups:

- interface parser fixtures, including `utun` point-to-point output;
- route parser fixtures;
- ARP parser fixtures;
- target-validation boundaries;
- Nmap argument construction and parser fixtures;
- topology merge and confidence rules;
- API contract and error envelopes;
- static-path and security-header behavior;
- frontend data normalization where practical.

Real-network and browser interaction checks belong to separately reported manual or acceptance evidence and must not be inferred from fixture tests.

## Operational limits

Results depend on current routing, ARP cache state, device response behavior, Wi-Fi isolation, VPNs, sleep states, local filters, and permissions. The UI and README must keep these limitations visible.
