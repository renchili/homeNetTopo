# HomeNetTopo Local API Contract

## Status

This contract describes the intended first implementation. Endpoint availability must not be claimed until matching source exists.

## General rules

- Base URL: `http://127.0.0.1:8765`
- API prefix: `/api/v1`
- Minimum Python runtime: 3.10
- JSON media type: `application/json; charset=utf-8`
- The service binds to IPv4 loopback only in the first release.
- Passive collection and active host discovery are separate operations.
- Timestamps use RFC 3339 UTC strings.
- Unknown response fields may be added compatibly; clients must ignore unknown fields.
- Breaking field or semantic changes require a new schema or API version.
- No endpoint persists or uploads network data.

## Fixed limits

| Limit | Value |
|---|---:|
| Maximum JSON request body | 16 KiB |
| Maximum requested networks | 32 |
| Maximum unique target addresses | 1024 |
| Active timeout default | 30 seconds |
| Active timeout minimum | 1 second |
| Active timeout maximum | 120 seconds |
| Passive command timeout | 5 seconds |
| Captured stdout per command | 2 MiB |
| Captured stderr per command | 64 KiB |
| Timed-out process kill grace | 2 seconds |

Requests exceeding a documented HTTP limit fail before command invocation.

## Request Host boundary

Every request must contain a Host value matching the configured loopback port.

For the default port, accepted forms are:

```text
127.0.0.1:8765
localhost:8765
```

The allowlist is derived from the actual configured loopback port. Missing, malformed, non-loopback, alternate-domain, or DNS-rebinding-style values return:

```text
400 invalid_host
```

The service does not trust arbitrary Host values for origin construction, redirects, links, or error content.

## State-changing browser request boundary

`POST /api/v1/discover` requires:

```text
Content-Type: application/json
X-HomeNetTopo-Request: 1
```

When `Origin` is present, it must exactly match an accepted loopback origin for the configured port. When `Sec-Fetch-Site` is present, it must be `same-origin` or `none`.

Failure returns:

```text
403 cross_origin_request
```

The server must not emit permissive CORS headers. An API `OPTIONS` request is not an alternative authorization path and returns `405 method_not_allowed` unless a later version explicitly defines otherwise.

## Collection concurrency

The service permits only one passive or active collection at a time.

A second request that would start collection returns immediately:

```text
409 collection_in_progress
```

The request is not queued, merged, or allowed to invoke another subprocess. A failed collection preserves the previous snapshot. A successful or coherent partial collection replaces it atomically.

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

Messages must be useful without exposing arbitrary command output, environment variables, or local filesystem details. `details` may include validated field names, configured limits, eligibility reasons, or source-status summaries.

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

On a non-macOS host, health may still return `200` with the actual normalized platform. Collection endpoints remain unsupported.

## `GET /api/v1/capabilities`

Returns runtime, platform, optional-tool, and public-limit information without collecting topology.

### Response `200`

```json
{
  "passive_collection": true,
  "active_discovery": {
    "available": true,
    "tool": "nmap",
    "mode": "host-discovery-only",
    "max_networks_per_request": 32,
    "max_addresses_per_request": 1024,
    "timeout_default_seconds": 30,
    "timeout_min_seconds": 1,
    "timeout_max_seconds": 120
  },
  "bind": "127.0.0.1",
  "port": 8765,
  "external_assets_required": false,
  "reverse_dns_enabled": false,
  "annotations_supported": false
}
```

Capability availability is informative. Every active request is still validated.

## `GET /api/v1/topology`

Returns a passive snapshot.

### Query parameter

`refresh` accepts only `true` or `false`.

- omitted or `refresh=true`: start a new passive collection;
- `refresh=false`: return the latest in-memory snapshot without collecting;
- `refresh=false` with no snapshot: return `404 not_found`.

The endpoint must never invoke Nmap.

### Success `200`

```json
{
  "schema_version": "1",
  "snapshot_id": "local-generated-id",
  "collected_at": "2026-08-03T01:00:00Z",
  "mode": "passive",
  "platform": "darwin",
  "partial": false,
  "warnings": [],
  "sources": [
    {
      "type": "interfaces",
      "status": "ok"
    },
    {
      "type": "routes",
      "status": "ok"
    },
    {
      "type": "neighbors",
      "status": "ok"
    }
  ],
  "networks": [
    {
      "cidr": "192.0.2.0/24",
      "interface": "en0",
      "eligible_for_active_discovery": false,
      "eligibility_reason": "documentation_example_address"
    }
  ],
  "nodes": [],
  "edges": []
}
```

The example uses documentation-reserved addressing and is not an eligible active target.

### Expected failures

- `400 bad_request` for invalid query values;
- `404 not_found` for `refresh=false` without a snapshot;
- `409 collection_in_progress` when a new passive collection is requested while another collection runs;
- `500 collection_failed` when no coherent snapshot can be produced;
- `501 unsupported_platform` on unsupported collection platforms.

A coherent partial result returns `200` with `partial=true`, source-status failures, and warnings.

## `POST /api/v1/discover`

Performs a fresh passive collection followed by explicit bounded Nmap host discovery and returns one merged snapshot.

### Required headers

```text
Content-Type: application/json
X-HomeNetTopo-Request: 1
```

Host, Origin, and Fetch Metadata rules from the general contract apply.

### Request

```json
{
  "networks": ["192.168.1.0/24"],
  "timeout_seconds": 30
}
```

`timeout_seconds` is optional and defaults to 30.

### Validation order

1. validate Host and browser-origin boundary;
2. reject body larger than 16 KiB;
3. require JSON object body;
4. require `networks` with 1–32 string entries;
5. parse canonical IPv4 networks;
6. reject public, loopback, link-local, multicast, unspecified, reserved-only, unrelated private, and tunnel-only targets;
7. collapse overlapping networks and count unique addresses;
8. reject totals above 1024;
9. validate integer timeout from 1 through 120;
10. resolve Nmap and construct the fixed argument array.

No process invocation may happen before validation completes.

### Success `200`

The response uses the topology snapshot shape with:

```json
{
  "mode": "active",
  "active_discovery": {
    "requested_networks": ["192.168.1.0/24"],
    "completed": true,
    "duration_ms": 1200,
    "hosts_reported_up": 4,
    "timeout_seconds": 30
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
- `415 bad_request` for unsupported content type
- `424 dependency_unavailable`
- `500 collection_failed`
- `501 unsupported_platform`
- `504 command_timeout`

A failed active operation preserves the previous snapshot and does not publish the intermediate passive collection.

## `GET /api/v1/topology/export`

Downloads the latest in-memory snapshot without collecting, modifying, persisting, or uploading data.

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

The user must first load or refresh topology. The export contains only the server snapshot; the first release has no user annotation layer.

## Snapshot source schema

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

Source status values:

- `ok`
- `warning`
- `failed`
- `not_run`

## Network schema

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

`interface_kind` initially includes `physical`, `virtual`, and `tunnel`. Tunnel networks are not active-discovery eligible.

## Evidence schema

```json
{
  "source": "arp",
  "observed_at": "2026-08-03T01:00:00Z",
  "summary": "Neighbor cache entry",
  "properties": {}
}
```

Evidence summaries must not contain raw command lines or unrestricted stderr.

## Node schema

```json
{
  "id": "device:192.168.1.10",
  "kind": "device",
  "label": "Living Room TV",
  "addresses": ["192.168.1.10"],
  "mac_addresses": ["02:00:00:00:00:10"],
  "interface_names": [],
  "properties": {},
  "evidence": [
    {
      "source": "arp",
      "observed_at": "2026-08-03T01:00:00Z",
      "summary": "Neighbor cache entry",
      "properties": {}
    }
  ],
  "confidence": "high",
  "observed_at": "2026-08-03T01:00:00Z"
}
```

Node kinds:

- `local_host`
- `interface`
- `subnet`
- `gateway`
- `device`
- `upstream_boundary`

A label may use a hostname already present in approved command output. The server does not perform a separate reverse-DNS or online lookup.

## Edge schema

```json
{
  "id": "edge:device:192.168.1.10:subnet:192.168.1.0-24",
  "source": "device:192.168.1.10",
  "target": "subnet:192.168.1.0-24",
  "type": "member_of",
  "observed": false,
  "confidence": "medium",
  "evidence": [
    {
      "source": "address_membership",
      "summary": "Address belongs to subnet",
      "properties": {}
    }
  ],
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

HTML and API responses use restrictive headers appropriate to a local application:

```text
Cache-Control: no-store
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), usb=()
Content-Security-Policy: default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'
```

Static immutable asset caching may be introduced only with content-addressed filenames and matching documentation. The first release defaults to `no-store` for simplicity.

## Static route behavior

- `/` serves `web/index.html`.
- Explicit repository-owned asset paths serve regular files from `web/`.
- Directory listing is disabled.
- Unknown static paths return `404`.
- Raw or encoded traversal, NUL bytes, separator ambiguity, and symlink escape are rejected.
- API and static methods not defined by this contract return `405 method_not_allowed` or a minimal static `405` response as appropriate.

## Compatibility

- `schema_version` governs topology JSON.
- Application version and schema version are independent.
- Existing field names and meanings cannot change incompatibly within schema version `1`.
- New enum values require clients to retain unknown-value resilience or a schema version change when they alter behavior materially.
