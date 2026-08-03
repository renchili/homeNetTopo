# HomeNetTopo Implementation Plan and Static Completion Record

## Status and authority

- Status: `STATIC_IMPLEMENTATION_COMPLETE_UNVERIFIED`
- Long-term owner: `docs/plan.md`
- Product authority: `AGENT.md` and `docs/questions.md`
- Architecture authority: `docs/design.md`
- Public API authority: `docs/api-spec.md`
- Metadata authority: `metadata.json`
- Implemented version: `0.1.0`

All planned source owners and deterministic test definitions now exist. No project code, tests, browser flow, Nmap command, real-network collection, CI workflow, build, or release artifact was executed during static generation.

## Implemented repository layout

```text
.gitignore
server.py
homenettopo/
  __init__.py
  commands.py
  discovery.py
  interfaces.py
  models.py
  neighbors.py
  routes.py
  topology.py
web/
  index.html
  core.mjs
  app.js
  styles.css
tests/
  __init__.py
  test_commands.py
  test_discovery.py
  test_interfaces.py
  test_models.py
  test_neighbors.py
  test_routes.py
  test_server.py
  test_static_security.py
  test_topology.py
  test_web_contract.py
  frontend/core.test.mjs
fixtures/macos/
  arp_all.txt
  arp_incomplete.txt
  ifconfig_multi_interface.txt
  ifconfig_utun_point_to_point.txt
  nmap_host_discovery.xml
  route_default.txt
  route_specific.txt
scripts/check.py
README.md
metadata.json
docs/
```

## Atomic requirement ledger

`DONE` below means source, test definitions, and documentation are statically mapped. It is not runtime acceptance.

| ID | Requirement | Implementation owner | Test/static owner | Status |
|---|---|---|---|---|
| HT-001 | Python 3.10+ macOS service bound to IPv4 loopback | `server.py` | `tests/test_server.py` | DONE |
| HT-002 | Command-free health and exact unsupported-platform capabilities | `server.py` | `tests/test_server.py` | DONE |
| HT-003 | Typed approved commands and no shell | `homenettopo/commands.py` | `tests/test_commands.py` | DONE |
| HT-004 | Safe Nmap resolution and source-only disclosure | commands/discovery/server | command/server tests | DONE |
| HT-005 | Deadlines, output limits, and terminate/kill cleanup | `commands.py` | command tests | DONE |
| HT-006 | macOS interface and `utun` parsing | `interfaces.py` | interface tests/fixtures | DONE |
| HT-007 | Default and specific IPv4 route parsing | `routes.py` | route tests/fixtures | DONE |
| HT-008 | Complete and incomplete ARP parsing | `neighbors.py` | neighbor tests/fixtures | DONE |
| HT-009 | Evidence-backed existing names only | parsers/topology | parser/topology tests | DONE |
| HT-010 | Coherent partial passive snapshots and prior-state preservation | server/topology | server/topology tests | DONE |
| HT-011 | Phase A before lock and commands | discovery/server | discovery/server tests | DONE |
| HT-012 | Phase B after fresh passive collection | discovery/server | discovery/server tests | DONE |
| HT-013 | Reject supernet, partial/noncanonical overlap, adjacent, tunnel, unrelated, public, and special targets | discovery | boundary tests | DONE |
| HT-014 | Enforce 32-network and 1024-address limits | discovery | exact-boundary tests | DONE |
| HT-015 | Invoke fixed Nmap XML command only after both phases | commands/discovery/server | command/discovery/server tests | DONE |
| HT-016 | Parse only up-host status and address evidence from XML | discovery | XML fixture tests | DONE |
| HT-017 | Separate total operation and fixed per-host timeout | commands/discovery/API | command/discovery tests | DONE |
| HT-018 | Stable snapshot, node, edge, source, warning, confidence, and active metadata | models/topology | model/topology tests | DONE |
| HT-019 | Conservative compatible merge and visible conflicts | topology | topology tests | DONE |
| HT-020 | Read-only health, capabilities, topology, and export GETs | server | server tests | DONE |
| HT-021 | Protected passive refresh that cannot invoke Nmap | server/collectors | server tests | DONE |
| HT-022 | Protected active flow: Phase A, passive, Phase B, Nmap | server/discovery | server/discovery tests | DONE |
| HT-023 | Single nonblocking collection lock and immediate conflict | server | server tests | DONE |
| HT-024 | Atomic replacement and preservation on failures | server | server tests | DONE |
| HT-025 | Host allowlist and DNS-rebinding-style rejection | server | server/static tests | DONE |
| HT-026 | Custom header, Origin, Fetch Metadata, no CORS/preflight bypass | server/app | server/web tests | DONE |
| HT-027 | Body/method/error enforcement and no command/path leakage | server | server tests | DONE |
| HT-028 | Contained static files, explicit MIME, traversal and symlink protection | server | static tests | DONE |
| HT-029 | Deterministic SVG layout, dynamic upstream and rectangle separation | core/app | Node layout tests | DONE |
| HT-030 | Loading, empty, partial, unavailable, validation, conflict, request, and unsupported states | core/app/HTML | Node/web tests | DONE |
| HT-031 | Keyboard, focus, non-gesture controls, 200% layout, reduced motion | web files | web tests plus later browser evidence | DONE |
| HT-032 | Python, Node, and full regression entrypoints | tests/scripts | `scripts/check.py` | DONE |
| HT-033 | Repository/private-data hygiene | `.gitignore`, scripts | hygiene stage | DONE |
| HT-034 | Exact operator documentation and evidence labeling | README/docs | consistency stage | DONE |
| HT-035 | First-release exclusions across contracts and implementation | all owners | contract/static guards | DONE |

## Implementation flow

### Passive refresh

1. validate Host and protected collection headers;
2. validate the empty JSON object;
3. acquire the nonblocking collection lock;
4. reject unsupported platforms;
5. run typed interface, route, and ARP commands independently;
6. retain coherent partial evidence with source warnings;
7. construct and validate the snapshot;
8. atomically replace the latest snapshot;
9. release the lock.

### Active discovery

1. Phase A validates request syntax, canonical IPv4 targets, classes, limits, and total timeout before lock or commands;
2. acquire the collection lock;
3. perform fresh passive collection;
4. Phase B requires every target to equal or be a subnet of an eligible non-tunnel local network;
5. collapse effective targets and recheck the address union;
6. resolve the canonical executable and construct the fixed XML command;
7. run with a bounded total deadline and fixed five-second host timeout;
8. parse only up-host status and addresses;
9. merge evidence and atomically publish the active snapshot;
10. preserve the previous snapshot on every failure.

## Verification entrypoints

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

Full regression stages are compile, metadata parse, Python tests, contract/path consistency, asset/CSP checks, Node 20+ tests, tracked-path hygiene, and a nonzero-on-failure summary. `--python-only` is development-only and reports frontend tests as `NOT RUN`.

## Evidence status

| Evidence | Status |
|---|---|
| Source owners present | PASS — static inspection only |
| Deterministic test definitions present | PASS — static inspection only |
| Python tests executed | NOT RUN |
| Node tests executed | NOT RUN |
| Full regression executed | NOT RUN |
| Supported macOS startup | NOT RUN |
| HTTP interaction | NOT RUN |
| Browser interaction/accessibility | NOT RUN |
| Nmap unavailable and active flows | NOT RUN |
| Real-network collection | NOT RUN |
| CI/artifacts/release | NOT RUN |

## Remaining acceptance work

Formal project acceptance requires exact-revision execution evidence for startup, all API routes and negative security paths, Python and Node tests, full regression, one bounded authorized Nmap discovery, timeout/conflict/snapshot behavior, browser pan/zoom/selection/details, dialog focus, reduced motion, 200% zoom, and representative empty, partial, tunnel, dependency-unavailable, and unsupported-platform states.

Static completion is not runtime correctness, CI success, release readiness, or formal project acceptance.
