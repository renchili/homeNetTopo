# HomeNetTopo Local API Contract

## Status

This contract describes the intended first implementation. Endpoint availability must not be claimed until matching source exists.

## General rules

- Base URL: `http://127.0.0.1:8765`
- API prefix: `/api/v1`
- Media type: `application/json; charset=utf-8`
- The service is local-only by default.
- Passive collection and active host discovery are separate operations.
- Timestamps use RFC 3339 UTC strings.
- Unknown fields may be added in backward-compatible revisions; clients must ignore fields they do not understand.

## Error envelope

```json
{
  "error": {
    "code": "invalid_target",
    "message": "The requested network is not eligible for active discovery.",
    "details": {},
    "request_id": "optional-local-request-id"
  }
}
```

Planned error codes:

- `bad_request`
- `invalid_json`
- `invalid_target`
- `target_too_large`
- `unsupported_platform`
- `dependency_unavailable`
- `command_timeout`
- `collection_failed`
- `not_found`
- `method_not_allowed`
- `internal_error`

The browser-facing message should be useful without exposing arbitrary command output or local filesystem details.

## `GET /api/v1/health`

Returns service identity and readiness without collecting network data.

### Response `200`

```json
{
  "status": "ok",
  "service": "homeNetTopo",
  "version": "0.1.0",
  "platform": "darwin"
}
```

## `GET /api/v1/capabilities`

Returns platform and optional-tool availability.

### Response `200`

```json
{
  "passive_collection": true,
  "active_discovery": {
    "available": true,
    "tool": "nmap",
    "mode": "host-discovery-only",
    "max_addresses_per_request": 1024
  },
  "bind": "127.0.0.1",
  "external_assets_required": false
}
```

Capability availability is informative. The server must still validate every active request.

## `GET /api/v1/topology`

Collects and returns a passive snapshot. This endpoint must not invoke Nmap.

### Query parameters

- `refresh`: optional boolean. When false or absent, the implementation may return a recent in-memory passive snapshot if documented by response metadata.

### Response `200`

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

The documentation example uses a reserved address and is not an eligible real target.

## `POST /api/v1/discover`

Runs explicit bounded host discovery and returns a newly merged topology snapshot.

### Request

```json
{
  "networks": ["192.168.1.0/24"],
  "timeout_seconds": 30
}
```

### Validation

- Body size is limited.
- `networks` is required and non-empty.
- Each entry must be a private IPv4 network associated with an eligible local interface.
- Disallowed address classes are rejected.
- The combined target size must not exceed the configured request limit.
- `timeout_seconds` must be within a documented bounded range.
- The server invokes only the approved host-discovery mode for this endpoint.

### Response `200`

The response uses the topology snapshot shape from `GET /api/v1/topology`, with:

```json
{
  "mode": "active",
  "active_discovery": {
    "requested_networks": ["192.168.1.0/24"],
    "completed": true,
    "duration_ms": 1200,
    "hosts_reported_up": 4
  }
}
```

### Expected failures

- `400 invalid_json`
- `400 invalid_target`
- `413 target_too_large`
- `415 bad_request` for unsupported content type
- `424 dependency_unavailable` when Nmap is not installed
- `504 command_timeout`
- `500 collection_failed` for a normalized command or parsing failure

## `GET /api/v1/topology/export`

Returns the latest in-memory snapshot as a JSON download. It must not upload or persist the snapshot on the server, and it must not trigger a new collection.

### Response headers

```text
Content-Type: application/json; charset=utf-8
Content-Disposition: attachment; filename="home-network-topology.json"
```

When no snapshot exists, the endpoint returns `404 not_found`. The user must first load or refresh the passive topology endpoint before exporting.

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
      "summary": "Neighbor cache entry"
    }
  ],
  "confidence": "high",
  "observed_at": "2026-08-03T01:00:00Z"
}
```

Node kinds initially include:

- `local_host`
- `interface`
- `subnet`
- `gateway`
- `device`
- `upstream_boundary`

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
      "summary": "Address belongs to subnet"
    }
  ],
  "properties": {}
}
```

Initial edge types include:

- `host_uses_interface`
- `interface_attached_to_subnet`
- `gateway_for_subnet`
- `member_of`
- `routes_to`
- `upstream_of`

## Response headers

The implementation should define restrictive local-app headers, including:

```text
Cache-Control: no-store
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Content-Security-Policy: default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'
```

Exact policy must match the final frontend asset model.

## Compatibility

Breaking JSON changes require a new API or schema version. Renaming existing fields without a version change is not allowed.
