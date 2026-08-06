# Home Net Topology

Home Net Topology (`homeNetTopo`) is a local-first macOS application that collects network evidence visible from the current Mac, builds a best-effort logical topology, and serves an interactive loopback-only web page.

## Implementation status

The repository contains the Python service, macOS parsers, bounded Nmap adapter, topology model, static browser interface, deterministic tests with inline synthetic inputs, a per-user macOS deployment script, and a full-regression entrypoint.

**This revision has not been executed or runtime-accepted.** Source presence is not evidence that startup, deployment, tests, browser behavior, Nmap discovery, Wi-Fi association collection, or real-network collection succeeds on a supported Mac.

## Requirements

Production requires macOS and Python 3.10 or newer. Nmap is optional and is used only for bounded active host discovery. Development verification additionally requires Node.js 20 or newer. No npm packages or third-party Python packages are used.

## Start from the repository

```text
python3 server.py
python3 server.py --port 8765
python3 server.py --nmap-path /opt/homebrew/bin/nmap
```

The default URL is `http://127.0.0.1:8765`. The first release rejects any bind other than `127.0.0.1`.

## Deploy as a macOS user service

`scripts/deploy.py` installs HomeNetTopo as a LaunchAgent for the current macOS user. It never uses `sudo`, never changes the loopback bind, and copies only the explicit runtime allowlist. Tests, documentation, Git metadata, caches, reports, and unlisted files are not installed.

```text
python3 scripts/deploy.py install
python3 scripts/deploy.py install --port 8877
python3 scripts/deploy.py install --nmap-path /opt/homebrew/bin/nmap
python3 scripts/deploy.py status
python3 scripts/deploy.py restart
python3 scripts/deploy.py diagnose
python3 scripts/deploy.py uninstall
python3 scripts/deploy.py uninstall --purge-logs
```

The deployment locations are fixed to the current user:

```text
~/Library/Application Support/HomeNetTopo
~/Library/LaunchAgents/com.homenettopo.local.plist
~/Library/Logs/HomeNetTopo
```

Installation validates regular files, rejects symbolic links, stages the exact runtime, disables environment proxies for the loopback health check, and retains the previous runtime until the new LaunchAgent is healthy. A failed replacement, bootstrap, or health check restores the prior runtime and property list.

### Optional local Wi-Fi relay fallback

macOS can show the current BSSID in the interactive Wi-Fi menu while withholding it from a background LaunchAgent. Automatic `system_profiler` evidence always has priority. When automatic BSSID evidence is absent, installation can provide a local fallback:

```text
python3 scripts/deploy.py install \
  --nmap-path /opt/homebrew/bin/nmap \
  --wifi-interface en0 \
  --wifi-bssid 02:aa:bb:cc:dd:55 \
  --wifi-ssid "Synthetic Wi-Fi" \
  --wifi-role relay
```

The example is synthetic. These values are validated and written only to the current user's LaunchAgent plist. They are not added to the repository, source logs, examples, or fixtures. `--wifi-role relay` is user-confirmed local configuration; automatic collection does not guess AP versus relay.

## Passive evidence and Wi-Fi identity

Initial page load sends a protected passive refresh. The fixed commands run concurrently:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
```

`networksetup` identifies Wi-Fi BSD interfaces and adapter hardware MAC addresses. `ifconfig` provides the MAC currently active on the interface; with Private Wi-Fi Address enabled, that current MAC can differ from the hardware MAC. `system_profiler` optionally provides the current SSID, serving-radio BSSID, channel, RSSI, noise, PHY mode, and transmit rate. Nearby-network entries are ignored.

The three MAC roles are kept separate:

```text
This Mac / en0
  IP address
  Hardware MAC             local adapter identity
  Private Wi-Fi MAC        current per-network local identity, when different

Connected Wi-Fi node
  BSSID                    serving AP, mesh node, or relay radio
```

A local IP, adapter hardware MAC, or private Wi-Fi MAC can never become a peer device. ARP or Nmap evidence that repeats a local IP or local MAC is discarded from peer creation. A BSSID belongs to the connected wireless node, not to the Mac.

The main path is evidence-backed:

```text
Wi-Fi with BSSID:
This Mac → interface → connected Wi-Fi node → gateway → upstream

Wi-Fi media without BSSID:
This Mac → interface → connected Wi-Fi node (AP or relay) → gateway → upstream

Non-Wi-Fi without adjacent-device evidence:
This Mac → interface → Intermediate L2 path unknown → gateway → upstream

Tunnel default route:
This Mac → tunnel interface → gateway → upstream
```

A BSSID proves which radio serves the client, but does not by itself prove whether it is the main AP, a mesh node, or a relay. A configured role is shown as local user evidence. Exact matching serving-radio and gateway MAC evidence is recorded as a positive relation; different MACs do not prove different physical appliances.

ARP identifies the link-layer address used for an IP neighbor, but does not enumerate transparent switches. Traceroute likewise does not reveal ordinary Layer-2 forwarding devices. An Ethernet switch is named only when adjacent-device or managed-topology evidence such as LLDP is available. The first release does not claim LLDP support.

Other same-subnet devices are rendered in a separate peer group and are never transit hops between this Mac and the gateway.

## Active discovery

After explicit confirmation, active discovery uses only:

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <validated-targets...>
```

Nmap finds responding peers. It does not reveal transparent switches, Wi-Fi backhaul, or prove the physical gateway path. Port, service, vulnerability, credential, operating-system, DNS, and internet-wide scanning are excluded.

Validation occurs in two phases:

1. request structure, canonical IPv4 syntax, RFC 1918 membership, body size, count, address union, and timeout are checked before commands;
2. after fresh passive collection, every target must equal or be contained by an eligible non-tunnel RFC 1918 network assigned to a local interface.

Only `10.0.0.0/8`, `172.16.0.0/12`, and `192.168.0.0/16` are eligible. Exact duplicates and contained targets may be removed only within the same most-specific local owner. Adjacent sibling targets remain separate and are never widened into a new supernet.

| Limit | Value |
|---|---:|
| JSON body | 16 KiB |
| Requested networks | 1–32 |
| Unique target addresses | at most 1024 |
| Nmap operation timeout | default 30 seconds; range 5–120 |
| Nmap host timeout | fixed 5 seconds |
| Interface/route/ARP timeout | 5 seconds each, concurrent |
| Wi-Fi interface detection | 3 seconds |
| Wi-Fi profiler process | 8 seconds; internal timeout 5 seconds |
| Captured stdout | 2 MiB |
| Captured stderr | 64 KiB |
| Terminate-to-kill grace | 2 seconds |

If all material passive sources fail, the normalized `collection_failed` error includes `failed_sources`; a `504 command_timeout` also includes `timeout_sources`. Optional Wi-Fi profiler failure alone never produces a 504.

## Local API

Read-only routes never start commands:

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

Collection routes require JSON, `X-HomeNetTopo-Request: 1`, an accepted loopback Host, matching Origin when present, and `Sec-Fetch-Site: same-origin` or `none` when present. There are no permissive CORS headers. One collection runs at a time; concurrent collection returns `409 collection_in_progress`. Successful snapshots replace the previous snapshot atomically, and failures preserve it.

The complete contract is in `docs/api-spec.md`.

## Interface

The browser provides passive refresh, explicit active discovery, an evidence-backed gateway path, separate peer groups, tunnel paths, selectable details, deterministic SVG layout, full-surface pan, bounded pointer-centered zoom, keyboard selection, warnings, recovery states, and local JSON export.

Selecting the Mac or interface shows local IPs, hardware MAC, and private Wi-Fi MAC. Selecting the connected Wi-Fi node shows role, SSID, BSSID, channel, RSSI, noise, PHY mode, and transmit rate when available. Internal parser field names are not used as primary UI labels.

## Privacy and exclusions

Topology data stays in process memory unless the user downloads an export. The application requires no cloud service, account, telemetry, CDN, or external asset.

The first release excludes reverse-DNS enrichment, online vendor lookup, persistent naming, persistent snapshots, LAN bind, active IPv6, port/service/OS scanning, packet capture, guaranteed switch discovery, and automatic proof that a Wi-Fi node is a relay.

Do not commit real local IP addresses, SSIDs, BSSIDs, hostnames, MAC addresses, logs, packet captures, scan output, LaunchAgent property lists, or exported snapshots. Tests use inline synthetic data; no independent fixture directory is required.

## Verification commands

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

`python3 scripts/check.py --python-only` is development feedback only and must not be cited as full-regression evidence.

## Evidence status for this revision

- Static source generation: complete.
- Test definitions: present.
- Deployment script: present, not executed.
- Python tests: not run.
- Frontend tests: not run.
- Full regression: not run.
- macOS startup and Wi-Fi collection: not run.
- LaunchAgent deployment: not run.
- Browser interaction: not run.
- Nmap discovery: not run.
- CI: not configured or run.
