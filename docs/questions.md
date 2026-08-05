# HomeNetTopo Decisions and Deferred Questions

## Status vocabulary

- `RESOLVED`: current requirement and repository evidence establish the answer.
- `DEFAULTED`: implementation may use the stated default only through coordinated owners.
- `DEFERRED`: outside the first release and not authorized for speculative implementation.

## Resolved decisions

| ID | Question | Status | Current answer | Impact |
|---|---|---|---|---|
| Q-001 | Primary platform | RESOLVED | macOS | Commands, parsers, deployment, and runtime acceptance target macOS. |
| Q-002 | Service bind | RESOLVED | IPv4 loopback `127.0.0.1` only | Remote access is out of scope. |
| Q-003 | Minimum Python | RESOLVED | Python 3.10 | Runtime uses standard-library behavior available in 3.10. |
| Q-004 | Production dependencies | RESOLVED | Python standard library and repository-owned browser assets | Nmap is optional; Node is test-only. |
| Q-005 | Page-load behavior | RESOLVED | Protected passive-refresh POST | It may read approved local OS state but cannot invoke Nmap. |
| Q-006 | Passive evidence commands | RESOLVED | `ifconfig`, IPv4 `netstat`, ARP, `networksetup`, and best-effort AirPort `system_profiler` JSON | Wi-Fi media survives missing profiler detail; nearby scans are discarded. |
| Q-007 | Passive execution model | RESOLVED | Independent fixed passive commands execute concurrently inside one collection owner | Wall-clock latency is bounded by the slowest source rather than cumulative timeouts. |
| Q-008 | Passive timeout disclosure | RESOLVED | Incoherent material failure reports `failed_sources`; 504 also reports `timeout_sources` | Optional Wi-Fi-detail timeout alone cannot produce 504. |
| Q-009 | Active discovery mode | RESOLVED | Nmap `-sn -n --max-retries 1 --host-timeout 5s -oX -` | XML stdout only; no ports, services, OS, DNS, or online lookup. |
| Q-010 | Active target relationship | RESOLVED | Every target equals or is contained by one eligible non-tunnel local RFC 1918 network | Supernets, partial overlaps, adjacent networks, unrelated ranges, and non-RFC1918 are rejected. |
| Q-011 | Active request limits | RESOLVED | 1–32 networks and at most 1024 unique addresses | Enforced before Nmap in both validation layers. |
| Q-012 | Active timeout semantics | RESOLVED | Total Nmap deadline default 30, range 5–120; per-host timeout fixed 5 | Separate process and host deadlines. |
| Q-013 | Command and body bounds | RESOLVED | 16 KiB body; material commands 5s; Wi-Fi media 3s; profiler 8s; stdout 2 MiB; stderr 64 KiB; kill grace 2s | Fixed implementation and test contract. |
| Q-014 | Browser request protection | RESOLVED | Host allowlist plus custom header, Origin, and Fetch Metadata checks | No permissive CORS or preflight bypass. |
| Q-015 | Collection concurrency | RESOLVED | One server collection and one browser collection owner; internal evidence commands may be concurrent | No second client collection, waiting, merging, phase overwrite, or background queue. |
| Q-016 | Snapshot lifecycle | RESOLVED | In-memory latest snapshot, no TTL, atomic replacement, failure preservation | Export and topology GET return `404` when absent. |
| Q-017 | Active validation sequence | RESOLVED | Phase A before commands; Phase B after fresh passive evidence | Nmap is forbidden until both phases pass. |
| Q-018 | Unsupported platform | RESOLVED | Health may work; collection capabilities are unavailable | No collection command is attempted. |
| Q-019 | Nmap disclosure and recovery | RESOLVED | Report availability and resolution source only; passive refresh and `Check Nmap setup` can recheck | Full executable path is never exposed. |
| Q-020 | Nmap output trust boundary | RESOLVED | Validate XML root, up-state, IPv4, MAC, and effective-target membership | Invalid evidence is `500 collection_failed` and cannot publish. |
| Q-021 | Wi-Fi attachment identity | RESOLVED | BSSID identifies the associated AP radio; `networksetup` plus default route infers an unidentified AP when details are absent | Wi-Fi must not regress to generic Ethernet unknown merely because BSSID is unavailable. |
| Q-022 | AP versus gateway physical identity | RESOLVED | Exact matching AP and gateway MAC is positive `same_mac`; different MACs remain `unknown` | One appliance commonly has different radio and routed-interface MACs. |
| Q-023 | Ethernet intermediate devices | RESOLVED | Ordinary ARP and IP routes cannot enumerate transparent switches | Without LLDP/CDP or managed-topology evidence, show `Intermediate L2 path unknown`, not a fabricated switch. |
| Q-024 | Same-subnet devices | RESOLVED | They are LAN peers, not host-to-gateway transit hops | Render peers in subnet context groups without transit lines. |
| Q-025 | Tunnel representation | RESOLVED | Preserve a direct Layer-3 interface-to-gateway path | Never hide tunnels or fabricate a Layer-2 attachment. |
| Q-026 | Graph coordinate convention | RESOLVED | Top-left world coordinates with an SVG viewBox camera | Layout, fit, pan, zoom, and overlap tests share one coordinate model. |
| Q-027 | Main path layout | RESOLVED | Host → interface → AP or unknown link → gateway → upstream | Peer groups are below the path; only path edges are rendered. |
| Q-028 | Font policy | RESOLVED | CSP permits `'self'` and `data:` fonts only | Extension-injected data fonts do not require external font origins. |
| Q-029 | Frontend test runtime | RESOLVED | Node.js 20+ built-in runner, no npm packages | Production does not require Node. |
| Q-030 | Full regression owner | RESOLVED | `python3 scripts/check.py` | Python-only mode is not full evidence. |
| Q-031 | Export without snapshot | RESOLVED | `404 not_found`, no collection | Export remains side-effect free. |
| Q-032 | Reverse DNS and annotations | RESOLVED | Not included | Existing approved-output names may be retained with evidence. |

## Deferred questions

| ID | Question | Why it matters | First-release behavior |
|---|---|---|---|
| Q-101 | Add LLDP/CDP or managed-network integration? | Requires packet or management APIs, permissions, new evidence schemas, privacy limits, and platform acceptance. | Ethernet intermediate path remains explicitly unknown. |
| Q-102 | Add active IPv6 discovery? | Changes parsing, validation, Nmap behavior, identity, and schemas. | IPv4 topology only. |
| Q-103 | Add annotations or persistent names? | Requires mutation API, storage, privacy, export, and migration rules. | No annotations. |
| Q-104 | Allow LAN bind? | Requires authentication, authorization, CSRF, TLS, and remote threat modeling. | Fixed loopback bind. |
| Q-105 | Add vendor or hostname enrichment? | Introduces external data, licensing, privacy, update, and timeout ownership. | No separate lookup. |
| Q-106 | Persist snapshots? | Stores private identifiers and introduces staleness, migration, and deletion concerns. | Process memory only. |

Deferred questions do not authorize implementation. A change requires coordinated updates to rules, metadata, design, API, ownership, source, tests, and README.
