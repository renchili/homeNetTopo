# HomeNetTopo Design

## Status

This document defines the intended first implementation. It is not evidence that the application, tests, deployment, Wi-Fi commands, browser interaction, or Nmap path has run successfully.

## Goals

- Collect IPv4, local interface MAC, adapter hardware MAC, route, ARP, Wi-Fi association, and optional radio measurements visible from the Mac.
- Show an evidence-backed path toward the default gateway.
- Keep local identities, serving-radio BSSID, peers, and transit semantics separate.
- Preserve tunnel interfaces as explicit Layer-3 paths.
- Represent unavailable non-Wi-Fi Layer-2 evidence as unknown instead of inventing switches.
- Keep active discovery bounded to validated local RFC 1918 targets.
- Serve a secure, accessible, loopback-only interface and a current-user LaunchAgent.

## Non-goals

The first release does not prove complete physical topology, automatically determine AP versus relay from BSSID alone, enumerate transparent switches without LLDP or managed-network evidence, discover hidden VLANs or backhaul, scan ports/services/OS, bind to LAN, capture packets, persist inventory, or use cloud enrichment.

## Owners

```text
server.py                  loopback HTTP, concurrent collection, fallback merge, snapshot publication
homenettopo/commands.py    fixed command allowlist and bounded subprocesses
homenettopo/interfaces.py  IP/current MAC, hardware MAC, BSSID and radio parsing/merge
homenettopo/routes.py      IPv4 route parser
homenettopo/neighbors.py   ARP parser
homenettopo/discovery.py   Phase A/B and Nmap evidence validation
homenettopo/models.py      public topology schema
homenettopo/topology.py    identity separation, gateway path, peers and confidence
web/core.mjs               reducer, path/peer layout and camera math
web/app.js                 fetch, semantic Details, safe DOM/SVG, input/focus/export
scripts/deploy.py          current-user LaunchAgent lifecycle, local fallback and rollback
scripts/check.py           full regression and cross-owner guards
```

## Approved commands

```text
INTERFACES       /sbin/ifconfig -a
ROUTES           /usr/sbin/netstat -rn -f inet
NEIGHBORS        /usr/sbin/arp -an
WIFI_INTERFACES  /usr/sbin/networksetup -listallhardwareports
WIFI_DETAILS     /usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
DISCOVERY        <canonical-nmap-path> -sn -n --max-retries 1
                 --host-timeout 5s -oX - <validated-targets...>
```

Commands run with `shell=False`, minimal environment, bounded output, total deadlines, and terminate/kill cleanup. Passive sources start concurrently. Interface, route, and ARP use five seconds; Wi-Fi interface detection uses three seconds; profiler uses an eight-second process deadline around its fixed five-second timeout.

## Passive collection and identity merge

1. Validate Host and protected POST headers.
2. Require an empty JSON object and acquire the single collection lock.
3. Launch all fixed passive commands concurrently.
4. Parse material interface/route/ARP evidence independently from optional Wi-Fi enrichment.
5. Merge automatic evidence with an optional local fallback.
6. Construct and atomically publish a complete or coherent partial snapshot.

The identity merge uses these owners:

| Evidence | Meaning |
|---|---|
| `ifconfig inet` | local IPv4 assignment |
| `ifconfig ether` | MAC currently active on the local interface, potentially a private Wi-Fi MAC |
| `networksetup Ethernet Address` | adapter hardware MAC |
| current `system_profiler` BSSID | serving AP/mesh/relay radio |
| ARP | IP-neighbor MAC, excluding all local IPs and local MACs |
| Nmap | responding peer evidence, excluding all local IPs and local MACs |

A detailed profiler result must not erase the adapter hardware MAC. A configured fallback must not override an automatically observed BSSID. Nearby-network scan entries are ignored.

Optional profiler failure becomes a warning and cannot by itself produce `504`. If material evidence is incoherent, `collection_failed` or `command_timeout` includes `failed_sources` and `timeout_sources`.

## Wi-Fi gateway path

When a current BSSID is available:

```text
local_host
  → host_uses_interface
interface
  → interface_associated_with
connected Wi-Fi node
  → attachment_reaches_gateway
gateway
  → upstream_of
upstream_boundary
```

The Wi-Fi node carries available SSID, BSSID, channel, RSSI, noise, PHY mode, transmit rate, role, and evidence source. Its default role is `access point or relay`. BSSID proves the serving radio; it does not prove main AP versus relay or physical identity with the gateway.

When macOS withholds BSSID, the graph retains a connected Wi-Fi node without an invented address. A background LaunchAgent may use a strictly validated local fallback:

```text
--wifi-interface en0
--wifi-bssid 02:aa:bb:cc:dd:55
--wifi-ssid "Synthetic Wi-Fi"
--wifi-role relay
```

The values above are synthetic. Fallback evidence is labelled `local_configuration`, has medium confidence, and is stored only in the current-user LaunchAgent plist. An automatic BSSID collected later has priority.

For a non-Wi-Fi path without adjacent-device evidence:

```text
interface
  → interface_reaches_link
link_boundary "Intermediate L2 path unknown"
  → attachment_reaches_gateway
gateway
```

The boundary can represent direct connection, switch, bridge, or mesh backhaul. It is uncertainty, not a fabricated device. Tunnel routes use direct Layer-3 interface-to-gateway edges.

## Peer semantics

`member_of` and `gateway_for_subnet` express subnet context, not forwarding order. Peer devices appear in a separate group and never enter the host-to-gateway path. A peer whose IP or MAC equals any local identity is rejected during topology construction.

## Active discovery

Phase A validates Host/origin, JSON, 16 KiB body, 1–32 canonical networks, RFC 1918 membership, address union up to 1024, and timeout 5–120 seconds before commands.

Phase B collects fresh interfaces, derives eligible non-tunnel networks, assigns each target to the most-specific local owner, rejects supernets/partial overlaps/unrelated ranges, deduplicates only within an owner, preserves adjacent sibling targets and overlapping owners, and recalculates the union.

Only then may Nmap run. Its XML must have `nmaprun`; hosts must be `up`; IPv4 and optional MAC must be canonical and in an effective target. Invalid evidence is `500 collection_failed`; failures preserve the previous snapshot.

## Browser design

The action area shows Nmap checking, ready, unavailable with recheck, no eligible LAN, or unsupported platform. The graph uses compact fixed columns, orthogonal paths, a viewBox camera, delayed pointer capture, drag-click suppression, pointer-centered zoom, keyboard selection, and a semantic Details panel.

Details present:

```text
IP addresses
Hardware MAC
Private Wi-Fi MAC
BSSID
SSID
Channel
RSSI
Noise
PHY mode
Transmit rate
Role
Evidence
```

The UI does not lead with internal identifiers or parser property names.

## Deployment

`scripts/deploy.py` manages `com.homenettopo.local` in `gui/<uid>`. It never uses `sudo`, always binds `127.0.0.1`, copies the exact 15-file runtime allowlist, rejects symlinks/special files, stages before replacement, retains rollback data until bootstrap and loopback health succeed, disables environment proxies, and retains logs unless purge is requested.

Local Wi-Fi fallback values are ProgramArguments in the current user's plist only. They are not environment variables, service log lines, or repository data.

## Testing and acceptance

Python tests cover command boundaries, all three Wi-Fi MAC roles, radio metrics, merge priority, local identity exclusion, AP/relay path, unknown Ethernet path, tunnel path, active validation, HTTP security, deployment fallback, and snapshot preservation. Node/static web tests cover reducer ownership, path/peer layout, camera behavior, selection, and semantic Details labels.

```text
python3 scripts/check.py
```

Formal acceptance still requires exact-revision execution on supported macOS, real command behavior, browser interaction, LaunchAgent lifecycle, Nmap recovery, one bounded active discovery, and full regression.

Do not commit real IPs, SSIDs, BSSIDs, MACs, hostnames, logs, LaunchAgent plists, captures, scans, or exports.
