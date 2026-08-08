# HomeNetTopo Implementation Ownership Record

## Status and authority

- Status: `STATIC_IMPLEMENTATION_REQUIRES_INDEPENDENT_ACCEPTANCE`
- Product authority: `AGENT.md` and `docs/questions.md`
- Architecture authority: `docs/design.md`
- Public API authority: `docs/api-spec.md`
- Metadata authority: `metadata.json`

This file records ownership and acceptance boundaries. It is not runtime evidence.

## User-intent boundary

HomeNetTopo is a local macOS topology viewer with a Python 3.10+ loopback service, a native CoreLocation/CoreWLAN Wi-Fi identity helper, approved passive evidence, optional bounded Nmap host discovery, a local browser interface, JSON export, in-memory snapshots, and current-user deployment.

The principal graph distinguishes the path toward a gateway from LAN peer devices. The current Wi-Fi radio is identified by BSSID when automatic evidence is available. Transparent Ethernet switches are not named without LLDP or managed-topology evidence. `Intermediate L2 path unknown` remains explicit for unclassified non-Wi-Fi links. Tunnel paths remain visible Layer 3 and peers are never transit hops.

## Artifact policy

Native expansion is explicitly limited to:

```text
macos/HomeNetTopoApp/HomeNetTopoApp.swift
macos/HomeNetTopoApp/AppDelegate.swift
macos/HomeNetTopoApp/WiFiCollector.swift
macos/HomeNetTopoApp/Info.plist
macos/HomeNetTopoApp/HomeNetTopoApp.xcodeproj/project.pbxproj
```

No native entitlements file, package manager, external framework, fixture directory, generated sample, or parallel deployment script is authorized.

Do not commit real IPs, SSIDs, BSSIDs, hostnames, MAC addresses, native cache content, deployment logs, exported snapshots, captures, or scan output.

## Current owners

| Concern | Production owner | Test owner |
|---|---|---|
| Native Location authorization, CoreWLAN association, login launch, cache publication | `macos/HomeNetTopoApp/` | `tests/test_static_security.py`, native guards in `scripts/check.py` |
| Loopback HTTP, cache trust boundary, collection lock, concurrent source orchestration, snapshot publication | `server.py` | `tests/test_server.py`, `tests/test_static_security.py` |
| Interface, networksetup, profiler, native cache parsing and evidence merge | `homenettopo/interfaces.py` | `tests/test_interfaces.py` |
| Route / ARP parsing | `homenettopo/routes.py`, `homenettopo/neighbors.py` | route/neighbor tests |
| Active RFC 1918 containment and Nmap evidence | `homenettopo/discovery.py`, `homenettopo/commands.py` | discovery/command tests |
| Public topology schema | `homenettopo/models.py` | `tests/test_models.py` |
| Local identity, current Wi-Fi node, gateway path, peers | `homenettopo/topology.py` | `tests/test_topology.py` |
| Browser state/layout/Details | `web/core.mjs`, `web/app.js`, `web/index.html`, `web/styles.css` | frontend/core and web-contract tests |
| Native build/install + Python LaunchAgent + rollback | `scripts/deploy.py` | `tests/test_static_security.py` |
| Source/test regression and static native contract | `scripts/check.py` | self-checking stages |

## Required Wi-Fi contracts

Three identities must stay separate:

```text
ifconfig ether                 -> local current / Private Wi-Fi MAC
networksetup Ethernet Address  -> local adapter Hardware MAC
CoreWLAN or profiler BSSID     -> current serving Wi-Fi radio
```

BSSID precedence is:

```text
wifi_native > wifi > local_configuration
```

`networksetup` remains authoritative for the local adapter Hardware MAC once present. Native association evidence cannot overwrite that local hardware identity.

The native helper:

- has stable bundle ID `com.homenettopo.wifi`;
- requests CoreLocation permission while foreground;
- keeps one shared `CWWiFiClient`;
- reads current SSID/BSSID, channel, RSSI, noise, PHY, transmit rate, and local hardware address when available;
- refreshes every five seconds;
- writes `~/Library/Caches/HomeNetTopo/wifi-current.json` atomically;
- registers `SMAppService.mainApp` for login launch, subject to macOS approval.

The Python service accepts native cache identity only from a regular non-symlink file owned by the current user, not group/world writable, at most 16 KiB, valid schema version 1, and no more than 20 seconds old.

Missing, stale, denied, restricted, or invalid native evidence is a warning/state, not an invented BSSID.

A BSSID proves the currently associated radio, not whether the physical appliance is definitely a main AP or relay. User-confirmed `role: relay` may coexist with automatic BSSID evidence.

## Gateway/path contracts

With automatic current BSSID:

```text
This Mac → interface → current Wi-Fi radio → gateway → upstream
```

All local IPv4, Private Wi-Fi MAC, and Hardware MAC values remain local identity. ARP/Nmap observations repeating a local IP or local MAC are excluded from peer nodes and active host counts.

ARP cannot enumerate transparent switches. Without LLDP/CDP or managed topology evidence, a non-Wi-Fi intermediate path uses `Intermediate L2 path unknown`.

BSSID equal to gateway ARP MAC may establish positive `same_mac`; a different MAC remains `not_established` because one appliance may expose multiple interface MACs.

LAN devices connected by subnet membership are peers, not transit hops. Tunnel paths are Layer 3 and never receive fabricated Layer-2 nodes.

## Collection and active discovery

Fixed passive command sources run concurrent inside one collection lock:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
```

The native cache is a file source, not a subprocess. `system_profiler` remains optional fallback.

Active discovery has two validation phases. Requested targets must be canonical RFC 1918 IPv4 equal to or contained by eligible non-tunnel local interface networks. Adjacent sibling targets remain separate. Nmap may run only after fresh containment succeeds, using fixed host-discovery XML arguments. Malformed/out-of-target evidence becomes `500 collection_failed` and cannot publish a new snapshot.

## Browser / HTTP contracts

Read-only routes never collect:

```text
GET /api/v1/health
GET /api/v1/capabilities
GET /api/v1/topology
GET /api/v1/topology/export
```

Collection routes:

```text
POST /api/v1/topology/refresh
POST /api/v1/discover
```

The Python service binds only to `127.0.0.1`. Collection requests require JSON, `X-HomeNetTopo-Request: 1`, and accepted same-origin signals when present. No permissive CORS.

Capabilities expose native helper state and activation URL but never current SSID, BSSID, Hardware MAC, Private Wi-Fi MAC, cache content, or fallback values.

Existing graph/Details owners already render local IP, Hardware MAC, Private Wi-Fi MAC, BSSID, SSID, channel, RSSI, noise, PHY, transmit rate, role, confidence, and evidence when snapshot fields are present.

## Deployment contracts

`scripts/deploy.py` is the only deployment owner. It never uses `sudo` and never changes the Python bind from loopback.

It validates the fixed Python/web runtime manifest and fixed native source manifest, builds only the fixed `HomeNetTopoApp` Xcode target with `/usr/bin/xcodebuild`, validates the bundle/privacy metadata, ad-hoc signs with `/usr/bin/codesign`, and installs only to current-user locations.

Native helper:

```text
~/Applications/HomeNetTopo Wi-Fi.app
```

Python service/runtime:

```text
~/Library/Application Support/HomeNetTopo
~/Library/LaunchAgents/com.homenettopo.local.plist
~/Library/Logs/HomeNetTopo
```

Install must foreground-open the native app after service health succeeds so the Location prompt can appear. Replacement failures restore prior runtime/app/plist where rollback data exists. Uninstall removes the native app, helper cache, Python runtime, and LaunchAgent; logs remain unless explicitly purged.

## Verification definitions

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

The source/test regression statically guards native CoreLocation/CoreWLAN, privacy plist, ServiceManagement, and Xcode boundaries but does not prove native compilation/runtime.

Exact-revision macOS acceptance additionally requires:

1. successful Xcode build and ad-hoc signing;
2. visible Location authorization for `HomeNetTopo Wi-Fi`;
3. current CoreWLAN BSSID shown in the helper;
4. fresh native cache within the 20-second trust window;
5. `GET /api/v1/capabilities` helper state `ready` without identity leakage;
6. passive snapshot source `wifi_native: ok` and the same BSSID on the connected Wi-Fi node;
7. local Private/Hardware MAC excluded from peers;
8. browser selection/Details showing the current BSSID and radio metrics;
9. current-user LaunchAgent and login-item lifecycle;
10. bounded Nmap behavior where applicable.

Do not report any unexecuted test, Xcode build, permission flow, or real-network check as PASS.
