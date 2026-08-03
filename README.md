# Home Net Topology

Home Net Topology (`homeNetTopo`) is a local-first macOS application that collects network evidence visible from the current Mac, builds a best-effort logical topology, and serves an interactive loopback-only web page.

## Implementation status

The repository contains the Python service, macOS parsers, bounded Nmap adapter, topology model, static browser interface, deterministic test definitions with inline synthetic parser inputs, and a full-regression entrypoint.

**This revision has not been executed or runtime-accepted.** Source presence is not evidence that startup, tests, browser behavior, Nmap discovery, or real-network collection succeeds on a supported Mac.

## Requirements

Production:

- macOS;
- Python 3.10 or newer;
- Python standard library;
- optional Nmap for active host discovery.

Development verification additionally requires Node.js 20 or newer. No npm packages are used.

## Start the service

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

## Discovery behavior

Initial page load sends a protected passive refresh request. Passive collection executes only:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
```

Active discovery requires a separate confirmation and uses only:

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <validated-targets...>
```

Nmap XML is parsed from stdout. The application does not enable port, service, vulnerability, credential, operating-system, DNS, or internet-wide scanning.

## Active target safety

Validation occurs in two phases:

1. request structure, IPv4 syntax, address classes, body size, count, union size, and operation timeout are checked before commands;
2. after fresh passive collection, every target must equal or be a subnet of a private network assigned to an eligible non-tunnel local interface.

Supernets, noncanonical partial-overlap requests, adjacent networks, unrelated private ranges, tunnel-only networks, public ranges, special ranges, more than 32 networks, and more than 1024 unique addresses are rejected before Nmap.

| Limit | Value |
|---|---:|
| JSON body | 16 KiB |
| Requested networks | 1–32 |
| Unique target addresses | at most 1024 |
| Total Nmap operation timeout | default 30 seconds; range 5–120 |
| Nmap per-host timeout | fixed 5 seconds |
| Passive command timeout | 5 seconds |
| Captured stdout | 2 MiB |
| Captured stderr | 64 KiB |
| Terminate-to-kill grace | 2 seconds |

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

The browser UI provides passive refresh, explicit active discovery, observed and inferred links, evidence and confidence details, deterministic SVG layout, pan and bounded zoom controls, keyboard selection, warnings, recovery states, and local JSON export.

The graph is a logical view, not proof of physical cabling, switching, VLANs, wireless infrastructure, isolated devices, or networks hidden behind other routers.

## Privacy and exclusions

Topology data remains in process memory unless the user downloads an export. The application does not require cloud services, accounts, telemetry, CDNs, or externally hosted assets.

The first release excludes reverse-DNS enrichment, online hostname or vendor lookup, user annotations, persistent naming, persistent snapshots, LAN bind, active IPv6, and port/service/OS scanning. Names already present in approved command output may be retained with evidence.

Do not commit real local IP addresses, hostnames, MAC addresses, logs, packet captures, scan output, or exported snapshots. Short synthetic parser samples are embedded directly in their owning tests; the project does not require a separate fixture directory.

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
- Python tests: not run.
- Frontend tests: not run.
- Full regression: not run.
- macOS startup: not run.
- Browser interaction: not run.
- Nmap discovery: not run.
- Real-network checks: not run.
- CI: not configured or run.
- Release artifact: not produced.

See [`docs/plan.md`](docs/plan.md) for implementation ownership and [`docs/design.md`](docs/design.md) for architecture and interaction rules.
