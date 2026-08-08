# HomeNetTopo Local API Contract

## Status

This document defines topology schema version `1` and the loopback API. It is not evidence that the exact revision has passed Python tests, Node tests, Xcode build, Location authorization, CoreWLAN runtime, LaunchAgent deployment, or browser acceptance.

## Runtime boundary

Base URL defaults to:

```text
http://127.0.0.1:8765
```

Accepted Host values are only `127.0.0.1:<port>` and `localhost:<port>`. Read-only GET routes never execute interface, route, ARP, Wi-Fi, or Nmap commands.

Collection POST routes require:

```text
Content-Type: application/json
X-HomeNetTopo-Request: 1
```

When supplied, Origin must match the loopback origin and `Sec-Fetch-Site` must be `same-origin` or `none`. No permissive CORS is emitted. One collection runs at a time; another receives `409 collection_in_progress`.

The Python service is a current-user LaunchAgent and remains bound to loopback. The native Wi-Fi helper is a current-user macOS app built with Xcode and installed at `~/Applications/HomeNetTopo Wi-Fi.app`.

## Current Wi-Fi identity

Modern Wi-Fi identity is represented by three separate local/link identities:

- **Private Wi-Fi MAC / current MAC**: `ifconfig ether`, belongs to the Mac/interface;
- **Hardware MAC**: `networksetup -listallhardwareports`, belongs to the local adapter;
- **BSSID**: current serving Wi-Fi radio, belongs to the connected Wi-Fi node.

Current BSSID precedence:

```text
wifi_native (CoreLocation-authorized CoreWLAN helper)
  > wifi (system_profiler current association)
  > local_configuration
```

The helper requests Location permission while foreground and publishes a local cache:

```text
~/Library/Caches/HomeNetTopo/wifi-current.json
```

The cache is accepted only when it is a current-user-owned regular non-symlink file, not group/world writable, at most 16 KiB, schema version 1, valid UTF-8 JSON, and at most 20 seconds old.

Example schema with synthetic values:

```json
{
  "schema_version": 1,
  "collected_at": "2026-08-08T12:00:00Z",
  "authorization": "authorized",
  "wifi": {
    "interface": "en0",
    "ssid": "Synthetic Wi-Fi",
    "bssid": "02:aa:bb:cc:dd:42",
    "hardware_mac_address": "02:00:00:00:20:01",
    "channel": "40",
    "rssi_dbm": -35,
    "noise_dbm": -90,
    "phy_mode": "802.11ax",
    "transmit_rate_mbps": 2401
  }
}
```

Authorization states are `authorized`, `not_determined`, `denied`, `restricted`, and `unknown`. A non-null `wifi` object is valid only with `authorized`. Stale, denied, restricted, malformed, wrong-owner, or unsafe-permission files cannot become BSSID evidence.

## Fixed passive command sources

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
```

These fixed sources launch concurrent inside one passive collection. Interface, route, and ARP are material coherence sources. `networksetup` identifies Wi-Fi media and local Hardware MAC. `system_profiler` is optional current-association fallback. Native CoreWLAN cache reading is not a subprocess.

## Errors

Envelope:

```json
{
  "error": {
    "code": "command_timeout",
    "message": "Passive collection timed out in: interfaces.",
    "details": {
      "failed_sources": ["interfaces"],
      "timeout_sources": ["interfaces"]
    },
    "request_id": "local-request-id"
  }
}
```

Codes include:

```text
bad_request
invalid_json
invalid_host
cross_origin_request
invalid_target
target_too_large
unsupported_platform
dependency_unavailable
collection_in_progress
command_timeout
collection_failed
not_found
method_not_allowed
internal_error
```

Optional profiler or native-helper identity failure alone does not produce a `504`. Native helper problems appear as `wifi_native` warning state when no automatic BSSID is otherwise available.

## `GET /api/v1/health`

Read-only service identity:

```json
{
  "status": "ok",
  "service": "homeNetTopo",
  "version": "0.1.0",
  "platform": "darwin"
}
```

## `GET /api/v1/capabilities`

Read-only capability response. Relevant `link_path` shape:

```json
{
  "link_path": {
    "wifi_interface_source": "networksetup",
    "wifi_bssid_source": "corewlan_native_then_system_profiler",
    "wifi_native_helper": {
      "status": "ready",
      "message": "Location-authorized CoreWLAN helper supplied fresh Wi-Fi identity.",
      "launch_url": "homenettopo-wifi://authorize"
    },
    "wifi_local_fallback_configured": false,
    "ethernet_adjacent_device_source": "not_available_without_lldp"
  }
}
```

Helper `status` may be `ready`, `missing`, `stale`, `not_determined`, `denied`, `restricted`, `no_association`, `invalid`, or `unsupported`.

Capabilities never return the current SSID, BSSID, Hardware MAC, Private Wi-Fi MAC, native cache contents, or manual fallback values.

## `GET /api/v1/topology`

Returns the latest snapshot. No snapshot returns `404 not_found`. GET does not collect.

## `GET /api/v1/topology/export`

Returns the same latest snapshot as a download:

```text
Content-Type: application/json; charset=utf-8
Content-Disposition: attachment; filename="home-network-topology.json"
Cache-Control: no-store
```

## `POST /api/v1/topology/refresh`

Request:

```json
{}
```

Flow:

1. validate Host and same-origin collection headers;
2. acquire the single collection lock;
3. launch the five fixed passive command sources concurrent;
4. validate material coherence;
5. read fresh native CoreWLAN cache;
6. merge Wi-Fi evidence in order `networksetup → system_profiler → wifi_native → local_configuration`, where later automatic BSSID wins but `networksetup` Hardware MAC remains authoritative;
7. construct and validate the snapshot;
8. publish atomically.

If native BSSID is fresh it becomes source `wifi_native`. If native identity is unavailable but profiler has a BSSID, profiler remains valid fallback. Local configuration can fill only otherwise missing BSSID/role data.

## `POST /api/v1/discover`

Request example:

```json
{
  "networks": ["192.168.1.0/24"],
  "operation_timeout_seconds": 30
}
```

Phase A validates structure, canonical IPv4, RFC 1918 scope, network/address limits, and timeout before commands. Phase B performs fresh passive collection and requires every requested target to equal or be contained by an eligible non-tunnel local network.

Adjacent sibling targets remain separate. Supernets, partial overlaps, unrelated RFC 1918 ranges, public/special networks, tunnel-only networks, and requests above fixed limits are rejected.

Only after both phases pass may the service run:

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <effective-targets...>
```

Only `up` hosts with valid in-target IPv4 and canonical optional MAC values are retained. Malformed or out-of-target evidence is `500 collection_failed` and preserves the previous snapshot.

## Limits

| Limit | Value |
|---|---:|
| JSON request body | 16 KiB |
| Requested networks | 32 |
| Unique target addresses | 1024 |
| Active total timeout | default 30; range 5–120 seconds |
| Nmap host timeout | 5 seconds |
| Interface/route/ARP timeout | 5 seconds each |
| Wi-Fi interface command timeout | 3 seconds |
| Wi-Fi profiler process timeout | 8 seconds |
| Native cache size | 16 KiB |
| Native cache maximum age | 20 seconds |
| Native helper refresh interval | 5 seconds |

## Snapshot schema

Top-level shape:

```json
{
  "schema_version": "1",
  "snapshot_id": "generated-id",
  "collected_at": "2026-08-08T12:00:00Z",
  "mode": "passive",
  "platform": "darwin",
  "partial": false,
  "warnings": [],
  "sources": [],
  "networks": [],
  "nodes": [],
  "edges": []
}
```

Source types include:

```text
interfaces
routes
neighbors
wifi_interfaces
wifi
wifi_native
local_configuration
nmap
address_membership
route_inference
link_path_inference
```

Source statuses are `ok`, `warning`, `failed`, and `not_run`.

### Wi-Fi node semantics

When BSSID is available, `access_point` represents the **current connected Wi-Fi radio**. Properties may include:

```text
role
ssid
bssid
channel
rssi_dbm
noise_dbm
phy_mode
transmit_rate_mbps
identity
identity_source
```

`identity_source: wifi_native` means a fresh Location-authorized CoreWLAN cache supplied the BSSID. That identity is high-confidence current association evidence.

A BSSID does not automatically prove whether the physical appliance is the main access point or a relay. A user-confirmed `role: relay` may coexist with native BSSID evidence.

### Local identity exclusion

Local IPv4, current/Private Wi-Fi MAC, and Hardware MAC values are authoritative local identity. ARP or Nmap entries repeating those values cannot create peer nodes and cannot inflate `active_discovery.hosts_reported_up`.

### Gateway and hidden Layer 2

A matching BSSID and gateway ARP MAC can establish `same_mac`. Different MAC addresses remain `not_established`, not proof of separate hardware.

ARP, route, and traceroute-style evidence cannot enumerate ordinary transparent switching. Without LLDP/CDP or managed topology evidence, a non-Wi-Fi path uses `link_boundary` labelled `Intermediate L2 path unknown`. LAN peer nodes remain subnet context and are never transit hops.

## Browser policy

The browser UI is same-origin only and uses safe DOM/SVG construction. The CSP allows repository/data fonts but no external scripts, styles, or font origins. The Details view renders Hardware MAC, Private Wi-Fi MAC, BSSID, SSID, Channel, RSSI, Noise, PHY mode, transmit rate, role, evidence, and confidence when supplied by the snapshot.
