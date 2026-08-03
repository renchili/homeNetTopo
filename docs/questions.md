# HomeNetTopo Decisions and Open Questions

## Status vocabulary

- `RESOLVED`: current requirement or repository evidence establishes the answer.
- `DEFAULTED`: implementation may proceed with the stated default, but the choice can be revisited without changing the core product.
- `OPEN`: a material product decision is not yet established.

## Decisions

| ID | Question | Status | Current answer | Source or impact |
|---|---|---|---|---|
| Q-001 | What is the primary host platform? | RESOLVED | macOS | User requirement. Parsers and setup target macOS command output. |
| Q-002 | Where is the interface served? | RESOLVED | Loopback only by default | Local-first privacy and security boundary. |
| Q-003 | Can loading the page trigger active discovery? | RESOLVED | No | Passive snapshot and active discovery are separate operations. |
| Q-004 | What active method is permitted by default? | RESOLVED | Nmap host discovery mode only | The first release discovers responsive hosts without inspecting ports or services. |
| Q-005 | Which targets are eligible? | RESOLVED | Private IPv4 networks associated with eligible local interfaces | Public, loopback, link-local, multicast, unspecified, and oversized ranges are rejected. |
| Q-006 | What is the initial active address limit? | DEFAULTED | 1024 addresses per request | Prevents accidental large operations; configurable later if source and docs agree. |
| Q-007 | Are cloud services required? | RESOLVED | No | Discovery data and UI remain local. |
| Q-008 | Are external frontend assets required? | RESOLVED | No | The page must work offline after local files are present. |
| Q-009 | How are uncertain links represented? | RESOLVED | Explicit evidence, observed/inferred marker, and confidence | Prevents the UI from claiming a proven physical topology. |
| Q-010 | Is Nmap a mandatory runtime dependency? | RESOLVED | No | Passive discovery remains available; the UI reports when optional active discovery is unavailable. |
| Q-011 | What implementation dependency posture is preferred? | DEFAULTED | Python standard library and native browser APIs | Keeps setup small; any new dependency requires a documented owner and reason. |
| Q-012 | Should tunnel interfaces be actively queried automatically? | RESOLVED | No | Tunnel networks may represent remote infrastructure; show them passively and require explicit eligibility rules. |
| Q-013 | What happens when JSON export is requested before a snapshot exists? | RESOLVED | Return `404 not_found` without collecting data | Export remains side-effect free; the user must first load or refresh the passive topology. |

## Open product questions

| ID | Question | Why it matters | Safe current behavior |
|---|---|---|---|
| Q-101 | Should the first release support IPv6 topology discovery? | It changes interface parsing, neighbor discovery, graph identity, validation, and API schemas. | Display IPv6 interface facts only if implemented coherently; do not perform active IPv6 discovery in the initial contract. |
| Q-102 | Should user annotations persist between runs? | Persistence would store local device identifiers and requires a file format, migration rules, privacy controls, and backup behavior. | Keep annotations and topology snapshots in memory only; JSON export is user initiated. |
| Q-103 | Should the server allow a configurable LAN bind? | Remote access requires a different authentication and browser-security model. | Keep the bind fixed to `127.0.0.1` in the first release. |
| Q-104 | Should local vendor names be derived from MAC prefixes? | A bundled database increases repository size and needs update/licensing ownership; online lookup conflicts with local-first behavior. | Show MAC addresses without mandatory vendor lookup. |
| Q-105 | Should discovery results be cached across process restarts? | Persistent cache can become stale and stores private network data. | Use process-memory caching only and expose collection timestamps. |

Open questions do not authorize speculative implementation. The safe current behavior remains controlling until the user or an approved project plan resolves the item.
