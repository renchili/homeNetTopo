# HomeNetTopo Project Guidance

## Project identity

`homeNetTopo` is a local-first macOS application that collects evidence visible from the current Mac, constructs a conservative logical topology, and renders it through a loopback-only browser interface.

The product must separate observed facts, deterministic inference, local user configuration, and unknown topology. A single endpoint cannot prove hidden switch ports, VLANs, wireless backhaul, controller relationships, firewall-internal segments, or silent devices.

## First-release scope

The release contains a Python 3.10+ standard-library service, optional bounded Nmap discovery, repository-owned browser assets, in-memory snapshots, JSON export, and a current-user LaunchAgent deployment path.

It excludes cloud services, accounts, telemetry, external assets, normal-path administrator privileges, reverse-DNS or vendor enrichment, persistent inventories, LAN bind, active IPv6, packet capture, port/service/OS/vulnerability scanning, guaranteed switch enumeration, containers, cloud deployment, and system-wide installation.

## Runtime and commands

- macOS collection platform;
- Python 3.10+ standard library;
- Node.js 20+ built-in runner for frontend tests;
- `127.0.0.1` only, default port `8765`;
- optional Nmap;
- current-user deployment: `python3 scripts/deploy.py install`.

Only these typed command families are allowed:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <validated-targets...>
```

Never invoke a shell. Use absolute system paths, concurrent independent passive sources, total process deadlines, bounded output, and terminate/kill cleanup. `networksetup` identifies Wi-Fi BSD interfaces even when profiler details are missing. `system_profiler` is optional current-association enrichment; nearby-network entries are ignored. Optional Wi-Fi failure alone cannot cause `504` and does not make otherwise coherent topology partial.

## Wi-Fi address identity boundary

Three address roles are distinct and must never be conflated:

1. `ifconfig` `ether`: MAC currently active on the local BSD interface; on Wi-Fi it may be a per-network private address.
2. `networksetup` `Ethernet Address`: local adapter hardware MAC.
3. `system_profiler` BSSID: serving Wi-Fi radio, which may be a main AP, mesh node, or relay.

Local IPs, current/private Wi-Fi MACs, and adapter hardware MACs belong only to `This Mac` and its interface. If ARP or Nmap repeats any local IP or local MAC, that evidence must not create a peer device. The serving BSSID belongs only to the connected Wi-Fi node.

When current association evidence supplies a canonical BSSID:

```text
This Mac → Wi-Fi interface → connected Wi-Fi node → gateway → upstream
```

The connected node includes available SSID, BSSID, channel, RSSI, noise, PHY mode, and transmit rate. BSSID proves the serving radio, not whether it is the main AP or a relay. Automatic collection must use role `access point or relay` unless another approved source proves more.

When macOS exposes Wi-Fi media but withholds BSSID, retain a connected Wi-Fi node with no invented identifier. Do not fall back to generic Ethernet `Intermediate L2 path unknown`.

A local LaunchAgent may accept a strictly validated fallback through:

```text
--wifi-interface
--wifi-bssid
--wifi-ssid
--wifi-role access-point|relay
```

Automatic BSSID evidence always overrides the fallback. The fallback is local user configuration, not observed evidence. It is stored only in the current user’s LaunchAgent plist and must not appear in repository files, examples with real values, logs, capability details, or fixtures.

For non-Wi-Fi links without LLDP/CDP or managed-topology evidence:

```text
This Mac → interface → Intermediate L2 path unknown → gateway → upstream
```

ARP and traceroute do not enumerate transparent Layer-2 devices. Tunnels remain visible as Layer-3 paths and never receive fabricated AP or switch nodes. Same-subnet devices are peers, not transit hops.

## Active-target containment

Active targets must equal or be contained by an eligible RFC 1918 IPv4 network assigned to a non-tunnel local interface. Reject supernets, partial overlaps, unrelated private space, public/special/documentation ranges, tunnel-only networks, and requests above fixed limits.

Phase A validates Host/origin protection, JSON, custom header, body size, shape, 1–32 canonical networks, RFC 1918 membership, unique-address union, and timeout before commands.

Phase B runs under the collection lock: collect fresh evidence, require usable interfaces, derive eligible local networks, enforce containment, assign most-specific local owners, deduplicate only within the same owner, keep adjacent sibling targets and overlapping-owner targets separate, and recalculate the union.

Interface timeout is `504 command_timeout`; unavailable or unparseable interface evidence is `500 collection_failed`; no eligible network is `400 invalid_target`. Nmap output must have `nmaprun`, state `up`, valid IPv4, canonical optional MAC, and membership in an effective target. Invalid evidence is `500 collection_failed` and preserves the previous snapshot.

## Browser and snapshot boundary

Accepted Host values are `127.0.0.1:<port>` and `localhost:<port>`. Collection routes require JSON, `X-HomeNetTopo-Request: 1`, matching Origin when present, and `Sec-Fetch-Site: same-origin` or `none`. Do not emit permissive CORS.

Read-only routes:

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

At most one collection runs. Independent commands may run concurrently inside it. Another client receives `409 collection_in_progress`. Successful snapshots publish atomically; failures preserve the previous snapshot. A material `504` identifies `timeout_sources`.

The UI must never leave an unexplained grey discovery placeholder. It displays Nmap checking, ready, unavailable with recheck, no eligible LAN, or unsupported platform. The SVG uses a viewBox camera, compact deterministic layout, full-surface pan after a drag threshold, pointer-centered zoom, orthogonal edges, keyboard selection, and meaningful Details.

Details must use user-facing names: IP addresses, Hardware MAC, Private Wi-Fi MAC, BSSID, SSID, Channel, RSSI, Noise, PHY mode, Transmit rate, and Role. Internal parser keys must not dominate the UI.

## Local deployment boundary

`scripts/deploy.py` is the only deployment owner. It manages `com.homenettopo.local` in `gui/<uid>`, copies exactly the approved 15 runtime files, rejects symlinks and special files, stages before replacement, retains rollback data until bootstrap and loopback health succeed, disables environment proxies, and preserves logs unless `--purge-logs` is supplied.

It must never use `sudo`, bind to `0.0.0.0`, install a system daemon, copy tests/docs/Git data, or emit local Wi-Fi fallback values to service logs.

## Ownership

```text
server.py                         loopback HTTP, concurrent collection, local fallback merge, snapshots
homenettopo/commands.py           typed command allowlist and bounded subprocesses
homenettopo/interfaces.py         IP/current MAC, hardware MAC, BSSID and radio parsing/merge
homenettopo/routes.py             IPv4 route parser
homenettopo/neighbors.py          ARP parser
homenettopo/discovery.py          Phase A/B and Nmap evidence validation
homenettopo/models.py             public topology schema
homenettopo/topology.py           identity separation, path, peers, deterministic evidence merge
web/core.mjs                      reducer, path/peer layout, camera math
web/app.js                        fetch, safe DOM/SVG, semantic Details, interaction
scripts/deploy.py                 current-user LaunchAgent deployment and rollback
scripts/check.py                  full-regression and cross-owner guards
tests/                            inline synthetic tests
docs/ and README.md               contracts and operator instructions
```

## Verification and repository hygiene

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

Full regression requires the exact revision. Keep caches, `.pyc`, virtual environments, node modules, reports, logs, packet captures, runtime exports, LaunchAgent plists, scans, real IPs, SSIDs, BSSIDs, MACs, and hostnames out of source control.

Tests use synthetic data. Documentation-reserved ranges are preferred unless RFC 1918 semantics are under test. Synthetic MACs use locally administered addresses. Short parser inputs remain inline; no independent fixture directory is authorized.
