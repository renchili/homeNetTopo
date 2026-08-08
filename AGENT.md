# HomeNetTopo Project Guidance

## Product boundary

`homeNetTopo` is a local-first macOS topology application. The browser UI and Python service remain bound to `127.0.0.1`; a small native macOS app supplies the current Wi-Fi identity that modern macOS protects behind Location permission.

The product must keep facts, deterministic inference, and unknown topology separate. It must never turn an IP peer, a local MAC address, or an inferred boundary into a physical transit device without evidence.

## Runtime owners

Production consists of:

- Python 3.10+ standard-library loopback service;
- repository-owned HTML/CSS/JavaScript/SVG UI;
- native Swift macOS helper using AppKit/SwiftUI, CoreLocation, CoreWLAN, and ServiceManagement;
- optional Nmap for bounded active host discovery.

Deployment requires Xcode command-line build support because `scripts/deploy.py` builds the native app before installing it under the current user. Node.js 20+ is development-only for frontend tests. No Python or npm third-party packages are used.

## Approved command boundary

HTTP callers never provide executables or arbitrary arguments. Runtime command families are fixed:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <validated-targets...>
```

Independent passive commands run concurrent inside one collection owner. Interface, route, and ARP commands use five-second process limits; Wi-Fi interface classification uses three seconds; profiler detail uses an eight-second process limit around its fixed five-second internal timeout.

Native build/deployment uses only fixed Apple tools and fixed repository sources:

```text
/usr/bin/xcodebuild
/usr/bin/codesign
/usr/bin/open
/bin/launchctl
```

Never use `shell=True`, `sudo`, arbitrary Xcode projects, arbitrary targets, or user-supplied build commands.

## Wi-Fi identity contract

There are three different link-layer identities and they must never be conflated:

1. `ifconfig ether` is the MAC currently used by the local BSD interface. With Private Wi-Fi Address enabled, this is the local **Private Wi-Fi MAC**.
2. `networksetup -listallhardwareports` supplies the local adapter **Hardware MAC**.
3. The current association **BSSID** identifies the serving Wi-Fi radio. It belongs to the connected Wi-Fi node, not to `This Mac`.

The BSSID evidence precedence is:

```text
wifi_native (CoreWLAN + Location) > wifi (system_profiler) > local_configuration
```

`wifi_interfaces` from `networksetup` identifies Wi-Fi media and preserves the Hardware MAC but does not identify the serving radio.

### Native helper

The helper source is fixed at:

```text
macos/HomeNetTopoApp/HomeNetTopoApp.swift
macos/HomeNetTopoApp/AppDelegate.swift
macos/HomeNetTopoApp/WiFiCollector.swift
macos/HomeNetTopoApp/Info.plist
macos/HomeNetTopoApp/HomeNetTopoApp.xcodeproj/project.pbxproj
```

Bundle ID:

```text
com.homenettopo.wifi
```

Installed app:

```text
~/Applications/HomeNetTopo Wi-Fi.app
```

The app requests CoreLocation When-In-Use authorization while foreground, keeps one shared `CWWiFiClient`, and refreshes the current CoreWLAN association every five seconds. It publishes only local evidence to:

```text
~/Library/Caches/HomeNetTopo/wifi-current.json
```

The cache is schema version 1, current-user owned, non-symlink, bounded to 16 KiB, and accepted by the Python service only when at most 20 seconds old. Denied, restricted, missing, stale, malformed, wrong-owner, or writable-by-group/other cache files never become BSSID evidence.

The helper registers its main app with `SMAppService.mainApp` for login launch. macOS may require explicit user approval. Installation must still open the helper in the foreground so the Location prompt can appear.

Do not add a fake location entitlement or claim that an entitlement bypasses Location privacy. The project is not sandboxed in this release.

### Wi-Fi path semantics

With fresh native BSSID:

```text
This Mac → interface → current Wi-Fi radio → gateway → upstream
```

The Wi-Fi node can show SSID, BSSID, Channel, RSSI, Noise, PHY mode, and transmit rate when available. A BSSID proves the current associated radio identity, not whether that physical appliance is definitively a main access point or relay. User-confirmed `relay` role may be retained beside automatic BSSID evidence.

If native evidence is unavailable, `system_profiler` may still supply BSSID. If neither automatic source does, keep a connected Wi-Fi node with unavailable identity and an actionable `wifi_native` warning. A manually configured BSSID is last-resort local evidence, never automatic observation.

## Host, gateway, peers, and hidden Layer 2

All local IPv4 addresses, Private Wi-Fi MAC values, and Hardware MAC values belong to `This Mac` / its interface. ARP or Nmap records repeating a local IP or local MAC must be excluded from peer nodes and active host counts.

ARP can map an IP neighbor to a MAC but cannot enumerate transparent switches. A different gateway MAC and BSSID do not prove separate physical appliances because one device may expose multiple interface MACs. Equality can be positive `same_mac` evidence; inequality remains `not_established`.

Without LLDP/CDP or managed topology evidence, non-Wi-Fi Ethernet paths use:

```text
This Mac → interface → Intermediate L2 path unknown → gateway → upstream
```

LAN peers remain subnet context, never transit hops. Tunnel interfaces remain visible Layer-3 paths and receive no fabricated Wi-Fi or Layer-2 device.

## Active discovery safety

Active discovery accepts only canonical RFC 1918 IPv4 networks equal to or contained by eligible non-tunnel local interface networks. Validation is two phase: request shape/range/limits before commands, then fresh interface containment under the collection lock.

Adjacent sibling targets remain separate; they are never widened into a new supernet. The final Nmap command is fixed to host discovery XML only. Malformed or out-of-target Nmap evidence is `500 collection_failed`. Interface timeout is `504 command_timeout`; unusable interface evidence is `500 collection_failed`; successful interfaces with no eligible target are `400 invalid_target`.

No port, service, vulnerability, credential, OS, packet-capture, public-internet, or reverse-DNS discovery is allowed.

## Browser / HTTP boundary

Accepted Host values are only:

```text
127.0.0.1:<port>
localhost:<port>
```

Read-only routes never execute collection commands:

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

Collection POSTs require JSON and `X-HomeNetTopo-Request: 1`; Origin and Fetch Metadata must be same-origin when present. No permissive CORS. The CSP may allow repository/data fonts but no external script/style/font origin.

Capabilities expose native helper **state and an activation URL only**, never SSID, BSSID, Hardware MAC, Private Wi-Fi MAC, or the manual fallback value.

## Snapshot lifecycle

Only one collection may run at a time. Fixed passive sources may execute concurrently inside that owner. Success publishes atomically; failure preserves the previous snapshot. Snapshots remain process-memory-only. The native Wi-Fi cache is a short-lived evidence handoff, not snapshot persistence.

## Deployment boundary

`scripts/deploy.py` owns deployment. It:

- never uses `sudo`;
- always binds Python service to `127.0.0.1`;
- copies only the fixed 15-file Python/web runtime manifest;
- validates the fixed five-file native source manifest;
- builds only `HomeNetTopoApp` from the fixed Xcode project;
- ad-hoc signs and verifies the built native app;
- installs the Python runtime under `~/Library/Application Support/HomeNetTopo`;
- installs the helper under `~/Applications/HomeNetTopo Wi-Fi.app`;
- writes the Python LaunchAgent under `~/Library/LaunchAgents/com.homenettopo.local.plist`;
- writes service/build logs under `~/Library/Logs/HomeNetTopo`;
- opens the native helper after service health succeeds;
- rolls back replaced runtime/app/plist when a later install step fails;
- removes native helper cache on uninstall.

Manual `--wifi-bssid`, `--wifi-ssid`, and `--wifi-role` options remain local-only fallbacks. They never belong in repository files or logs.

## Current ownership

```text
server.py                         HTTP boundary, native-cache validation, collection orchestration, snapshots
homenettopo/commands.py           fixed subprocess allowlist and bounded execution
homenettopo/interfaces.py         interface/networksetup/profiler/native Wi-Fi parsing and merge priority
homenettopo/routes.py             IPv4 route parser
homenettopo/neighbors.py          ARP parser
homenettopo/discovery.py          RFC 1918 Phase A/B validation and Nmap evidence validation
homenettopo/models.py             validated public snapshot schema
homenettopo/topology.py           local identity, Wi-Fi/gateway path, peer membership, evidence/confidence
macos/HomeNetTopoApp/             CoreLocation + CoreWLAN helper and Xcode project
web/core.mjs                      pure reducer/layout/camera math
web/app.js                        safe DOM/SVG, fetch, focus, interaction, semantic Details
scripts/deploy.py                 current-user Python LaunchAgent + native app build/install/rollback
scripts/check.py                  source/test regression and native static contract guards
tests/                            synthetic test definitions only
docs/                             design/API/plan/decisions
README.md                         operator instructions
metadata.json                     compact contract
```

## Verification

Source/test regression commands:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

`python3 scripts/check.py` statically guards the native source/Xcode contract but does not prove a Swift build or Location/CoreWLAN runtime. Native acceptance requires exact-revision deployment on macOS, successful Xcode build, visible Location authorization, a fresh `wifi_native` cache, and a topology snapshot containing the current BSSID.

Never report unexecuted tests/builds/runtime checks as PASS.

## Repository hygiene

Never commit real IPs, SSIDs, BSSIDs, hostnames, MAC addresses, LaunchAgent plists, native cache files, logs, packet captures, scan output, exported snapshots, build products, DerivedData, caches, or credentials. Test values are synthetic. No independent fixture directory is required.
