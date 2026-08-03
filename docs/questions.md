# HomeNetTopo Decisions and Open Questions

## Status vocabulary

- `RESOLVED`: current requirement or repository evidence establishes the answer.
- `DEFAULTED`: implementation may proceed with the stated default, but the choice can be revisited only through a coordinated contract change.
- `OPEN`: a material product decision is not yet established.

## Decisions

| ID | Question | Status | Current answer | Source or impact |
|---|---|---|---|---|
| Q-001 | What is the primary host platform? | RESOLVED | macOS | Parsers, commands, setup, and acceptance target macOS. |
| Q-002 | Where is the interface served? | RESOLVED | Loopback only on `127.0.0.1` | Remote access is out of scope. |
| Q-003 | Can loading the page trigger active host discovery? | RESOLVED | No | Page load may collect local OS state but cannot invoke Nmap. |
| Q-004 | What active method is permitted? | RESOLVED | Nmap `-sn -n` host discovery only | No port, service, vulnerability, or OS scanning. |
| Q-005 | Which targets are eligible? | RESOLVED | Private IPv4 networks associated with eligible non-tunnel local interfaces | Public, special, unrelated, tunnel-only, and oversized ranges are rejected. |
| Q-006 | What is the active address limit? | RESOLVED | 1024 unique addresses across at most 32 networks | Enforced before process invocation. |
| Q-007 | Are cloud services required? | RESOLVED | No | Discovery data and UI remain local. |
| Q-008 | Are external frontend assets required? | RESOLVED | No | The page works offline from repository-owned assets. |
| Q-009 | How are uncertain links represented? | RESOLVED | Evidence, observed/inferred marker, and confidence | Prevents physical-topology overclaiming. |
| Q-010 | Is Nmap mandatory? | RESOLVED | No | Passive discovery remains available. |
| Q-011 | What dependency posture applies? | RESOLVED | Python 3.10+ standard library at runtime; Node 20+ built-in test runner only for frontend development tests | No npm packages or production Node dependency. |
| Q-012 | Are tunnel networks active targets? | RESOLVED | No | Tunnel facts are shown passively only in the first release. |
| Q-013 | What happens when export is requested without a snapshot? | RESOLVED | Return `404 not_found` without collecting | Export is side-effect free. |
| Q-014 | Does the first release perform reverse DNS or online name/vendor lookup? | RESOLVED | No | Existing names in approved command output may be retained; no separate lookup occurs. |
| Q-015 | Does the first release support user annotations or persistent device names? | RESOLVED | No | Avoids undefined storage, privacy, mutation, and export semantics. |
| Q-016 | How is passive snapshot refresh controlled? | RESOLVED | Omitted or `refresh=true` performs a new passive collection; `refresh=false` returns the current in-memory snapshot or `404` | No automatic TTL. |
| Q-017 | How are concurrent collection requests handled? | RESOLVED | One passive or active collection at a time; a second collection returns `409 collection_in_progress` | Failed collections preserve the previous snapshot. |
| Q-018 | How are browser-originated active requests protected? | RESOLVED | Loopback Host allowlist, custom request header, matching Origin when present, cross-site Fetch Metadata rejection, and no permissive CORS | Covers cross-origin and DNS-rebinding-style requests. |
| Q-019 | What are the fixed request and process bounds? | RESOLVED | 16 KiB JSON body; active timeout 1–120 seconds, default 30; passive command timeout 5 seconds; stdout 2 MiB; stderr 64 KiB; kill grace 2 seconds | Values are public contract and test boundaries. |
| Q-020 | What owns the full regression entrypoint? | RESOLVED | `scripts/check.py`, run as `python3 scripts/check.py`; full mode requires Node 20+ and fails when frontend tests cannot run | A separate Python-only developer mode may skip Node but cannot be reported as full regression. |

## Deferred product questions

| ID | Question | Why it matters | First-release behavior |
|---|---|---|---|
| Q-101 | Should IPv6 topology discovery be added? | It changes parsing, identity, validation, and schemas. | IPv4 topology only; no active IPv6 discovery. |
| Q-102 | Should user annotations be added later? | It requires a state owner, mutation contract, privacy policy, export behavior, and migrations if persisted. | No annotation feature. |
| Q-103 | Should configurable LAN bind be added? | It requires authentication, authorization, CSRF, TLS/deployment, and remote threat modeling. | Fixed loopback bind. |
| Q-104 | Should vendor or hostname enrichment be added? | A database or resolver adds licensing, update, privacy, timeout, and failure ownership. | No separate lookup; preserve only names already present in approved evidence. |
| Q-105 | Should snapshots persist across restarts? | Persistence stores private network identifiers and introduces staleness and migration concerns. | Process memory only. |

Deferred questions do not authorize speculative implementation. Their first-release behavior remains controlling until the user and all affected contract owners are updated together.
