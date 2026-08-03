# HomeNetTopo Decisions and Deferred Questions

## Status vocabulary

- `RESOLVED`: current requirement and repository evidence establish the answer.
- `DEFAULTED`: implementation may use the stated default only through the coordinated contract owners.
- `DEFERRED`: explicitly outside the first release and not authorized for speculative implementation.

## Resolved decisions

| ID | Question | Status | Current answer | Impact |
|---|---|---|---|---|
| Q-001 | Primary platform | RESOLVED | macOS | Commands, parsers, setup, and runtime acceptance target macOS. |
| Q-002 | Service bind | RESOLVED | IPv4 loopback `127.0.0.1` only | Remote access is out of scope. |
| Q-003 | Minimum Python | RESOLVED | Python 3.10 | Runtime code may use Python 3.10 standard-library behavior. |
| Q-004 | Production dependencies | RESOLVED | Python standard library and repository-owned browser assets | Nmap is optional; Node is development-test-only. |
| Q-005 | Page-load behavior | RESOLVED | Page load explicitly calls protected passive-refresh POST | It may read local OS state but cannot invoke Nmap. |
| Q-006 | Active discovery mode | RESOLVED | Nmap `-sn -n --max-retries 1 --host-timeout 5s -oX -` | XML stdout only; no ports, services, OS, DNS, or online lookup. |
| Q-007 | Active target relationship | RESOLVED | Every target must equal or be a subnet of one eligible non-tunnel local network | Supernets, partial overlaps, adjacent networks, and unrelated private ranges are rejected. |
| Q-008 | Active request limits | RESOLVED | 1–32 networks and at most 1024 unique addresses | Enforced in both validation phases before Nmap. |
| Q-009 | Active timeout semantics | RESOLVED | `operation_timeout_seconds` is total Nmap-process deadline; default 30, range 5–120 | Nmap per-host timeout is separately fixed at 5 seconds. |
| Q-010 | Request body and command bounds | RESOLVED | 16 KiB body; passive timeout 5s; stdout 2 MiB; stderr 64 KiB; kill grace 2s | Public contract and exact test boundaries. |
| Q-011 | Browser request protection | RESOLVED | Host allowlist plus custom header, Origin and Fetch Metadata checks for both collection POST endpoints | No permissive CORS or preflight bypass. |
| Q-012 | Read-only and collection endpoints | RESOLVED | GET endpoints never execute commands; passive refresh and active discover are protected POST endpoints | Cross-origin pages cannot trigger collection through a simple GET. |
| Q-013 | Collection concurrency | RESOLVED | One collection at a time; second collection returns `409 collection_in_progress` | No waiting, merging, or background queue. |
| Q-014 | Snapshot lifecycle | RESOLVED | Process-memory latest snapshot, no TTL, atomic replacement, failed operations preserve previous snapshot | Export and topology GET return `404` when absent. |
| Q-015 | Active validation sequence | RESOLVED | Phase A validates request syntax and absolute safety before commands; Phase B validates local-network containment after fresh passive collection | Nmap is forbidden until both phases pass. |
| Q-016 | Unsupported-platform capabilities | RESOLVED | Health may work; capabilities report passive false and active unavailable with reason `unsupported_platform` | No collection command is attempted. |
| Q-017 | Nmap capability disclosure | RESOLVED | Report availability and resolution source only | Full executable path is not exposed to the browser. |
| Q-018 | Nmap output parser | RESOLVED | XML from stdout parsed with `xml.etree.ElementTree` | Deterministic fixture and version-tolerant structured parsing. |
| Q-019 | Uncertain topology links | RESOLVED | Evidence, observed/inferred marker, and confidence | Prevents physical-topology overclaiming. |
| Q-020 | Graph coordinate convention | RESOLVED | Node coordinates are top-left world coordinates | Layout and overlap tests use rectangle bounds consistently. |
| Q-021 | Upstream graph position | RESOLVED | Dynamically placed after the right edge of the widest device grid | Fixed minimum `x=1160`, otherwise grid-right plus 48. |
| Q-022 | Frontend test runtime | RESOLVED | Node.js 20+ built-in test runner, no npm packages | Production does not require Node. |
| Q-023 | Full regression owner | RESOLVED | `python3 scripts/check.py` | Full mode requires Python and Node stages; Python-only mode is not full evidence. |
| Q-024 | Export without snapshot | RESOLVED | `404 not_found`, no collection | Export remains side-effect free. |
| Q-025 | Reverse DNS and annotations | RESOLVED | Not included in the first release | Existing names in approved command output may be retained with evidence. |

## Deferred questions

| ID | Question | Why it matters | First-release behavior |
|---|---|---|---|
| Q-101 | Add active IPv6 discovery? | Changes parsing, identity, validation, Nmap behavior, and schemas. | IPv4 topology only. |
| Q-102 | Add user annotations or persistent names? | Requires mutation API, privacy rules, storage, export semantics, and migrations. | No annotation feature. |
| Q-103 | Allow LAN bind? | Requires authentication, authorization, CSRF, TLS/deployment, and remote threat modeling. | Fixed loopback bind. |
| Q-104 | Add vendor or hostname enrichment? | Introduces resolver/database licensing, privacy, update, timeout, and failure ownership. | No separate lookup. |
| Q-105 | Persist snapshots? | Stores private identifiers and introduces staleness, migration, and deletion concerns. | Process memory only. |

Deferred questions do not authorize implementation. Changing one requires updating `AGENT.md`, `metadata.json`, `docs/design.md`, `docs/api-spec.md`, `docs/plan.md`, source owners, tests, and README together.
