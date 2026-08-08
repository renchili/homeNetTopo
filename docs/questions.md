# HomeNetTopo Decisions and Deferred Questions

## Status vocabulary

- `RESOLVED`: current requirement and repository evidence establish the decision.
- `DEFAULTED`: implementation may use the stated default only through coordinated owners.
- `DEFERRED`: outside the current release and not authorized for speculative implementation.

## Resolved decisions

| ID | Question | Status | Current answer |
|---|---|---|---|
| Q-001 | Primary platform | RESOLVED | macOS. |
| Q-002 | Service bind | RESOLVED | IPv4 loopback `127.0.0.1` only. |
| Q-003 | Python runtime | RESOLVED | Python 3.10+, standard library only. |
| Q-004 | Native runtime | RESOLVED | Swift macOS app using Apple CoreLocation, CoreWLAN, AppKit/SwiftUI, and ServiceManagement frameworks. |
| Q-005 | Native build | RESOLVED | Deployment builds the fixed Xcode target with Apple command-line tools; no arbitrary project/target input. |
| Q-006 | Page-load behavior | RESOLVED | Protected passive-refresh POST; Nmap is never implicit. |
| Q-007 | Passive command evidence | RESOLVED | `ifconfig`, IPv4 `netstat`, ARP, `networksetup`, and best-effort AirPort `system_profiler` JSON. |
| Q-008 | Passive execution | RESOLVED | Fixed independent subprocesses execute concurrent inside one collection owner. |
| Q-009 | Native BSSID source | RESOLVED | Foreground Location-authorized CoreWLAN helper is the preferred current BSSID source. |
| Q-010 | BSSID fallback order | RESOLVED | `wifi_native > wifi(system_profiler) > local_configuration`. |
| Q-011 | Native cache | RESOLVED | `~/Library/Caches/HomeNetTopo/wifi-current.json`, schema 1, max 16 KiB, max age 20 seconds. |
| Q-012 | Cache trust | RESOLVED | Current-user-owned regular non-symlink, no group/world write, valid schema/timestamp/fields; unsafe or stale files never become identity evidence. |
| Q-013 | Location state | RESOLVED | Denied/restricted/not-determined/missing/stale helper state is actionable warning/capability state, not an invented BSSID. |
| Q-014 | Login launch | RESOLVED | Native app registers `SMAppService.mainApp`; macOS may require user approval. |
| Q-015 | Private Wi-Fi MAC | RESOLVED | `ifconfig ether` is current local MAC and may be the per-network Private Wi-Fi MAC. |
| Q-016 | Hardware MAC | RESOLVED | `networksetup Ethernet Address` is local adapter Hardware MAC and remains authoritative once observed. |
| Q-017 | Serving-radio identity | RESOLVED | BSSID belongs to the current connected Wi-Fi node, never to `This Mac`. |
| Q-018 | AP versus relay | RESOLVED | BSSID proves current associated radio, not main-AP versus relay role; optional local `relay` confirmation may coexist with automatic BSSID. |
| Q-019 | AP versus gateway physical identity | RESOLVED | Exact matching BSSID/gateway ARP MAC may be `same_mac`; different MACs remain `not_established`. |
| Q-020 | Local identity exclusion | RESOLVED | Local IPv4, Private Wi-Fi MAC, and Hardware MAC cannot become ARP/Nmap peer nodes or inflate active host count. |
| Q-021 | Wi-Fi path | RESOLVED | `This Mac → interface → current Wi-Fi node → gateway → upstream`; if BSSID is absent, the Wi-Fi boundary remains visible without invented identity. |
| Q-022 | Ethernet intermediate devices | RESOLVED | Without LLDP/CDP or managed evidence, use `Intermediate L2 path unknown`; never fabricate a switch. |
| Q-023 | LAN peers | RESOLVED | Same-subnet devices are peer context, not transit hops. |
| Q-024 | Tunnels | RESOLVED | Preserve direct Layer-3 interface/gateway path; no fabricated L2 attachment. |
| Q-025 | Active discovery | RESOLVED | Nmap host discovery only: `-sn -n --max-retries 1 --host-timeout 5s -oX -`. |
| Q-026 | Active target scope | RESOLVED | Canonical RFC 1918 targets equal to or contained by eligible non-tunnel local networks; adjacent siblings remain separate. |
| Q-027 | Nmap trust | RESOLVED | Validate XML root, up state, IPv4, optional MAC, and effective-target membership; invalid evidence is `500 collection_failed`. |
| Q-028 | Request security | RESOLVED | Host allowlist, JSON, custom header, Origin/Fetch Metadata when present; no permissive CORS. |
| Q-029 | Collection concurrency | RESOLVED | One server/browser collection owner; passive evidence sources may be concurrent internally. |
| Q-030 | Snapshot lifecycle | RESOLVED | In-memory latest snapshot, atomic replacement, failure preservation, no snapshot TTL. |
| Q-031 | Capabilities privacy | RESOLVED | Expose native helper status/message/activation URL and fallback presence only; never current SSID/BSSID/MAC/fallback values. |
| Q-032 | Native install location | RESOLVED | `~/Applications/HomeNetTopo Wi-Fi.app`; Python remains current-user LaunchAgent under `~/Library`. |
| Q-033 | Entitlements | RESOLVED | No fake Location entitlement or sandbox entitlement file is introduced for this release. |
| Q-034 | Browser details | RESOLVED | Display local IP, Hardware MAC, Private Wi-Fi MAC, BSSID, SSID, channel, RSSI, noise, PHY, rate, role, evidence, and confidence when present. |
| Q-035 | Full source/test regression | RESOLVED | `python3 scripts/check.py`; native Xcode/runtime acceptance remains a separate exact-revision macOS check. |
| Q-036 | Reverse DNS / online vendor enrichment | RESOLVED | Not included. |

## Deferred questions

| ID | Question | Why it matters | Current behavior |
|---|---|---|---|
| Q-101 | Automatically prove AP versus Wi-Fi relay/Mesh role? | Requires router/Mesh controller or other topology source; BSSID alone is insufficient. | Role remains `access point or relay` unless locally confirmed. |
| Q-102 | Add LLDP/CDP or managed switch integration? | Adds permissions, packet/management APIs, evidence schemas, and acceptance scope. | Ethernet intermediate path stays unknown. |
| Q-103 | Add active IPv6 discovery? | Changes validation, identity, Nmap, and schema. | IPv4 only. |
| Q-104 | Add persistent annotations/names? | Requires mutation API, storage, privacy, migration, and deletion. | No persistent annotations. |
| Q-105 | Allow LAN bind? | Requires authentication, authorization, CSRF/TLS, and remote threat model. | Loopback only. |
| Q-106 | Add online vendor/hostname lookup? | Adds external data/privacy/licensing/timeouts. | No external enrichment. |
| Q-107 | Persist topology snapshots? | Stores private identifiers and creates staleness/migration concerns. | Process-memory snapshots only; native cache is short-lived evidence handoff. |

Deferred questions do not authorize implementation. Any expansion requires coordinated updates to manifest/rules, metadata, design, API, ownership, source, tests, and README.
