# HomeNetTopo Local API Contract

## Status and boundary

This document defines local API and topology schema version `1`. It is not evidence that the exact revision has run successfully.

- Base URL: `http://127.0.0.1:8765`
- Prefix: `/api/v1`
- Bind: IPv4 loopback only
- State: in-memory; no upload or automatic persistence
- GET routes never execute collection commands
- One collection runs at a time; successful snapshots publish atomically and failures preserve the previous snapshot

Every request requires Host `127.0.0.1:<port>` or `localhost:<port>`. Collection routes require JSON, `X-HomeNetTopo-Request: 1`, matching loopback Origin when present, and `Sec-Fetch-Site: same-origin` or `none` when present. No permissive CORS is emitted.

## Fixed limits

| Limit | Value |
|---|---:|
| JSON body | 16 KiB |
| Requested networks | 32 |
| Unique target addresses | 1024 |
| Active total timeout | default 30; range 5–120 seconds |
| Nmap host timeout | 5 seconds |
| Interface/route/ARP timeout | 5 seconds each, concurrent |
| Wi-Fi interface detection | 3 seconds |
| Wi-Fi profiler process/internal timeout | 8 / 5 seconds |
| Captured stdout/stderr | 2 MiB / 64 KiB |
| Kill grace | 2 seconds |

Material passive failures expose normalized `failed_sources`; `504 command_timeout` also exposes `timeout_sources`. Optional Wi-Fi detail failure alone does not return 504.

## Routes

```text
GET  /api/v1/health
GET  /api/v1/capabilities
GET  /api/v1/topology
GET  /api/v1/topology/export
POST /api/v1/topology/refresh
POST /api/v1/discover
```

Read-only routes never collect. No snapshot returns `404 not_found`. Collection conflicts return `409 collection_in_progress`.

## Capabilities

`GET /api/v1/capabilities` includes:

```json
{
  "link_path": {
    "wifi_interface_source": "networksetup",
    "wifi_bssid_source": "system_profiler",
    "wifi_local_fallback_configured": false,
    "ethernet_adjacent_device_source": "not_available_without_lldp"
  }
}
```

The fallback field is boolean only. The API never returns locally configured SSID/BSSID values through capabilities. Nmap capability exposes only resolution source, not executable path.

## Passive refresh

`POST /api/v1/topology/refresh` accepts `{}` and runs the fixed commands concurrently:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
```

Evidence roles:

| Source | Public meaning |
|---|---|
| `ifconfig inet` | local IPv4 addresses |
| `ifconfig ether` | current interface MAC, potentially a private Wi-Fi MAC |
| `networksetup Ethernet Address` | adapter hardware MAC |
| current profiler BSSID | serving Wi-Fi radio |
| profiler radio fields | SSID, channel, RSSI, noise, PHY, transmit rate |
| ARP | IP-neighbor evidence excluding local IPs and local MACs |

Nearby-network profiler entries are ignored. A redacted BSSID is never guessed. A configured fallback fills missing current-link identity but automatic BSSID evidence has priority.

## Active discovery

`POST /api/v1/discover` request:

```json
{
  "networks": ["192.168.1.0/24"],
  "operation_timeout_seconds": 30
}
```

Phase A validates request/security/body, canonical IPv4, RFC 1918 membership, 1–32 networks, at most 1024 unique addresses, and timeout before commands.

Phase B collects fresh interfaces, requires containment by eligible non-tunnel local RFC 1918 networks, assigns most-specific local owners, deduplicates only inside the same owner, preserves adjacent sibling targets and overlapping-owner targets, and recalculates the union.

Only then may the service run:

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <effective-targets...>
```

Nmap XML requires `nmaprun`; only `up` hosts are considered; IPv4 and optional MAC must be canonical and inside an effective target. Evidence matching any local IP or local current/hardware MAC is excluded from peer creation and from `hosts_reported_up`. Invalid Nmap evidence is `500 collection_failed`.

## Snapshot schema

```json
{
  "schema_version": "1",
  "snapshot_id": "local-generated-id",
  "collected_at": "2026-08-03T03:00:00Z",
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
local_configuration
nmap
address_membership
route_inference
link_path_inference
```

Node kinds:

```text
local_host
interface
access_point
link_boundary
subnet
gateway
device
upstream_boundary
```

### Local host and interface identity

The `local_host` node contains local IPv4 addresses, interface names, and all observed local current/hardware MAC addresses.

An `interface` node can contain:

```json
{
  "properties": {
    "kind": "physical",
    "current_mac_address": "02:00:00:00:10:01",
    "hardware_mac_address": "02:00:00:00:20:01",
    "private_wifi_mac_address": "02:00:00:00:10:01"
  }
}
```

Values are synthetic. `private_wifi_mac_address` appears only when the active Wi-Fi MAC differs from the adapter hardware MAC.

### Connected Wi-Fi node

A serving radio is represented as `access_point` for schema compatibility, but its role is explicitly AP-or-relay unless confirmed:

```json
{
  "kind": "access_point",
  "label": "Synthetic Wi-Fi",
  "mac_addresses": ["02:aa:bb:cc:dd:55"],
  "properties": {
    "connection": "Wi-Fi",
    "role": "relay",
    "identity": "BSSID configured locally",
    "ssid": "Synthetic Wi-Fi",
    "bssid": "02:aa:bb:cc:dd:55",
    "channel": "44 (5GHz, 80MHz)",
    "rssi_dbm": -41,
    "noise_dbm": -91,
    "phy_mode": "802.11ax",
    "transmit_rate_mbps": 1200
  }
}
```

Automatic canonical BSSID uses identity `BSSID observed` and high confidence. A local fallback uses source `local_configuration`, identity `BSSID configured locally`, and medium confidence. BSSID proves the serving radio but not main AP versus relay or physical identity with the gateway.

When no BSSID exists, a connected Wi-Fi node remains with role `access point or relay` and no invented MAC. Non-Wi-Fi links without LLDP/managed evidence use `Intermediate L2 path unknown`. Tunnel paths remain direct Layer-3 interface-to-gateway paths.

Peer `device` nodes remain subnet context, never transit hops. `member_of` is not forwarding order. Path edge types include `interface_associated_with`, `attachment_reaches_gateway`, `interface_reaches_link`, `interface_reaches_gateway`, `routes_to`, and `upstream_of`.

## Local service configuration

The service accepts these startup-only fallback arguments:

```text
--wifi-interface <bsd-interface>
--wifi-bssid <canonical-mac>
--wifi-ssid <1-to-32-byte-ssid>
--wifi-role access-point|relay
```

At least one fallback value requires `--wifi-interface`. Deployment writes them only to the current-user LaunchAgent ProgramArguments. They are not HTTP request fields and cannot be changed remotely through the API.

## Errors

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

## Browser response policy

The CSP permits repository fonts and `data:` fonts with `font-src 'self' data:` and rejects external script, style, and font origins.

## Compatibility

Application version and topology schema version are independent. Compatible source, property, capability, node, and edge additions are allowed within schema version `1`; existing meanings cannot change incompatibly.
