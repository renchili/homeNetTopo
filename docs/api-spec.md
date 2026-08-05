# HomeNetTopo Local API Contract

## Status

This document defines local API and topology schema version `1`. It is not evidence that the exact revision has run successfully.

## General boundary

- Base URL: `http://127.0.0.1:8765`
- Prefix: `/api/v1`
- JSON: `application/json; charset=utf-8`
- Bind: IPv4 loopback only
- State: in-memory; no upload or automatic persistence
- Timestamps: RFC 3339 UTC
- GET routes are read-only and never execute collection commands

Every request requires Host `127.0.0.1:<port>` or `localhost:<port>`. Missing, malformed, non-loopback, alternate-domain, IPv6-literal, or rebinding-style Host values return `400 invalid_host`.

Collection routes require:

```text
Content-Type: application/json
X-HomeNetTopo-Request: 1
```

When present, Origin must match an accepted loopback origin and `Sec-Fetch-Site` must be `same-origin` or `none`. Cross-origin failures return `403 cross_origin_request`. The service emits no permissive CORS and API OPTIONS returns `405 method_not_allowed`.

Only one collection runs at a time. Another client receives `409 collection_in_progress`; requests are not queued or merged. Independent fixed passive commands may execute concurrently inside that one collection. Successful snapshots replace state atomically. Failures preserve the previous snapshot.

## Fixed limits

| Limit | Value |
|---|---:|
| JSON body | 16 KiB |
| Requested networks | 32 |
| Unique target addresses | 1024 |
| Active total timeout | default 30; range 5–120 seconds |
| Nmap host timeout | 5 seconds |
| Interface/route/ARP timeout | 5 seconds each, concurrent |
| Wi-Fi interface detection timeout | 3 seconds |
| Wi-Fi profiler process timeout | 8 seconds |
| Wi-Fi profiler internal timeout | 5 seconds |
| Captured stdout | 2 MiB |
| Captured stderr | 64 KiB |
| Kill grace | 2 seconds |

## Error envelope

```json
{
  "error": {
    "code": "command_timeout",
    "message": "Passive collection timed out in: interfaces, routes.",
    "details": {
      "failed_sources": ["interfaces", "routes"],
      "timeout_sources": ["interfaces", "routes"]
    },
    "request_id": "local-request-id"
  }
}
```

`failed_sources` and `timeout_sources` contain only normalized source identifiers, never raw command lines, stderr, environment values, or filesystem paths. Optional Wi-Fi profiler failure alone does not return `504`; it is represented in snapshot source status and warnings when material evidence is coherent.

Codes:

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

## `GET /api/v1/health`

Returns service identity without collecting:

```json
{
  "status": "ok",
  "service": "homeNetTopo",
  "version": "0.1.0",
  "platform": "darwin"
}
```

## `GET /api/v1/capabilities`

Returns capability data without executing interface, route, ARP, Wi-Fi, or Nmap collection:

```json
{
  "platform": "darwin",
  "passive_collection": true,
  "active_discovery": {
    "available": true,
    "unavailable_reason": null,
    "tool": "nmap",
    "resolution_source": "homebrew_arm64",
    "mode": "host-discovery-xml",
    "max_networks_per_request": 32,
    "max_addresses_per_request": 1024,
    "operation_timeout_default_seconds": 30,
    "operation_timeout_min_seconds": 5,
    "operation_timeout_max_seconds": 120,
    "host_timeout_seconds": 5
  },
  "link_path": {
    "wifi_interface_source": "networksetup",
    "wifi_bssid_source": "system_profiler",
    "ethernet_adjacent_device_source": "not_available_without_lldp"
  },
  "bind": "127.0.0.1",
  "port": 8765,
  "external_assets_required": false,
  "reverse_dns_enabled": false,
  "annotations_supported": false
}
```

Allowed Nmap resolution sources are `explicit`, `homebrew_arm64`, `homebrew_intel`, `path`, and `unavailable`. The full executable path is never returned.

`networksetup` identifies Wi-Fi BSD interfaces. `system_profiler` optionally enriches current SSID/BSSID. `link_path` documents evidence availability, not a claim that LLDP is implemented. The first release cannot guarantee Ethernet adjacent-device identity without LLDP or managed-topology evidence.

When Nmap is unavailable, the browser retains passive use and exposes an explicit capability recheck. A successful passive refresh also re-reads capabilities before releasing the browser collection owner.

## Read-only topology routes

`GET /api/v1/topology` returns the latest snapshot without collecting. No snapshot returns `404 not_found`; query parameters return `400 bad_request`.

`GET /api/v1/topology/export` downloads the latest snapshot without collecting or mutating:

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

Performs passive macOS collection only and never invokes Nmap. Fixed commands are:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
```

All five commands start concurrently. The collection still has one server lock owner; concurrency is internal and cannot start a second collection.

Interface, route, and ARP are material coherence sources. `wifi_interfaces` is fast media evidence from `networksetup`; `wifi` is best-effort current-association detail from `system_profiler`.

- If profiler detail succeeds, SSID/BSSID enriches the Wi-Fi attachment.
- If profiler detail times out or fails to parse, `wifi` is failed with a warning while `wifi_interfaces` may still prevent a Wi-Fi default route from being mislabeled as Ethernet.
- A coherent material result returns `200`, possibly with `partial: true`.
- If all material evidence is incoherent, return `500 collection_failed` or `504 command_timeout`; details identify `failed_sources` and `timeout_sources`.

The Wi-Fi parsers retain only hardware-port/current-association data and ignore nearby-network lists. A redacted BSSID is unavailable and is never guessed.

Expected errors include `400 invalid_json`, `400 bad_request`, `400 invalid_host`, `403 cross_origin_request`, `409 collection_in_progress`, `413 target_too_large`, `415 bad_request`, `500 collection_failed`, `501 unsupported_platform`, and `504 command_timeout`.

## `POST /api/v1/discover`

Request:

```json
{
  "networks": ["192.168.1.0/24"],
  "operation_timeout_seconds": 30
}
```

### Phase A

Before lock acquisition and commands:

1. validate Host and same-origin boundary;
2. enforce the 16 KiB body limit;
3. require an object with 1–32 canonical network strings;
4. require RFC 1918 membership in `10.0.0.0/8`, `172.16.0.0/12`, or `192.168.0.0/16`;
5. reject loopback, link-local, multicast, unspecified, public, documentation, reserved, and every non-RFC1918 range;
6. enforce at most 1024 unique addresses;
7. validate timeout from 5 through 120 seconds.

### Phase B

After fresh passive collection, under the lock:

1. require usable interface evidence;
2. derive eligible RFC 1918 networks on non-tunnel interfaces;
3. require each target to equal or be contained by one eligible network;
4. assign each target to its most-specific containing local network;
5. reject supernets, partial overlaps, adjacent networks outside the owner, unrelated RFC 1918 ranges, non-RFC1918 ranges, and tunnel-only ranges;
6. remove exact duplicates and contained targets only within the same owner group;
7. preserve adjacent sibling targets and targets owned by different overlapping local networks;
8. recalculate the final address union.

Interface timeout returns `504 command_timeout`. Unavailable or unparseable interface evidence returns `500 collection_failed`. Successful interface evidence with no eligible network returns `400 invalid_target`.

Only after both phases pass may the service resolve and run:

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <effective-targets...>
```

Nmap XML must have an `nmaprun` root. Only `up` hosts are considered. Every accepted IPv4 must be valid and belong to at least one effective target. Optional MAC values normalize to six lowercase hexadecimal octets. Duplicate hosts reduce deterministically. Malformed or out-of-effective-target evidence returns `500 collection_failed` and cannot publish a snapshot.

Expected errors additionally include `424 dependency_unavailable`. A failed active operation preserves the previous snapshot and does not publish fresh intermediate passive data.

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

Active snapshots additionally contain `active_discovery` with requested/effective networks, completion, duration, validated host count, total timeout, fixed host timeout, and XML output format. `effective_networks` never widens adjacent sibling targets or collapses across owner groups.

### Source types

```text
interfaces
routes
neighbors
wifi_interfaces
wifi
nmap
address_membership
route_inference
link_path_inference
```

Source statuses are `ok`, `warning`, `failed`, and `not_run`.

### Network and topology semantics

Network descriptors expose canonical CIDR, interface, interface kind, active eligibility, reason, and address count. Tunnel networks are not active-discovery eligible.

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

`access_point` has three evidence levels:

- canonical BSSID: observed current AP radio;
- current association without BSSID: observed AP boundary with unavailable identity;
- Wi-Fi interface plus default route: inferred AP boundary with unavailable identity.

A non-Wi-Fi path without LLDP/managed evidence uses `link_boundary` labelled `Intermediate L2 path unknown`. Peer `device` nodes remain subnet members, not transit hops.

Edge types:

```text
host_uses_interface
interface_associated_with
interface_reaches_link
attachment_reaches_gateway
interface_reaches_gateway
interface_attached_to_subnet
gateway_for_subnet
member_of
routes_to
upstream_of
```

An `interface_associated_with` edge is observed when association data exists and inferred when only Wi-Fi media plus the default route is known. `member_of` is peer context, never transit order. `routes_to` and `upstream_of` are Layer-3 inference. Every edge exposes observed status, confidence, evidence, and properties; the schema does not claim physical wiring.

## Browser response policy

The CSP permits repository-owned fonts and `data:` fonts with `font-src 'self' data:`. It does not permit external font origins, external scripts, or external styles.

## Compatibility

Application version and topology schema version are independent. Existing field names and meanings cannot change incompatibly inside schema version `1`. Compatible node, edge, source, capability, and property additions are allowed when documented by this contract.
