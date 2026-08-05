# HomeNetTopo Implementation Ownership Record

## Status and authority

- Status: `STATIC_IMPLEMENTATION_REQUIRES_INDEPENDENT_ACCEPTANCE`
- Long-term owner: `docs/plan.md`
- Product authority: `AGENT.md` and `docs/questions.md`
- Architecture authority: `docs/design.md`
- Public API authority: `docs/api-spec.md`
- Metadata authority: `metadata.json`

This document records implementation ownership. It is not runtime evidence, an acceptance report, or automatic authorization for additional files.

## User-intent boundary

The first release is a local macOS topology viewer with a Python 3.10+ loopback service, approved passive evidence, optional bounded Nmap host discovery, a local browser interface, JSON export, in-memory snapshots, and a current-user LaunchAgent deployment path.

The principal graph distinguishes the evidence-backed path toward a gateway from devices that merely share an IPv4 subnet. Wi-Fi media is identified through `networksetup`; current BSSID may identify the associated AP radio through optional profiler evidence. Transparent Ethernet switches are not named without LLDP or managed-topology evidence. `Intermediate L2 path unknown` remains explicit for unclassified non-Wi-Fi links. Tunnel paths remain visible as Layer 3 and peers are never transit hops.

It excludes reverse DNS, online enrichment, annotations, persistence, LAN bind, active IPv6, port/service/OS scanning, packet capture, guaranteed switch enumeration, containers, cloud deployment, and system-wide installation.

## Artifact policy

- Short single-use test inputs remain inline in their owning tests.
- No fixtures, samples, demos, reports, or generated-data directory is required.
- Local runtime data, SSIDs, BSSIDs, deployment logs, topology exports, packet captures, and scan output do not enter source control.
- `scripts/deploy.py` is the only deployment script. It does not authorize a package manager, container manifest, system installer, or parallel deployment directory.

## Current owners

| Concern | Production owner | Test owner | Documentation owner |
|---|---|---|---|
| Service, request security, collection lock, concurrent passive-source orchestration, active orchestration, snapshot publication | `server.py` | `tests/test_server.py`, `tests/test_static_security.py` | `docs/api-spec.md`, `README.md` |
| Approved interface, route, ARP, networksetup, profiler, and Nmap commands; bounded execution | `homenettopo/commands.py` | `tests/test_commands.py` | `AGENT.md`, `docs/design.md` |
| Interface parsing, Wi-Fi hardware-port parsing, profiler parsing, deterministic evidence merge | `homenettopo/interfaces.py` | `tests/test_interfaces.py` | `docs/design.md` |
| Route parsing | `homenettopo/routes.py` | `tests/test_routes.py` | `docs/design.md` |
| Neighbor parsing | `homenettopo/neighbors.py` | `tests/test_neighbors.py` | `docs/design.md` |
| Active validation and Nmap evidence boundary | `homenettopo/discovery.py` | `tests/test_discovery.py` | `docs/api-spec.md`, `docs/design.md` |
| Models, path node/edge enums, deterministic serialization | `homenettopo/models.py` | `tests/test_models.py` | `docs/api-spec.md` |
| Gateway-path construction, peer membership, identity correlation | `homenettopo/topology.py` | `tests/test_topology.py` | `docs/design.md` |
| Browser state, path/peer layout, camera math | `web/core.mjs` | `tests/frontend/core.test.mjs` | `docs/design.md` |
| Browser fetch, capability status, DOM/SVG, full-surface pan, viewBox zoom/fit, focus, export | `web/app.js`, `web/index.html`, `web/styles.css` | `tests/test_web_contract.py` | `docs/design.md` |
| Current-user LaunchAgent deployment and rollback | `scripts/deploy.py` | `tests/test_static_security.py` | `README.md`, `AGENT.md`, `docs/design.md` |
| Full regression and documentation enforcement | `scripts/check.py` | self-checking stages | `README.md`, `AGENT.md`, `docs/design.md` |

## Required contracts

### Passive evidence and path inference

- Fixed passive sources execute concurrently inside one server collection lock.
- Material evidence uses `ifconfig`, IPv4 `netstat`, and ARP with independent five-second deadlines.
- Fast Wi-Fi media detection uses `/usr/sbin/networksetup -listallhardwareports` with a three-second deadline.
- Optional Wi-Fi detail uses `/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType` under an eight-second process deadline.
- `networksetup` evidence survives profiler timeout, command failure, parse failure, missing current-network fields, and redaction.
- The profiler parser keeps only current association data; nearby-network entries are ignored.
- Canonical BSSID identifies an associated AP radio. Current association without BSSID creates an observed unidentified AP. Wi-Fi media plus a default route creates an inferred unidentified AP.
- A Wi-Fi path must not regress to the generic Ethernet `Intermediate L2 path unknown` boundary merely because profiler details are absent.
- ARP maps an IP neighbor to a link-layer address but does not enumerate transparent switches.
- Without LLDP or managed-topology evidence, a non-Wi-Fi intermediate path uses `link_boundary` with low-confidence `link_path_inference` evidence.
- Exact AP BSSID and gateway ARP MAC equality may mark `same_mac`. Different MACs remain `unknown`.
- Devices connected by `member_of` are peers, not transit hops.
- Optional Wi-Fi-detail failure is nonfatal when material evidence remains coherent; the snapshot may be partial and retain warnings.
- If no material source is coherent, normalized errors include `failed_sources`; `504 command_timeout` additionally includes `timeout_sources`.

### Collection and active discovery

- Read-only GET routes never start commands.
- Active discovery validates request safety before commands, then validates fresh local containment before Nmap.
- Every target is assigned to its most-specific containing local network.
- Exact duplicates and contained targets may be removed only inside the same owner group; adjacent sibling targets remain separate.
- Nmap may run only after both validation phases pass.
- Parsed Nmap IPv4 and optional MAC evidence is validated before topology construction.
- Every accepted up-host remains inside at least one effective target network.
- Malformed or out-of-range Nmap evidence returns `500 collection_failed` and cannot publish a snapshot.
- Failed operations preserve the previous snapshot.

### Browser and static delivery

- Static files come from a fixed allowlist with traversal and symlink protection.
- CSP permits local and `data:` fonts through `font-src 'self' data:` but no external font, script, or style origin.
- The browser uses one shared collection-in-flight owner and ignores stale completion actions.
- A successful passive refresh rechecks capabilities so restored Nmap availability can recover without a page reload.
- The main path is `local_host → interface → access_point|link_boundary → gateway → upstream_boundary` when supported by evidence.
- A tunnel may use `interface → gateway` directly and is never hidden or assigned a fabricated Layer-2 attachment.
- Subnets and peer devices are rendered in context groups below the path. Membership relationships are not rendered as transit lines.
- Only path relationships are drawn: `host_uses_interface`, `interface_associated_with`, `interface_reaches_link`, `attachment_reaches_gateway`, `interface_reaches_gateway`, `upstream_of`, and `routes_to`.
- Edges render as orthogonal SVG paths.
- The canvas uses a viewBox camera, automatically fits each new snapshot, pans from nodes, edges, groups, or blank space, and zooms around the pointer.
- Active discovery has a visible Nmap state. Unavailable Nmap exposes `Check Nmap setup`; it is not an unexplained disabled placeholder.
- Keyboard operation, focus return, reduced motion, pan, zoom, fit, reset, selection, details, and export remain part of the interface contract.

### Local deployment

- `scripts/deploy.py` installs only into the current user's Library and never uses `sudo`.
- The LaunchAgent label is `com.homenettopo.local` in `gui/<uid>`.
- The service always receives `--bind 127.0.0.1`.
- The deployment copies only the 15 explicit `RUNTIME_FILES`: `server.py`, `metadata.json`, `scripts/deploy.py`, the eight named `homenettopo/*.py` files, and the four named web assets.
- Directory-recursive copying is not allowed; unlisted files, caches, tests, and local artifacts are excluded.
- Source and staged files must be regular contained files and may not be symbolic links.
- Updates stage a complete runtime and keep the previous runtime and plist until LaunchAgent startup and loopback health succeed.
- Health verification contacts only `127.0.0.1`, disables environment proxies, and bounds the response body.
- Uninstall retains logs unless `--purge-logs` is explicitly requested.

### Code documentation

- Comments explain non-obvious contracts and rationale, not obvious syntax.
- Critical Python models, parsers, security boundaries, orchestration functions, deployment actions, and regression stages have concise docstrings.
- Frontend comments cover reducer ownership, stale responses, capability recovery, safe DOM/SVG construction, address-union arithmetic, evidence-backed path layout, peer grouping, and viewBox camera behavior.
- `scripts/check.py` enforces documentation for critical symbols without requiring comments on trivial assignments.

## Verification definitions

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

Full regression includes compile, metadata, Python tests, documentation guards, cross-owner contracts, deployment guards, asset/CSP checks, Node tests, and tracked-path hygiene.

A passing or failing status requires executed evidence tied to the exact revision. Source definitions alone are not execution evidence.

## Acceptance boundary

Formal implementation acceptance must independently recheck the exact revision, repository delta, artifact necessity, source/documentation consistency, regression execution, current-user LaunchAgent lifecycle, browser interaction, supported-macOS startup, real `networksetup` and profiler output including timeout/redaction behavior, source-specific `timeout_sources`, and real command boundaries.

The implementation and deployment remain unverified until the independent acceptance workflow produces a verdict from current evidence.
