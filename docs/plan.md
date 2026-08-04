# HomeNetTopo Implementation Ownership Record

## Status and authority

- Status: `STATIC_IMPLEMENTATION_REQUIRES_INDEPENDENT_ACCEPTANCE`
- Long-term owner: `docs/plan.md`
- Product authority: `AGENT.md` and `docs/questions.md`
- Architecture authority: `docs/design.md`
- Public API authority: `docs/api-spec.md`
- Metadata authority: `metadata.json`

This document records implementation ownership. It is not runtime evidence, an acceptance report, an implementation requirement ledger, or automatic authorization for additional files.

## User-intent boundary

The first release is a local macOS topology viewer with:

- a Python 3.10+ standard-library service bound to `127.0.0.1`;
- passive evidence from approved `ifconfig`, `netstat`, and `arp` commands;
- optional bounded Nmap host discovery after explicit confirmation;
- a local browser interface and JSON export;
- in-memory snapshots only;
- no reverse DNS, online enrichment, annotations, persistence, LAN bind, active IPv6, or port/service/OS scanning.

Implementation choices that are not required by these outcomes remain optional and require a separate necessity and authorization decision.

## Artifact policy

A path listed in this document is an ownership record, not permission to create additional parallel artifacts.

Current test-data policy:

- short single-use parser inputs are inline constants in their owning test modules;
- there is no `fixtures/`, `samples/`, `examples/`, `demos/`, `reports/`, or generated-artifact directory requirement;
- a separate data file is allowed only when native format, size, reuse, readability, or tooling makes inline data materially worse and the exact path is separately authorized;
- real network identities, command logs, packet captures, scan exports, and user runtime data must not enter source control.

## Current owners

| Concern | Production owner | Test owner | Documentation owner |
|---|---|---|---|
| Service, request security, collection lock, snapshot publication | `server.py` | `tests/test_server.py`, `tests/test_static_security.py` | `docs/api-spec.md`, `README.md` |
| Typed command construction and bounded execution | `homenettopo/commands.py` | `tests/test_commands.py` | `docs/design.md` |
| Interface parsing | `homenettopo/interfaces.py` | `tests/test_interfaces.py` | `docs/design.md` |
| Route parsing | `homenettopo/routes.py` | `tests/test_routes.py` | `docs/design.md` |
| Neighbor parsing | `homenettopo/neighbors.py` | `tests/test_neighbors.py` | `docs/design.md` |
| Active validation and Nmap XML | `homenettopo/discovery.py` | `tests/test_discovery.py` | `docs/api-spec.md`, `docs/design.md` |
| Models and deterministic serialization | `homenettopo/models.py` | `tests/test_models.py` | `docs/api-spec.md` |
| Topology construction | `homenettopo/topology.py` | `tests/test_topology.py` | `docs/design.md` |
| Browser state and layout | `web/core.mjs` | `tests/frontend/core.test.mjs` | `docs/design.md` |
| Browser DOM, SVG, and interaction adapter | `web/app.js`, `web/index.html`, `web/styles.css` | `tests/test_web_contract.py` | `docs/design.md` |
| Repository-relative regression entrypoint | `scripts/check.py` | self-checking stages | `README.md` |

## Required contracts

### Collection and state

- GET routes are read-only and do not start collection commands.
- Passive refresh uses only approved passive commands.
- A nonempty command output that contains no recognizable facts is a parse failure, not a successful empty source.
- macOS route rows require the IPv4 table header and recognizable destination, gateway, flags, and interface columns; abbreviated network destinations, IPv4 gateways, `link#N`, and MAC gateways are supported.
- Active discovery validates the request before lock and commands, then checks containment against fresh eligible local networks before resolving or invoking Nmap.
- One collection runs at a time; concurrent collection returns `409 collection_in_progress`.
- Successful snapshots replace the in-memory snapshot atomically; failure preserves the previous snapshot.

### Active discovery

- Target count: 1–32 networks.
- Target union: at most 1024 unique IPv4 addresses.
- Total operation timeout: default 30 seconds, accepted range 5–120.
- Nmap per-host timeout: fixed 5 seconds.
- Targets must be RFC 1918 networks within `10.0.0.0/8`, `172.16.0.0/12`, or `192.168.0.0/16` and must equal or be contained by an eligible non-tunnel local network.
- Every target is assigned to its most-specific containing local network.
- Exact duplicates and contained targets may be removed only within the same owner group. Adjacent sibling targets remain separate, and the command layer preserves the Phase B effective target set except for exact duplicate removal and deterministic ordering.
- Supernets, partial overlap, adjacent, unrelated, tunnel-only, non-RFC1918, public, documentation, loopback, link-local, multicast, unspecified, and reserved ranges are rejected.
- Nmap is limited to host discovery XML output.

### Browser and static delivery

- Static files are served from a fixed allowlist with traversal and symlink protection.
- The graph uses deterministic top-left coordinates and dynamic upstream placement after the rightmost device or gateway column.
- Loading, empty, partial, dependency, validation, conflict, request-error, unsupported-platform, confirmation, cancellation, and active-running states have explicit owners.
- Keyboard operation, focus return, reduced motion, narrow layouts, pan, zoom, fit, reset, selection, details, and export remain part of the interface contract.

## Verification definitions

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

These commands define the verification entrypoints. A passing or failing status requires executed evidence tied to the exact revision; source definitions alone are not execution evidence.

## Acceptance boundary

Formal implementation acceptance must independently recheck the exact revision, repository delta, artifact necessity, source and documentation consistency, test execution, browser interaction, supported-macOS startup, and real command boundaries.

The implementation remains unverified until the independent acceptance workflow produces a verdict from current evidence.