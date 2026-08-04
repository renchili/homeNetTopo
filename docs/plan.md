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

It excludes reverse DNS, online enrichment, annotations, persistence, LAN bind, active IPv6, port/service/OS scanning, containers, cloud deployment, and system-wide installation.

## Artifact policy

- Short single-use test inputs remain inline in their owning tests.
- No fixtures, samples, demos, reports, or generated-data directory is required.
- Local runtime data, deployment logs, topology exports, packet captures, and scan output do not enter source control.
- `scripts/deploy.py` is the only deployment script. It does not authorize a package manager, container manifest, system installer, or parallel deployment directory.

## Current owners

| Concern | Production owner | Test owner | Documentation owner |
|---|---|---|---|
| Service, request security, collection lock, active orchestration, snapshot publication | `server.py` | `tests/test_server.py`, `tests/test_static_security.py` | `docs/api-spec.md`, `README.md` |
| Approved commands, Nmap resolution, bounded execution | `homenettopo/commands.py` | `tests/test_commands.py` | `docs/design.md` |
| Interface parsing | `homenettopo/interfaces.py` | `tests/test_interfaces.py` | `docs/design.md` |
| Route parsing | `homenettopo/routes.py` | `tests/test_routes.py` | `docs/design.md` |
| Neighbor parsing | `homenettopo/neighbors.py` | `tests/test_neighbors.py` | `docs/design.md` |
| Active validation and Nmap evidence boundary | `homenettopo/discovery.py` | `tests/test_discovery.py` | `docs/api-spec.md`, `docs/design.md` |
| Models and deterministic serialization | `homenettopo/models.py` | `tests/test_models.py` | `docs/api-spec.md` |
| Topology construction | `homenettopo/topology.py` | `tests/test_topology.py` | `docs/design.md` |
| Browser state, coordination, recovery, and layout | `web/core.mjs` | `tests/frontend/core.test.mjs` | `docs/design.md` |
| Browser fetch, DOM/SVG, interaction, focus, and export | `web/app.js`, `web/index.html`, `web/styles.css` | `tests/test_web_contract.py` | `docs/design.md` |
| Current-user LaunchAgent deployment and rollback | `scripts/deploy.py` | `tests/test_static_security.py` | `README.md`, `AGENT.md`, `docs/design.md` |
| Full regression and documentation enforcement | `scripts/check.py` | self-checking stages | `README.md`, `AGENT.md`, `docs/design.md` |

## Required contracts

### Collection and active discovery

- Read-only GET routes never start commands.
- Passive refresh uses only approved commands and may publish a coherent partial snapshot.
- Active discovery validates request safety before commands, then validates fresh local containment before Nmap.
- Every target is assigned to its most-specific containing local network.
- Exact duplicates and contained targets may be removed only inside the same owner group; adjacent sibling targets remain separate.
- Nmap may run only after both validation phases pass.
- Parsed Nmap IPv4 and optional MAC evidence is validated before topology construction.
- Every accepted up-host remains inside at least one effective target network.
- Failed operations preserve the previous snapshot.

### Browser and static delivery

- Static files come from a fixed allowlist with traversal and symlink protection.
- The browser uses one shared collection-in-flight owner and ignores stale completion actions.
- A successful passive refresh rechecks capabilities so restored Nmap availability can recover without a page reload.
- Keyboard operation, focus return, reduced motion, pan, zoom, fit, reset, selection, details, and export remain part of the interface contract.

### Local deployment

- `scripts/deploy.py` installs only into the current user's Library and never uses `sudo`.
- The LaunchAgent label is `com.homenettopo.local` in `gui/<uid>`.
- The service always receives `--bind 127.0.0.1`.
- The runtime copy is limited to `server.py`, `metadata.json`, `scripts/deploy.py`, `homenettopo/`, and `web/`.
- Fixed paths are `~/Library/Application Support/HomeNetTopo`, `~/Library/LaunchAgents/com.homenettopo.local.plist`, and `~/Library/Logs/HomeNetTopo`.
- Updates stage a complete runtime and keep the previous runtime and plist until LaunchAgent startup and loopback health succeed.
- Health verification contacts only `127.0.0.1`.
- Uninstall retains logs unless `--purge-logs` is explicitly requested.

### Code documentation

- Comments explain non-obvious contracts and rationale, not obvious syntax.
- Critical Python models, parsers, security boundaries, orchestration functions, deployment actions, and regression stages have concise docstrings.
- Frontend comments cover reducer ownership, stale responses, focus recovery, safe DOM/SVG construction, address-union arithmetic, and deterministic layout.
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

Formal implementation acceptance must independently recheck the exact revision, repository delta, artifact necessity, source and documentation consistency, test execution, current-user LaunchAgent install/update/status/restart/uninstall and rollback, browser interaction, supported-macOS startup, and real command boundaries.

The implementation and deployment remain unverified until the independent acceptance workflow produces a verdict from current evidence.
