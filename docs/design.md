# HomeNetTopo Design

## Status

This document defines the intended first implementation. It is not evidence that the application, tests, deployment, Wi-Fi profiler, browser interaction, or Nmap path has run successfully.

## Goals

- Collect IPv4, route, ARP, and current Wi-Fi association evidence visible from the Mac.
- Show an evidence-backed path toward the default gateway.
- Keep same-subnet peers separate from transit-path nodes.
- Preserve tunnel interfaces as explicit Layer-3 paths.
- Represent unavailable intermediate Layer-2 evidence as unknown instead of inventing switches.
- Keep active discovery bounded to validated local RFC 1918 targets.
- Serve a secure, accessible, loopback-only interface.
- Provide deterministic state, layout, tests, and current-user deployment ownership.

## Non-goals

- Proving complete physical topology from one endpoint.
- Discovering every transparent switch, bridge, mesh backhaul, VLAN, controller, or firewall-internal segment.
- Treating ARP peers as transit devices.
- Port, service, vulnerability, credential, OS, public, or internet-wide scanning.
- Reverse DNS, online enrichment, persistent inventory, LAN bind, active IPv6, packet capture, cloud deployment, containers, or system-wide installation.

## Runtime and owners

Production uses macOS, Python 3.10+, the Python standard library, repository-owned browser assets, and optional Nmap. Node.js 20+ is development-only.

```text
server.py                  loopback HTTP, security boundary, source orchestration, lock, snapshots
homenettopo/commands.py    exact command allowlist, Nmap resolution, bounded subprocess runner
homenettopo/interfaces.py  ifconfig and current Wi-Fi association parsers
homenettopo/routes.py      IPv4 route parser
homenettopo/neighbors.py   ARP parser
homenettopo/discovery.py   Phase A/B and Nmap evidence validation
homenettopo/models.py      validated public topology schema
homenettopo/topology.py    evidence merge, gateway path, peer membership, confidence
web/core.mjs               reducer, path/peer layout, address arithmetic, camera math
web/app.js                 fetch, capability status, safe DOM/SVG, input/focus/export
web/index.html             accessible page and explanatory copy
web/styles.css             visual tokens and path/peer/tunnel presentation
scripts/deploy.py          current-user LaunchAgent lifecycle and rollback
scripts/check.py           full regression and cross-owner guards
```

## Approved commands

The browser and HTTP body cannot supply executable names or arguments.

```text
INTERFACES  /sbin/ifconfig -a
ROUTES      /usr/sbin/netstat -rn -f inet
NEIGHBORS   /usr/sbin/arp -an
WIFI        /usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
DISCOVERY   <canonical-nmap-path> -sn -n --max-retries 1
            --host-timeout 5s -oX - <validated-targets...>
```

Commands run with `shell=False`, a minimal environment, bounded output, total deadlines, and terminate/kill cleanup. Interface, route, and ARP commands use five seconds. Wi-Fi profiling uses an eight-second process deadline around the profiler’s fixed five-second timeout.

Nmap resolution order is explicit path, Apple Silicon Homebrew, Intel Homebrew, then `PATH`. The public API exposes only the resolution source.

## Passive collection

1. Validate Host and protected POST headers.
2. Require an empty JSON object.
3. Acquire the single collection lock.
4. Require macOS.
5. Run interface, route, ARP, and Wi-Fi commands independently.
6. Parse each source with explicit failure semantics.
7. Construct a complete or coherent partial snapshot.
8. Publish atomically and release the lock.
9. Re-read capabilities before the browser releases its passive collection owner.

Interface, route, and ARP are the material coherence sources. Wi-Fi association is additional path evidence: its failure creates a warning and partial snapshot but does not erase otherwise coherent topology.

## Determining the path to the gateway

The topology builder uses the default route’s interface and gateway.

### Wi-Fi association evidence

`system_profiler` JSON is searched only for current interface association objects. Nearby-network scan lists are ignored.

When a canonical BSSID is present:

```text
local_host
  → host_uses_interface
interface
  → interface_associated_with       observed
access_point
  → attachment_reaches_gateway      inferred
 gateway
  → upstream_of                     inferred
upstream_boundary
```

The BSSID identifies an associated AP radio. It does not prove the physical identity of the router appliance. Exact AP BSSID and gateway ARP MAC equality is positive `same_mac` evidence. Different MACs remain `unknown` because one device may expose different radio and routed-interface MAC addresses.

When the current association is visible but BSSID is redacted or missing, the graph keeps an `access_point` node labelled as identity unavailable. It never guesses or silently merges it with the gateway.

### Ethernet and unclassified non-tunnel links

ARP resolves an IP neighbor to a link-layer address. It does not enumerate transparent switching infrastructure. An IP route or traceroute-style hop sequence also does not reveal a device that forwards only Layer-2 frames.

A directly adjacent switch can be identified only when an adjacent-device or managed-topology source such as LLDP/CDP is actually available. This first release has no such source. It therefore creates:

```text
interface
  → interface_reaches_link          inferred, low confidence
link_boundary "Intermediate L2 path unknown"
  → attachment_reaches_gateway      inferred, low confidence
gateway
```

The boundary properties state that it may represent a direct link, switch, bridge, or mesh backhaul. It is uncertainty, not an invented device.

### Tunnel paths

A default route through a tunnel uses:

```text
interface → interface_reaches_gateway → gateway → upstream
```

No access point, switch, or Layer-2 broadcast-domain node is inserted.

### LAN peers

`member_of` and `gateway_for_subnet` express address/subnet context. They do not express forwarding order. The browser groups subnets and peer devices below the main path and does not render membership edges as transit lines.

## Active discovery

### Phase A

Before lock acquisition or commands:

- validate Host, content type, custom header, Origin, and Fetch Metadata;
- enforce 16 KiB JSON limit;
- require 1–32 canonical IPv4 networks;
- require RFC 1918 membership;
- reject loopback, link-local, multicast, unspecified, public, documentation, reserved, or tunnel-only targets;
- enforce at most 1024 unique addresses;
- validate total timeout from 5 through 120 seconds.

### Phase B

After fresh passive collection:

- require usable interface evidence;
- derive eligible non-tunnel RFC 1918 networks;
- require every target to equal or be contained by one eligible network;
- assign the target to its most-specific containing local network;
- reject supernets, partial overlaps, adjacent networks outside the owner, unrelated networks, and tunnel-only networks;
- reduce exact duplicates and contained targets only inside the same owner group;
- preserve adjacent sibling targets and distinct overlapping-owner targets;
- recalculate the address union.

Interface timeout is `504 command_timeout`. Missing or unparseable interface evidence is `500 collection_failed`. Successful interface evidence without an eligible network is `400 invalid_target`.

Only after both phases pass may Nmap run. Nmap XML must have an `nmaprun` root. Only `up` hosts are accepted. IPv4 and optional MAC values are validated, and every accepted address must belong to at least one effective target. Malformed or out-of-effective-target evidence is `500 collection_failed`. Failed operations preserve the prior snapshot and do not publish intermediate passive data.

## API, concurrency, and browser security

Accepted Host values are derived from the configured port and limited to `127.0.0.1` and `localhost`. Collection POSTs require JSON and `X-HomeNetTopo-Request: 1`; optional Origin and Fetch Metadata must be same-origin. No permissive CORS is emitted.

Read-only routes never collect:

```text
GET /api/v1/health
GET /api/v1/capabilities
GET /api/v1/topology
GET /api/v1/topology/export
```

Collection routes are:

```text
POST /api/v1/topology/refresh
POST /api/v1/discover
```

One collection runs at a time. Another client gets `409 collection_in_progress`. The browser uses one `collectionInFlight` owner and ignores stale completions.

## Browser information architecture

```text
header
  product and snapshot metadata
  passive refresh
  active discovery action plus visible Nmap capability state
  export
status
  progress, errors, source warnings, recovery instructions
workspace
  gateway path and LAN peers graph
  details panel
dialog
  eligible targets, address total, timeout, confirmation
```

The Nmap action is never an unexplained grey placeholder:

- checking: disabled with `Nmap: checking`;
- ready: enabled `Discover devices`;
- missing: enabled `Check Nmap setup` plus `Nmap: unavailable`;
- no eligible target: disabled `No eligible LAN`;
- unsupported platform: explicit disabled explanation.

Checking Nmap only re-reads capabilities; it does not start discovery.

## Deterministic graph layout

Top-left world coordinates use fixed path columns:

```text
local host       x = 0
interface        x = 240
AP/unknown link  x = 500
gateway          x = 760
upstream         x = 1040
```

Each interface owns a vertical lane. The path row is above an optional subnet/peer context group. Peers use up to three columns, or four for more than 30 devices. Membership edges are omitted from rendered path edges.

The layout output contains:

- positioned path and peer nodes;
- subnet/peer group rectangles;
- only path edges;
- hidden relationship count;
- complete world bounds.

Rendered path edge types are:

```text
host_uses_interface
interface_associated_with
interface_reaches_link
attachment_reaches_gateway
interface_reaches_gateway
upstream_of
routes_to
```

Edges use orthogonal SVG paths. A viewBox camera fits each new snapshot, pans from nodes/edges/groups/blank space, suppresses click after drag, and zooms around the pointer. Layout and camera math are pure and deterministic.

## Topology schema additions

Node kinds include:

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

Path edge types add:

```text
interface_associated_with
interface_reaches_link
attachment_reaches_gateway
interface_reaches_gateway
```

Sources add `wifi` and `link_path_inference`. Every inferred path edge remains visibly inferred with confidence and evidence. The schema does not claim physical wiring.

## Current-user deployment

`scripts/deploy.py` manages one current-user LaunchAgent and never uses `sudo`. It copies only the explicit 15 runtime files, rejects symlinks, stages before replacement, keeps rollback data until loopback health succeeds, disables proxy use for health checks, and retains logs unless purge is requested.

## Testing design

Python tests cover command allowlists, Wi-Fi parser redaction/current-network filtering, route and ARP parsers, active validation, path node/edge schema, Wi-Fi AP path, unknown Ethernet path, tunnel path, AP/gateway MAC relation, source degradation, HTTP security, deployment, and snapshot preservation.

Node tests cover reducer ownership, capability recovery, evidence graph preservation, path order, peer grouping, hidden membership edges, tunnel paths, layout determinism, rectangle overlap, camera fit/zoom, address arithmetic, selection, and export naming.

Full regression:

```text
python3 scripts/check.py
```

It includes compile, metadata, Python tests, documentation guards, contract guards, browser asset/CSP checks, Node tests, deployment guards, and tracked-path hygiene.

## Privacy and acceptance

Snapshots remain in memory unless exported. Do not commit real SSIDs, BSSIDs, IPs, MACs, hostnames, logs, captures, or scan results.

Formal acceptance still requires exact-revision execution on supported macOS, including real `system_profiler` output and redaction behavior, browser interaction, LaunchAgent lifecycle, Nmap unavailable/recovery, one bounded active discovery, and regression execution.
