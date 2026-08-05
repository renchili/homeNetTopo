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

The principal graph must distinguish the evidence-backed path toward a gateway from devices that merely share an IPv4 subnet. Wi-Fi association may identify the directly associated AP radio through BSSID. Transparent Ethernet switches are not named without LLDP or managed-topology evidence. Unknown intermediate Layer-2 transit remains explicitly unknown. Tunnel paths remain visible as Layer 3.

It excludes reverse DNS, online enrichment, annotations, persistence, LAN bind, active IPv6, port/service/OS scanning, packet capture, guaranteed switch enumeration, containers, cloud deployment, and system-wide installation.

## Artifact policy

- Short single-use test inputs remain inline in their owning tests.
- No fixtures, samples, demos, reports, or generated-data directory is required.
- Local runtime data, SSIDs, BSSIDs, deployment logs, topology exports, packet captures, and scan output do not enter source control.
- `scripts/deploy.py` is the only deployment script. It does not authorize a package manager, container manifest, system installer, or parallel deployment directory.

## Current owners

| Concern | Production owner | Test owner | Documentation owner |
|---|---|---|---|
| Service, request security, collection lock, passive-source degradation, active orchestration, snapshot publication | `server.py` | `tests/test_server.py`, `tests/test_static_security.py` | `docs/api-spec.md`, `README.md` |
| Approved interface, route, ARP, Wi-Fi profiler, and Nmap commands; bounded execution | `homenettopo/commands.py` | `tests/test_commands.py` | `AGENT.md`, `docs/design.md` |
| Interface and current Wi-Fi-association parsing | `homenettopo/interfaces.py` | `tests/test_interfaces.py` | `docs/design.md` |
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

- Fixed passive commands collect interface, route, ARP, and best-effort current Wi-Fi association evidence.
- Wi-Fi profiling uses `/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType` under the bounded process runner.
- The Wi-Fi parser keeps only current association data. Nearby-network entries are ignored.
- Canonical BSSID identifies an associated AP radio. A missing or redacted BSSID creates an unidentified AP attachment; it is never guessed.
- ARP maps an IP neighbor to a link-layer address but does not enumerate transparent switches.
- Ordinary route information does not expose Layer-2 forwarding devices.
- Without LLDP or managed-topology evidence, a non-Wi-Fi intermediate path is represented by `link_boundary` with low-confidence `link_path_inference` evidence.
- Exact AP BSSID and gateway ARP MAC equality may mark `same_mac`. Different MACs remain `unknown`; they do not prove different physical appliances.
- Devices connected by `member_of` are LAN peers, not transit hops.
- Wi-Fi source failure is nonfatal when interface, route, or ARP evidence still forms a coherent snapshot. The snapshot is partial and retains a warning.

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
- The browser uses one shared collection-in-flight owner and ignores stale completion actions.
- A successful passive refresh rechecks capabilities so restored Nmap availability can recover without a page reload.
- The main path is `local_host → interface → access_point|link_boundary → gateway → upstream_boundary` when those nodes are supported by evidence.
- A tunnel may use `interface → gateway` directly and is never hidden or assigned a fabricated Layer-2 attachment.
- Subnets and peer devices are rendered in context groups below the path. Membership relationships are not rendered as transit lines.
- Only path relationships are drawn: `host_uses_interface`, `interface_associated_with`, `interface_reaches_link`, `attachment_reaches_gateway`, `interface_reaches_gateway`, `upstream_of`, and `routes_to`.
- Edges render as orthogonal SVG paths.
- The canvas uses a viewBox camera, automatically fits each new snapshot, pans from nodes, edges, groups, or blank space, and zooms around the pointer.
- A drag suppresses the resulting click so panning does not accidentally change selection.
- Active discovery has a visible Nmap state. Unavailable Nmap exposes `Check Nmap setup`; it is not an unexplained disabled placeholder.
- Keyboard operation, focus return, reduced motion, pan, zoom, fit, reset, selection, details, and export remain part of the interface contract.

### Local deployment

- `scripts/deploy.py` installs only into the current user's Library and never uses `sudo`.
- The LaunchAgent label is `com.homenettopo.local` in `gui/<uid>`.
- The service always receives `--bind 127.0.0.1`.
- The deployment copies only the 15 explicit `RUNTIME_FILES`: `server.py`, `metadata.json`, `scripts/deploy.py`, the eight named `homenettopo/*.py` files, and the four named web assets.
- Directory-recursive copying is not allowed; unlisted files, caches, tests, and local artifacts are excluded.
- Fixed paths are `~/Library/Application Support/HomeNetTopo`, `~/Library/LaunchAgents/com.homenettopo.local.plist`, and `~/Library/Logs/HomeNetTopo`.
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

Formal implementation acceptance must independently recheck the exact revision, repository delta, artifact necessity, source and documentation consistency, test execution, current-user LaunchAgent install/update/status/restart/uninstall and rollback, browser interaction, supported-macOS startup, real Wi-Fi association output including redaction behavior, and real command boundaries.

The implementation and deployment remain unverified until the independent acceptance workflow produces a verdict from current evidence.
