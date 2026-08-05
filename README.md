# Home Net Topology

Home Net Topology (`homeNetTopo`) is a local-first macOS application that collects network evidence visible from the current Mac, builds a best-effort logical topology, and serves an interactive loopback-only web page.

## Implementation status

The repository contains the Python service, macOS parsers, bounded Nmap adapter, topology model, static browser interface, deterministic test definitions with inline synthetic parser inputs, a per-user macOS deployment script, and a full-regression entrypoint.

**This revision has not been executed or runtime-accepted.** Source presence is not evidence that startup, deployment, tests, browser behavior, Nmap discovery, Wi-Fi association collection, or real-network collection succeeds on a supported Mac.

## Requirements

Production:

- macOS;
- Python 3.10 or newer;
- Python standard library;
- optional Nmap for active host discovery.

Development verification additionally requires Node.js 20 or newer. No npm packages are used.

## Start from the repository

```text
python3 server.py
```

The default URL is:

```text
http://127.0.0.1:8765
```

Optional arguments:

```text
python3 server.py --port 8765
python3 server.py --nmap-path /opt/homebrew/bin/nmap
```

The first release rejects any bind other than `127.0.0.1`.

## Deploy as a macOS user service

`scripts/deploy.py` installs HomeNetTopo as a LaunchAgent for the current macOS user. It never uses `sudo`, never changes the loopback bind, and copies only these versioned runtime files:

```text
server.py
metadata.json
scripts/deploy.py
homenettopo/__init__.py
homenettopo/commands.py
homenettopo/discovery.py
homenettopo/interfaces.py
homenettopo/models.py
homenettopo/neighbors.py
homenettopo/routes.py
homenettopo/topology.py
web/index.html
web/app.js
web/core.mjs
web/styles.css
```

Local caches, tests, documentation, Git metadata, reports, and unlisted files are not installed.

Install or update:

```text
python3 scripts/deploy.py install
```

Use a different loopback port or an explicit Nmap executable:

```text
python3 scripts/deploy.py install --port 8877
python3 scripts/deploy.py install --nmap-path /opt/homebrew/bin/nmap
```

Manage the installed service:

```text
python3 scripts/deploy.py status
python3 scripts/deploy.py restart
python3 scripts/deploy.py uninstall
python3 scripts/deploy.py uninstall --purge-logs
```

The deployment locations are fixed to the current user:

```text
~/Library/Application Support/HomeNetTopo
~/Library/LaunchAgents/com.homenettopo.local.plist
~/Library/Logs/HomeNetTopo
```

Installation validates source files, rejects symbolic links, stages the exact runtime before replacing the active copy, disables environment proxies for the loopback health check, and retains the previous runtime until the new LaunchAgent is healthy. If replacement, activation, or health verification fails, the previous runtime and property list are restored. Uninstall retains logs unless `--purge-logs` is supplied.

## Passive evidence and the gateway path

Initial page load sends a protected passive refresh request. Passive collection uses only fixed commands:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
```

The commands are launched concurrently, so refresh latency is bounded by the slowest source instead of the sum of all source timeouts. `networksetup` quickly identifies which BSD interface is Wi-Fi. `system_profiler` is optional SSID/BSSID enrichment; its timeout or parse failure produces a warning but does not discard the faster Wi-Fi-interface evidence or force a `504` when the material interface, route, or ARP evidence is coherent. Nearby-network scan entries are ignored.

The main graph row describes the path toward the default gateway using explicit evidence:

```text
Wi-Fi with BSSID:
This Mac → interface → associated Wi-Fi AP radio → gateway → upstream

Wi-Fi interface without BSSID details:
This Mac → interface → Wi-Fi access point (identity unavailable) → gateway → upstream

Non-Wi-Fi without adjacent-device evidence:
This Mac → interface → Intermediate L2 path unknown → gateway → upstream

Tunnel default route:
This Mac → tunnel interface → gateway → upstream
```

A BSSID identifies the directly associated Wi-Fi radio. It does not by itself prove whether that radio and the IP gateway are the same physical appliance. Exact matching AP and gateway MAC evidence is recorded as a positive match; different MAC addresses remain `unknown` because one appliance commonly has multiple interface addresses.

ARP identifies the link-layer address used for an IP neighbor, but it does not enumerate transparent switches. Normal IP route and traceroute evidence also does not reveal ordinary Layer-2 forwarding devices. An Ethernet switch is named only when an adjacent-device or managed-topology source such as LLDP is actually available. This first release does not claim LLDP support, so missing evidence is shown explicitly rather than replaced with a fabricated switch.

Other same-subnet devices are rendered in a separate LAN-peers group. They are not drawn as transit hops between this Mac and the gateway.

## Active discovery

Active discovery requires a separate confirmation and uses only:

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <validated-targets...>
```

Nmap finds responding peer hosts. It does not reveal transparent switches, access-point backhaul, or prove the physical path to the gateway. The application does not enable port, service, vulnerability, credential, operating-system, DNS, or internet-wide scanning.

The action area always states its capability:

- `Nmap: checking` while capability data is loading;
- `Nmap: ready` when bounded discovery is available;
- `Nmap: unavailable` with a `Check Nmap setup` action when the optional executable is absent;
- `No eligible LAN` when Nmap exists but no non-tunnel RFC 1918 network is eligible;
- an explicit unsupported-platform state outside macOS.

The button is therefore not an undeveloped placeholder. When Nmap is unavailable, the check action re-reads `/api/v1/capabilities` without starting a scan.

## Active target safety

Validation occurs in two phases:

1. request structure, canonical IPv4 syntax, RFC 1918 membership, body size, count, union size, and operation timeout are checked before commands;
2. after fresh passive collection, every target must equal or be a subnet of an RFC 1918 network assigned to an eligible non-tunnel local interface.

Only `10.0.0.0/8`, `172.16.0.0/12`, and `192.168.0.0/16` are eligible address classes. Supernets, noncanonical partial-overlap requests, adjacent networks, unrelated RFC 1918 ranges, tunnel-only networks, public and special ranges, more than 32 networks, and more than 1024 unique addresses are rejected before Nmap.

Exact duplicates and contained targets may be removed only within the same most-specific containing local network. Adjacent sibling targets remain separate and are never widened into a new supernet.

| Limit | Value |
|---|---:|
| JSON body | 16 KiB |
| Requested networks | 1–32 |
| Unique target addresses | at most 1024 |
| Total Nmap operation timeout | default 30 seconds; range 5–120 |
| Nmap per-host timeout | fixed 5 seconds |
| Interface/route/ARP timeout | 5 seconds each, run concurrently |
| Wi-Fi interface detection timeout | 3 seconds |
| Wi-Fi profiler process timeout | 8 seconds; profiler internal timeout 5 seconds |
| Captured stdout | 2 MiB |
| Captured stderr | 64 KiB |
| Terminate-to-kill grace | 2 seconds |

If all material passive sources fail, the normalized error includes `failed_sources`; a `504 command_timeout` also includes `timeout_sources`. Optional Wi-Fi profiler failure alone never produces a 504.

## Local API

Read-only routes never start collection commands:

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

Both collection routes require JSON, `X-HomeNetTopo-Request: 1`, an accepted loopback Host, matching Origin when present, and `Sec-Fetch-Site: same-origin` or `none` when present. The server emits no permissive CORS headers and does not accept API preflight as an authorization path.

Only one collection can run at a time. A concurrent collection returns `409 collection_in_progress`. Successful snapshots replace the latest snapshot atomically; failures preserve the prior snapshot. Snapshots have no TTL and are not persisted across restarts.

The complete contract is in [`docs/api-spec.md`](docs/api-spec.md).

## Interface

The browser UI provides passive refresh, explicit active discovery, an evidence-backed gateway path, separately grouped LAN peers, tunnel paths, evidence and confidence details, deterministic SVG layout, full-surface pan, bounded pointer-centered zoom, keyboard selection, warnings, recovery states, and local JSON export.

Specific IPv4 routes are represented as inferred `routes_to` relationships from a gateway to a destination boundary. The graph is a logical view, not proof of physical cabling, switching, VLANs, AP backhaul, isolated devices, or networks hidden behind other routers.

The response policy permits repository fonts and `data:` fonts but still blocks external font origins. This avoids false console noise from local browser-extension font injection without enabling network-hosted assets. Browser-extension `runtime.lastError` messages are outside the page runtime.

## Code documentation policy

Comments and docstrings explain contracts that are not obvious from syntax: security boundaries, parser failure rules, state ownership, atomic publication, evidence limits, rollback behavior, and deterministic algorithms. They explain *why* a rule exists rather than repeat assignments or control flow. `python3 scripts/check.py` verifies documentation on these critical owners.

## Privacy and exclusions

Topology data remains in process memory unless the user downloads an export. The application does not require cloud services, accounts, telemetry, CDNs, or externally hosted assets.

The first release excludes reverse-DNS enrichment, online hostname or vendor lookup, user annotations, persistent naming, persistent snapshots, LAN bind, active IPv6, port/service/OS scanning, packet capture, and guaranteed Ethernet-switch discovery. Names already present in approved command output may be retained with evidence.

Do not commit real local IP addresses, SSIDs, BSSIDs, hostnames, MAC addresses, logs, packet captures, scan output, or exported snapshots. Short synthetic parser samples are embedded directly in their owning tests; the project does not require a separate fixture directory.

## Verification commands

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

A Python-only developer mode is available:

```text
python3 scripts/check.py --python-only
```

It reports frontend tests as `NOT RUN` and must not be cited as full-regression or release evidence.

## Evidence status for this revision

- Static source generation: complete.
- Test definitions: present.
- Deployment script: present, not executed.
- Python tests: not run.
- Frontend tests: not run.
- Full regression: not run.
- macOS startup: not run.
- Wi-Fi interface and BSSID collection: not run.
- LaunchAgent deployment: not run.
- Browser interaction: not run.
- Nmap discovery: not run.
- Real-network checks: not run.
- CI: not configured or run.
- Release artifact: not produced.

See [`docs/plan.md`](docs/plan.md) for implementation ownership and [`docs/design.md`](docs/design.md) for architecture and interaction rules.
