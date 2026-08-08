# HomeNetTopo Design

## Status

This document defines the intended architecture. Source presence is not evidence that Python tests, Node tests, Xcode build, CoreLocation authorization, CoreWLAN collection, LaunchAgent deployment, browser interaction, or real-network topology has succeeded.

## Goals

- Identify the current Wi-Fi radio through a real macOS application identity rather than depending on a background Python process.
- Keep the Mac's Private Wi-Fi MAC, adapter Hardware MAC, and serving BSSID as separate identities.
- Show an evidence-backed path from this Mac toward the gateway.
- Keep LAN peer devices outside the transit row.
- Keep hidden Ethernet Layer 2 explicit instead of inventing a switch.
- Bound active discovery to validated local RFC 1918 networks.
- Keep all service/UI traffic local and loopback-only.

## Architecture

```text
HomeNetTopo Wi-Fi.app
  CoreLocation permission
  CoreWLAN current interface
  SMAppService login launch
       │
       │ atomic local cache, <= 20 s old
       ▼
~/Library/Caches/HomeNetTopo/wifi-current.json
       │
       ▼
Python LaunchAgent on 127.0.0.1
  ifconfig / netstat / arp / networksetup / system_profiler
  optional bounded Nmap
       │
       ▼
validated topology snapshot
       │
       ▼
local browser UI
```

Production owners:

```text
macos/HomeNetTopoApp/           CoreLocation/CoreWLAN/ServiceManagement helper
server.py                       loopback API, native cache validation, collection lock, publication
homenettopo/interfaces.py       interface/Wi-Fi parsers and evidence precedence
homenettopo/topology.py         local identity, Wi-Fi/gateway path, peers, evidence/confidence
scripts/deploy.py               fixed Xcode build, native install, Python LaunchAgent lifecycle
web/                            static same-origin topology UI
```

The native app uses only Apple frameworks. The Python service uses only the Python standard library. Xcode command-line build support is required by deployment; Node.js 20+ is development-only.

## Why native Wi-Fi collection exists

The service needs current SSID/BSSID, not merely the name of the Wi-Fi BSD interface. The native helper owns the user-visible Location authorization flow and a long-lived CoreWLAN client. The Python LaunchAgent consumes only a short-lived evidence file and never attempts to impersonate an app permission context.

The helper:

1. launches as a normal foreground macOS app during install;
2. requests CoreLocation When-In-Use access;
3. keeps one shared `CWWiFiClient`;
4. obtains the default `CWInterface`;
5. reads current SSID, BSSID, channel, RSSI, noise, PHY mode, transmit rate, and local hardware address when available;
6. writes one atomic JSON cache every five seconds;
7. registers `SMAppService.mainApp` for login launch, subject to macOS user approval.

The helper is not sandboxed in this release and no location entitlement is used as a privacy bypass.

## Native cache trust boundary

Cache path:

```text
~/Library/Caches/HomeNetTopo/wifi-current.json
```

Schema version is `1`. The Python service requires:

- a regular non-symlink file;
- ownership by the current user;
- no group/world write permission;
- size at most 16 KiB;
- valid UTF-8/JSON/schema;
- valid canonical interface and MAC fields;
- valid authorization state;
- collection time no more than 20 seconds old and no more than five seconds in the future.

A denied/restricted/missing/stale/invalid cache never becomes BSSID evidence. Those states are normalized to a public-safe helper status and actionable warning. Capabilities expose helper status but never current Wi-Fi identity values.

## Wi-Fi identity model

Three identities are deliberately separate:

```text
ifconfig ether
  -> current MAC / Private Wi-Fi MAC
  -> local interface

networksetup Ethernet Address
  -> adapter Hardware MAC
  -> local interface

CoreWLAN BSSID
  -> current serving radio
  -> connected Wi-Fi node
```

The Hardware MAC from `networksetup` is authoritative once present. Later native association evidence cannot overwrite it.

BSSID precedence:

```text
wifi_native > wifi > local_configuration
```

where:

- `wifi_native` = fresh Location-authorized CoreWLAN cache;
- `wifi` = `system_profiler` current-association fallback;
- `local_configuration` = optional manually supplied fallback.

The user-confirmed role may survive an automatic identity replacement. For example, `role: relay` can coexist with a native BSSID while the BSSID remains observed rather than configured.

## Passive collection

The fixed subprocesses are:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
```

They run concurrent inside one passive collection. Interface, route, and ARP are material coherence evidence. `networksetup` provides fast Wi-Fi media classification and Hardware MAC. `system_profiler` is optional association fallback.

The native cache is a file read after command collection. It does not add a subprocess deadline.

Merge order is:

```text
networksetup media
→ system_profiler association
→ native CoreWLAN association
→ local fallback
```

Although local fallback is processed last, its configured fields fill only missing automatic values; it cannot replace an already observed BSSID. Native automatic fields override profiler association fields.

## Gateway path

### Wi-Fi with native/current BSSID

```text
local_host
  → host_uses_interface                 observed
interface
  → interface_associated_with           observed, high confidence
access_point/current Wi-Fi radio
  → attachment_reaches_gateway          inferred
gateway
  → upstream_of                         inferred
upstream_boundary
```

The Wi-Fi node stores BSSID only; local Private Wi-Fi MAC and Hardware MAC remain on host/interface nodes.

`identity_source: wifi_native` means a fresh native CoreWLAN association supplied the BSSID. The node can also carry SSID, Channel, RSSI, Noise, PHY, and transmit rate.

A BSSID establishes the currently associated radio, not the complete physical topology. It does not automatically prove main-AP versus relay role or mesh backhaul. User-confirmed role is a separate evidence dimension.

### Wi-Fi without BSSID

If `networksetup` proves that the default-route interface is Wi-Fi but neither native helper nor profiler supplies BSSID, the graph still retains a connected Wi-Fi boundary. It must not invent a BSSID and must expose why native identity is unavailable.

### Non-Wi-Fi

ARP maps IP neighbors to MAC addresses but does not enumerate transparent switches. Without LLDP/CDP or managed topology evidence, render:

```text
interface
  → Intermediate L2 path unknown
  → gateway
```

The boundary may represent direct attachment, switch, bridge, or other hidden Layer 2; it is uncertainty, not a device claim.

### Tunnel

A tunnel default route remains direct Layer 3:

```text
interface → gateway → upstream
```

No fabricated Wi-Fi or Layer-2 node is inserted.

## Local identity and LAN peers

All assigned IPv4 addresses and every known local Private Wi-Fi MAC / Hardware MAC are authoritative local identity. If ARP or validated Nmap repeats a local IP or local MAC, it is filtered before peer aggregation and before active host-count publication.

LAN peers appear in subnet context below the path. `member_of` is not a transit relationship.

A gateway ARP MAC equal to the BSSID can be positive `same_mac` evidence. A different gateway MAC remains `not_established`; one appliance can expose different radio and routed-interface MAC values.

## Active discovery

Phase A checks canonical IPv4, RFC 1918 scope, object/body/count/address limits, and operation timeout before commands. Phase B performs fresh passive collection and requires each target to equal or be contained by an eligible non-tunnel local interface network.

Adjacent sibling targets remain separate and are never widened. Only after both phases pass may Nmap run:

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <targets...>
```

Only up hosts with valid in-range IPv4 and canonical optional MAC values are accepted. Malformed/out-of-range output becomes `collection_failed`. No port, service, OS, vulnerability, credential, packet-capture, public, or reverse-DNS discovery is in scope.

## HTTP/browser security

The Python service binds only `127.0.0.1`. Accepted Host values are `127.0.0.1:<port>` and `localhost:<port>`. Collection POSTs require JSON, the custom `X-HomeNetTopo-Request: 1` header, and matching same-origin signals when present. No permissive CORS.

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

The CSP allows repository/data fonts but no external script/style/font origins. The frontend uses safe DOM/SVG construction and an SVG viewBox camera.

## Native deployment

`scripts/deploy.py` is the only deployment owner. Native source manifest is fixed to five repository files. Build commands are fixed to `/usr/bin/xcodebuild`, `/usr/bin/codesign`, and `/usr/bin/open`; Python lifecycle uses `/bin/launchctl`. No shell or sudo is used.

Install order:

1. validate Python/web and native source manifests;
2. build fixed Xcode target `HomeNetTopoApp` into a temporary build root;
3. validate bundle ID/privacy metadata/executable;
4. ad-hoc sign and verify the app;
5. stage Python/web runtime;
6. stop the old Python LaunchAgent;
7. atomically replace Python runtime and native app with rollback copies;
8. write and bootstrap the Python LaunchAgent;
9. require loopback health;
10. foreground-open the native app for Location authorization.

Native app path:

```text
~/Applications/HomeNetTopo Wi-Fi.app
```

Python runtime/path owners:

```text
~/Library/Application Support/HomeNetTopo
~/Library/LaunchAgents/com.homenettopo.local.plist
~/Library/Logs/HomeNetTopo
```

Uninstall asks the app to unregister its `SMAppService.mainApp` login item and removes the native app, cache, Python runtime, and LaunchAgent. Logs are retained unless explicitly purged.

## Testing and acceptance

Python tests cover native cache parsing/freshness, Wi-Fi merge priority, local MAC exclusion, topology identity source, HTTP states, and static deployment boundaries. Native source guards inspect the CoreLocation/CoreWLAN calls, privacy plist, ServiceManagement usage, Xcode project, and fixed source/build contract.

The source/test regression command is:

```text
python3 scripts/check.py
```

It does **not** build or execute the native app. Exact-revision release acceptance additionally requires macOS Xcode build, Location permission, a fresh native cache, current BSSID in the topology, LaunchAgent lifecycle, browser behavior, and bounded Nmap recovery/discovery where applicable.
