# HomeNetTopo Project Guidance

## Project identity

`homeNetTopo` is a local-first macOS application that collects network evidence visible from the current Mac, constructs a conservative logical topology, and renders it through a loopback-only browser interface.

The product must separate facts, deterministic inference, and unknown topology. A single endpoint cannot prove hidden switch ports, VLANs, wireless backhaul, controller relationships, firewall-internal segments, or silent devices.

## First-release scope

The release contains:

1. a Python 3.10+ standard-library service for macOS evidence collection;
2. optional bounded Nmap host discovery;
3. a local HTML/CSS/JavaScript/SVG interface;
4. in-memory snapshots and JSON export;
5. a current-user LaunchAgent deployment path.

It excludes cloud services, accounts, telemetry, external assets, administrator privileges in the normal path, reverse-DNS or vendor enrichment, annotations, persistent inventories, LAN bind, active IPv6, packet capture, port/service/OS/vulnerability scanning, guaranteed Ethernet-switch enumeration, containers, cloud deployment, and system-wide installation.

## Runtime and dependencies

- Supported collection platform: macOS.
- Minimum Python: 3.10.
- Production Python dependencies: standard library only.
- Browser assets: repository-owned; no CDN.
- Optional active executable: Nmap.
- Frontend tests: Node.js 20+ built-in test runner; no npm packages.
- Bind: `127.0.0.1` only.
- Default port: `8765`.
- User deployment: `python3 scripts/deploy.py install`.

## Approved command boundary

HTTP and browser callers never provide executable names or arbitrary arguments. Only these typed command families are allowed:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <validated-targets...>
```

Requirements:

- never invoke a shell;
- use absolute macOS system-tool paths;
- launch independent passive sources concurrently so refresh duration is bounded by the slowest source rather than cumulative deadlines;
- apply a 5-second process deadline to interface, route, and ARP commands;
- apply a 3-second deadline to Wi-Fi hardware-port detection;
- apply an 8-second process deadline to Wi-Fi profiling, which also has the fixed 5-second profiler timeout;
- use `networksetup` to identify Wi-Fi BSD interfaces even when profiler details are unavailable;
- retain only current Wi-Fi association data, not nearby-network scan entries;
- treat `system_profiler` as optional enrichment: timeout or parse failure may mark a snapshot partial but cannot by itself cause `504`;
- resolve Nmap in this order: explicit option, `/opt/homebrew/bin/nmap`, `/usr/local/bin/nmap`, then `shutil.which("nmap")`;
- canonicalize Nmap and require an executable regular file;
- expose only the Nmap resolution source, never its path;
- use total process deadlines, bounded stdout/stderr, and terminate/kill cleanup;
- normalize failures before returning them to the browser.

Fixed limits:

| Limit | Value |
|---|---:|
| Maximum JSON body | 16 KiB |
| Maximum requested networks | 32 |
| Maximum unique target addresses | 1024 |
| Active-operation timeout default | 30 seconds |
| Active-operation timeout range | 5–120 seconds |
| Nmap per-host timeout | 5 seconds |
| Interface/route/ARP timeout | 5 seconds each, concurrent |
| Wi-Fi interface detection timeout | 3 seconds |
| Wi-Fi profiler process timeout | 8 seconds |
| Captured stdout | 2 MiB |
| Captured stderr | 64 KiB |
| Timed-out process kill grace | 2 seconds |

## Evidence-backed host-to-gateway path

The main graph must answer “what does this Mac use to reach the gateway?” without turning unrelated peers into transit devices.

### Wi-Fi

When current association evidence supplies a canonical BSSID:

```text
This Mac → Wi-Fi interface → associated AP radio → gateway → upstream
```

The BSSID identifies the associated radio, not necessarily the complete appliance. A matching AP BSSID and gateway ARP MAC may be recorded as `same_mac`. Different MAC addresses remain `unknown`; they do not prove separate boxes because one appliance may use multiple interface MACs.

When macOS exposes the association but redacts or omits BSSID, retain an `access_point` node whose identity is unavailable. Never guess the BSSID or collapse it into the gateway.

When only `networksetup` identifies the default-route interface as Wi-Fi, infer a Wi-Fi access-point boundary with unavailable identity. Mark the interface-to-AP edge inferred and cite the Wi-Fi-interface plus default-route evidence. Do not fall back to the generic Ethernet `Intermediate L2 path unknown` node.

### Ethernet and other non-tunnel links

ARP maps an IP neighbor to a link-layer address; it does not enumerate transparent switches. Ordinary IPv4 routes and traceroute-style hop evidence do not expose devices that forward only at Layer 2.

An adjacent switch may be named only from actual LLDP/CDP or managed-topology evidence. This release does not claim such a source. Without it, render:

```text
This Mac → interface → Intermediate L2 path unknown → gateway → upstream
```

The unknown boundary may represent a direct link, switch, bridge, or mesh backhaul. It is low-confidence path uncertainty, not a fabricated device.

### Tunnels

Tunnel interfaces remain visible as Layer-3 paths and never receive a fabricated access point, switch, or Layer-2 broadcast-domain node.

### LAN peers

ARP and validated Nmap devices that share a subnet are peers. They belong in a separate subnet/LAN group. They must not appear on the host-to-gateway transit row, and membership edges must not become transit lines.

## Active-target containment

An active target is eligible only when it equals or is a subnet of an eligible RFC 1918 IPv4 network assigned to a non-tunnel local interface.

Reject targets that are supernets, partial overlaps, adjacent but outside, unrelated RFC 1918 space, non-RFC1918, loopback, link-local, multicast, unspecified, public, documentation-only, tunnel-only, or above fixed limits.

### Phase A

Before lock acquisition and commands, validate Host/origin protection, JSON media type and custom header, body size, object shape, 1–32 canonical networks, RFC 1918 membership, unique-address union, and operation timeout.

### Phase B

Under the collection lock:

1. collect fresh passive evidence;
2. require usable interface evidence;
3. derive eligible non-tunnel local networks;
4. require containment;
5. assign every target to its most-specific containing local network;
6. remove exact duplicates and contained targets only inside the same owner group;
7. keep adjacent sibling targets and distinct overlapping-owner targets separate;
8. recalculate the final union.

Interface timeout is `504 command_timeout`; unavailable or unparseable interface evidence is `500 collection_failed`; successful interface evidence with no eligible local network is `400 invalid_target`.

Nmap may be resolved and invoked only after both phases pass. Parsed Nmap evidence must have an `nmaprun` root, host state `up`, valid IPv4, canonical optional MAC, and membership in at least one effective target. Malformed or out-of-effective-target evidence is `500 collection_failed` and preserves the previous snapshot.

## Browser request boundary

Every request requires a Host matching the configured port:

```text
127.0.0.1:<port>
localhost:<port>
```

Collection routes:

```text
POST /api/v1/topology/refresh
POST /api/v1/discover
```

They require:

```text
Content-Type: application/json
X-HomeNetTopo-Request: 1
```

When present, Origin must exactly match an accepted loopback origin and `Sec-Fetch-Site` must be `same-origin` or `none`. Do not emit permissive CORS. API OPTIONS is not authorization. Read-only GET routes never start commands.

The CSP may allow repository fonts and `data:` fonts but must not allow external font origins. Extension-injected runtime messages are outside application ownership.

## Snapshot and concurrency lifecycle

Read-only routes:

```text
GET /api/v1/health
GET /api/v1/capabilities
GET /api/v1/topology
GET /api/v1/topology/export
```

Rules:

- at most one passive or active collection runs at a time;
- independent fixed passive commands may run concurrently inside that one collection;
- the browser uses one shared collection-in-flight owner;
- another client receives `409 collection_in_progress` immediately;
- successful passive, coherent partial, and successful active results replace the snapshot atomically;
- failures preserve the prior snapshot;
- intermediate passive data from a failed active operation is not published;
- snapshots are in-memory and have no TTL.

Wi-Fi profiling is best-effort. Failure produces a warning and partial snapshot when interface, route, or ARP evidence remains coherent. Fast Wi-Fi interface evidence remains available. A `504 command_timeout` requires all material passive evidence to be incoherent and must identify `timeout_sources`; optional Wi-Fi-detail timeout alone is never sufficient.

## Capability and UI behavior

A runtime Nmap failure changes active capability to unavailable while passive use remains. Passive refresh rechecks capabilities before releasing its collection owner.

The action area must display one of:

- `Nmap: checking`;
- `Nmap: ready` and `Discover devices`;
- `Nmap: unavailable` and an enabled `Check Nmap setup` recheck action;
- `No eligible LAN`;
- explicit unsupported-platform state.

Do not leave an unexplained grey placeholder button.

The graph uses an SVG viewBox camera, automatically fits a new snapshot, pans from nodes/edges/groups/blank space, suppresses click after drag, zooms around the pointer, and renders path edges orthogonally.

Main path order:

```text
local host → interface → access point or unknown link → gateway → upstream
```

Subnet and peer groups appear below the path. Tunnel paths remain visible. Keyboard operation, focus return, reduced motion, 200% zoom, selection, details, and export remain required.

## Local deployment boundary

`scripts/deploy.py` is the only deployment owner. It installs into the current user’s Library and manages `com.homenettopo.local` in `gui/<uid>`.

It must:

- never use `sudo`;
- always pass `--bind 127.0.0.1`;
- copy only the exact 15-file `RUNTIME_FILES` allowlist;
- reject source or staged symlinks and special files;
- stage before atomic replacement;
- keep rollback data until LaunchAgent bootstrap and loopback health succeed;
- disable environment proxies for health checks;
- install under `~/Library/Application Support/HomeNetTopo`;
- write `~/Library/LaunchAgents/com.homenettopo.local.plist`;
- write logs under `~/Library/Logs/HomeNetTopo`;
- retain logs unless uninstall receives `--purge-logs`.

## Current ownership

```text
server.py                         HTTP boundary, concurrent source orchestration, lock, snapshots, static delivery
homenettopo/commands.py           typed command allowlist and bounded subprocess execution
homenettopo/interfaces.py         ifconfig, Wi-Fi hardware-port, and association parsers/merge
homenettopo/routes.py             IPv4 route parser
homenettopo/neighbors.py          ARP parser
homenettopo/discovery.py          Phase A/B and Nmap evidence validation
homenettopo/models.py             validated public topology schema
homenettopo/topology.py           gateway path, peer membership, evidence merge, deterministic order
web/core.mjs                      reducer, path/peer layout, address arithmetic, camera math
web/app.js                        fetch, capability status, safe DOM/SVG, pointer/keyboard/focus/export
web/index.html                    accessible page structure and explanatory copy
web/styles.css                    visual tokens, path/peer/tunnel states, focus/reduced motion
scripts/deploy.py                 current-user LaunchAgent deployment and rollback
scripts/check.py                  complete regression entrypoint and static contract guards
tests/                            inline synthetic Python tests
tests/frontend/core.test.mjs      pure frontend Node tests
docs/                             design, API, ownership, decisions
README.md                         operator setup and evidence limits
metadata.json                     compact product contract
```

## Code documentation boundary

Comments and docstrings explain security, parser failure, evidence limits, two-phase ownership, Nmap validation, atomic publication, path uncertainty, reducer ownership, focus recovery, camera/layout behavior, deployment rollback, and user-level installation limits. They must not merely restate syntax.

## Verification ownership

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

Full regression requires Node 20+ and includes compile, metadata, Python tests, documentation guards, cross-owner contracts, assets/CSP, frontend tests, deployment guards, and tracked-path hygiene. Executed success may be claimed only for the exact tested revision.

## Repository hygiene

Keep caches, `.pyc`, virtual environments, node modules, coverage, reports, logs, packet captures, runtime exports, scan data, SSIDs, BSSIDs, real IPs, real MACs, and hostnames out of source control.

Test data must be synthetic. Tests unrelated to private-address semantics prefer documentation-reserved ranges. RFC 1918 containment and active-discovery tests may use clearly synthetic RFC 1918 values. Synthetic MAC addresses use locally administered values. Short inputs stay inline.
