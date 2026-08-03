# HomeNetTopo Local API Contract

## Status

This contract defines the intended first implementation. It is not evidence that the endpoints already exist or run.

## General rules

- Base URL: `http://127.0.0.1:8765`
- API prefix: `/api/v1`
- Minimum Python runtime: 3.10
- JSON media type: `application/json; charset=utf-8`
- Bind: IPv4 loopback only
- No endpoint uploads or persists network data
- Timestamps: RFC 3339 UTC
- Breaking field or semantic changes require a new API or schema version
- Every GET endpoint is read-only and must not execute collection commands

## Fixed limits

| Limit | Value |
|---|---:|
| Maximum JSON body | 16 KiB |
| Maximum requested networks | 32 |
| Maximum unique target addresses | 1024 |
| Active-operation timeout default | 30 seconds |
| Active-operation timeout range | 5–120 seconds |
| Nmap per-host timeout | 5 seconds |
| Passive command timeout | 5 seconds |
| Captured stdout | 2 MiB |
| Captured stderr | 64 KiB |
| Timed-out process kill grace | 2 seconds |

`operation_timeout_seconds` is the total deadline enforced by the subprocess runner for the Nmap process. The Nmap command separately uses a fixed `--host-timeout 5s`.

## Host boundary

Every request must contain a Host value matching the configured loopback port.

Accepted forms for the default port:

```text
127.0.0.1:8765
localhost:8765
```

The allowlist is derived from the actual configured port. Missing, malformed, non-loopback, alternate-domain, IPv6-literal, or DNS-rebinding-style Host values return:

```text
400 invalid_host
```

The service must not use an untrusted Host value to construct redirects, links, origins, filenames, or error text.

## Protected collection boundary

These endpoints execute commands and therefore require same-origin request protection:

```text
POST /api/v1/topology/refresh
POST /api/v1/discover
```

Required headers:

```text
Content-Type: application/json
X-HomeNetTopo-Request: 1
```

When `Origin` is present, it must exactly match an accepted loopback origin for the configured port. When `Sec-Fetch-Site` is present, it must be `same-origin` or `none`.

A missing custom header, mismatched Origin, or cross-site Fetch Metadata value returns:

```text
403 cross_origin_request
```

The server emits no permissive CORS headers. API `OPTIONS` is not an authorization path and returns `405 method_not_allowed`.

## Collection concurrency

Only one passive or active collection may run at a time.

A second collection request returns immediately:

```text
409 collection_in_progress
```

It is not queued, merged, or allowed to start another command. A failed operation preserves the previous snapshot. A successful passive result, coherent partial passive result, or successful active result replaces the snapshot atomically.

## Error envelope

```json
{
  "error": {
    "code": "invalid_target",
    "message": "The requested network is not eligible for active discovery.",
    "details": {},
    "request_id": "local-request-id"
  }
}
```

Error codes:

- `bad_request`
- `invalid_json`
- `invalid_host`
- `cross_origin_request`
- `invalid_target`
- `target_too_large`
- `unsupported_platform`
- `dependency_unavailable`
- `collection_in_progress`
- `command_timeout`
- `collection_failed`
- `not_found`
- `method_not_allowed`
- `internal_error`

Messages must not expose raw command lines, unrestricted stderr, environment variables, or local filesystem paths. Details may contain validated field names, configured limits, eligibility reasons, source-status summaries, or Nmap resolution-source identifiers.

## `GET /api/v1/health`

Returns service identity without collecting network data.

### Response `200`

```json
{
  "status": "ok",
  "service": "homeNetTopo",
  "version": "0.1.0",
  "platform": "darwin"
}
```

On a non-macOS host, health may still return `200` with the normalized actual platform.

## `GET /api/v1/capabilities`

Returns platform, optional-tool availability, limits, and first-release feature flags without executing collection commands.

### Supported-platform example `200`

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
  "bind": "127.0.0.1",
  "port": 8765,
  "external_assets_required": false,
  "reverse_dns_enabled": false,
  "annotations_supported": false
}
```

Allowed `resolution_source` values:

- `explicit`
- `homebrew_arm64`
- `homebrew_intel`
- `path`
- `unavailable`

The full Nmap executable path is never returned.

### Unsupported-platform example `200`

```json
{
  "platform": "linux",
  "passive_collection": false,
  "active_discovery": {
    "available": false,
    "unavailable_reason": "unsupported_platform",
    "tool": "nmap",
    "resolution_source": "unavailable",
    "mode": "host-discovery-xml",
    "max_networks_per_request": 32,
    "max_addresses_per_request": 1024,
    "operation_timeout_default_seconds": 30,
    "operation_timeout_min_seconds": 5,
    "operation_timeout_max_seconds": 120,
    "host_timeout_seconds": 5
  },
  "bind": "127.0.0.1",
  "port": 8765,
  "external_assets_required": false,
  "reverse_dns_enabled": false,
  "annotations_supported": false
}
```

Capability reporting does not execute `ifconfig`, `netstat`, `arp`, or Nmap discovery.

## `GET /api/v1/topology`

Returns the latest in-memory snapshot without collecting or changing state.

Query parameters are not supported in schema version `1`; an unexpected query parameter returns `400 bad_request`.

### Success `200`

Uses the topology snapshot schema below.

### No snapshot

```text
404 not_found
```

The browser should call `POST /api/v1/topology/refresh` before the first read.

## `POST /api/v1/topology/refresh`

Performs passive macOS collection only. It must never invoke Nmap.

### Required headers

```text
Content-Type: application/json
X-HomeNetTopo-Request: 1
```

### Request

```json
{}
```

The body must be a JSON object with no fields in schema version `1`.

### Success `200`

Returns a passive snapshot and replaces the latest snapshot atomically.

A coherent partial result returns `200` with:

```json
{
  "mode": "passive",
  "partial": true,
  "warnings": [],
  "sources": []
}
```

### Expected failures

- `400 invalid_json`
- `400 bad_request`
- `400 invalid_host`
- `403 cross_origin_request`
- `409 collection_in_progress`
- `413 target_too_large` for body size overflow
- `415 bad_request` for unsupported content type
- `500 collection_failed` when no coherent snapshot can be produced
- `501 unsupported_platform`
- `504 command_timeout`

A failure preserves the previous snapshot.

## `POST /api/v1/discover`

Performs fresh passive collection followed by bounded Nmap host discovery. It returns one merged active snapshot.

### Required headers

```text
Content-Type: application/json
X-HomeNetTopo-Request: 1
```

### Request

```json
{
  "networks": ["192.168.1.0/24"],
  "operation_timeout_seconds": 30
}
```

`operation_timeout_seconds` is optional and defaults to 30.

### Validation Phase A — before lock and commands

1. validate Host and browser-origin boundary;
2. reject body larger than 16 KiB;
3. require a JSON object;
4. require `networks` with 1–32 string entries;
5. parse each item as a canonical IPv4 network;
6. reject loopback, link-local, multicast, unspecified, public, and reserved-only documentation ranges;
7. reject an absolute unique-address union above 1024;
8. validate `operation_timeout_seconds` as an integer from 5 through 120.

Phase A failure must not acquire the collection lock and must not execute any command.

### Validation Phase B — after fresh passive collection

Under the collection lock:

1. run approved passive commands;
2. derive eligible private IPv4 networks assigned to non-tunnel local interfaces;
3. require each requested target to be equal to or a subnet of one eligible local network;
4. reject supernets, partial overlaps, adjacent networks, tunnel-only networks, and unrelated private ranges;
5. collapse duplicate or contained targets;
6. recalculate the final unique-address union and require at most 1024 addresses.

Passive commands are permitted between Phase A and Phase B because they establish current local eligibility. **Nmap must not be resolved or invoked until both phases pass.**

### Nmap command

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <validated-targets...>
```

The subprocess runner enforces `operation_timeout_seconds` as the total process deadline. XML stdout is parsed with `xml.etree.ElementTree`. Only host-up address and status evidence is accepted; port, service, OS, script, and name-resolution data are ignored or rejected.

### Success `200`

```json
{
  "schema_version": "1",
  "snapshot_id": "local-generated-id",
  "collected_at": "2026-08-03T03:00:00Z",
  "mode": "active",
  "platform": "darwin",
  "partial": false,
  "warnings": [],
  "sources": [],
  "networks": [],
  "nodes": [],
  "edges": [],
  "active_discovery": {
    "requested_networks": ["192.168.1.0/24"],
    "effective_networks": ["192.168.1.0/24"],
    "completed": true,
    "duration_ms": 1200,
    "hosts_reported_up": 4,
    "operation_timeout_seconds": 30,
    "host_timeout_seconds": 5,
    "output_format": "xml"
  }
}
```

The successful merged snapshot replaces the latest snapshot atomically.

### Expected failures

- `400 invalid_json`
- `400 bad_request`
- `400 invalid_target`
- `400 invalid_host`
- `403 cross_origin_request`
- `409 collection_in_progress`
- `413 target_too_large`
- `415 bad_request`
- `424 dependency_unavailable`
- `500 collection_failed`
- `501 unsupported_platform`
- `504 command_timeout`

A failed active operation preserves the previous snapshot and does not publish its intermediate passive data.

## `GET /api/v1/topology/export`

Downloads the latest snapshot without collecting, modifying, persisting, or uploading data.

### Success `200`

```text
Content-Type: application/json; charset=utf-8
Content-Disposition: attachment; filename="home-network-topology.json"
Cache-Control: no-store
```

### No snapshot

```text
404 not_found
```

## Topology snapshot schema

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

### Source schema

```json
{
  "type": "interfaces",
  "status": "ok",
  "message": null,
  "duration_ms": 14
}
```

Source types:

- `interfaces`
- `routes`
- `neighbors`
- `nmap`
- `address_membership`
- `route_inference`

Source statuses:

- `ok`
- `warning`
- `failed`
- `not_run`

### Network schema

```json
{
  "cidr": "192.168.1.0/24",
  "interface": "en0",
  "interface_kind": "physical",
  "eligible_for_active_discovery": true,
  "eligibility_reason": "eligible_private_local_network",
  "address_count": 256
}
```

`interface_kind` includes `physical`, `virtual`, and `tunnel`. Tunnel networks are never active-discovery eligible in schema version `1`.

### Evidence schema

```json
{
  "source": "arp",
  "observed_at": "2026-08-03T03:00:00Z",
  "summary": "Neighbor cache entry",
  "properties": {}
}
```

Evidence summaries must not contain raw command lines or unrestricted stderr.

### Node schema

```json
{
  "id": "device:192.168.1.10",
  "kind": "device",
  "label": "Living Room TV",
  "addresses": ["192.168.1.10"],
  "mac_addresses": ["02:00:00:00:00:10"],
  "interface_names": [],
  "properties": {},
  "evidence": [],
  "confidence": "high",
  "observed_at": "2026-08-03T03:00:00Z"
}
```

Node kinds:

- `local_host`
- `interface`
- `subnet`
- `gateway`
- `device`
- `upstream_boundary`

A label may use a name already present in approved local command output. The service performs no separate reverse-DNS or online lookup.

### Edge schema

```json
{
  "id": "edge:device:192.168.1.10:subnet:192.168.1.0-24",
  "source": "device:192.168.1.10",
  "target": "subnet:192.168.1.0-24",
  "type": "member_of",
  "observed": false,
  "confidence": "medium",
  "evidence": [],
  "properties": {}
}
```

Edge types:

- `host_uses_interface`
- `interface_attached_to_subnet`
- `gateway_for_subnet`
- `member_of`
- `routes_to`
- `upstream_of`

Every edge endpoint must reference a node in the same snapshot.

## Response headers

HTML, static, and API responses use restrictive local-application headers:

```text
Cache-Control: no-store
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), usb=()
Content-Security-Policy: default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'
```

No `Access-Control-Allow-Origin` header is emitted.

## Static route behavior

- `/` serves `web/index.html`.
- Explicit local asset paths serve regular files under the canonical `web/` root.
- Directory listing is disabled.
- Unknown static paths return `404`.
- Raw or encoded traversal, repeated decoding, NUL bytes, alternate separators, and symlink escape are rejected.
- Undefined API and static methods return `405` as appropriate.

## Compatibility

- `schema_version` governs topology JSON.
- Application version and schema version are independent.
- Existing field names and meanings cannot change incompatibly inside schema version `1`.
- Materially new behavior requires compatible fields or a schema/API version change.
