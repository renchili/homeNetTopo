# Home Net Topology

Home Net Topology (`homeNetTopo`) is a local-first macOS application that collects network evidence visible from the current Mac, builds a conservative logical topology, and serves an interactive loopback-only web page.

The current implementation adds a native macOS Wi-Fi identity helper so the product can obtain the **current SSID/BSSID** through CoreWLAN after the user grants Location permission. The Python LaunchAgent no longer depends on `system_profiler` as the only way to identify the connected Wi-Fi radio.

## Status

This revision is source-complete but unverified. The Python/Node tests, Xcode build, Location prompt, CoreWLAN runtime, LaunchAgent lifecycle, browser interaction, and real network behavior have not been executed for this exact revision.

## Requirements

Runtime:

- macOS 13 or newer for the native helper;
- Python 3.10 or newer;
- Python standard library only;
- Apple system frameworks: CoreLocation, CoreWLAN, AppKit/SwiftUI, ServiceManagement;
- optional Nmap for bounded active host discovery.

Installation currently builds the native helper from source and therefore requires Xcode command-line build support. Development frontend verification additionally requires Node.js 20 or newer. No npm packages are used.

## Recommended install

From the repository root:

```text
python3 ./scripts/deploy.py install
```

With an explicit Nmap path:

```text
python3 ./scripts/deploy.py install --nmap-path /opt/homebrew/bin/nmap
```

The installer:

1. builds the fixed `HomeNetTopoApp` Xcode target;
2. ad-hoc signs and verifies `HomeNetTopo Wi-Fi.app`;
3. installs it to `~/Applications/HomeNetTopo Wi-Fi.app`;
4. installs the Python/web runtime under `~/Library/Application Support/HomeNetTopo`;
5. manages the Python service as current-user LaunchAgent `com.homenettopo.local`;
6. waits for the loopback service to become healthy;
7. opens the native Wi-Fi helper in the foreground.

When `HomeNetTopo Wi-Fi` opens, grant **Location** access. The app explains that macOS requires Location permission for current SSID/BSSID access. Once permission is granted, it reads the current Wi-Fi association through CoreWLAN and refreshes it every five seconds.

Then return to:

```text
http://127.0.0.1:8765
```

and use **Refresh passive**.

No manual BSSID is required for the normal path.

If you know the connected wireless node is a relay and want to preserve that role annotation while still using the automatically detected BSSID:

```text
python3 ./scripts/deploy.py install \
  --nmap-path /opt/homebrew/bin/nmap \
  --wifi-interface en0 \
  --wifi-role relay
```

The native/automatic BSSID still wins. Manual `--wifi-bssid` and `--wifi-ssid` options remain last-resort local fallbacks only.

## What identifies the current Wi-Fi device

The application intentionally separates three MAC identities:

```text
This Mac / interface
  Private Wi-Fi MAC   <- ifconfig ether
  Hardware MAC        <- networksetup Ethernet Address

Current Wi-Fi node
  BSSID               <- native CoreWLAN helper (preferred)
                          then system_profiler fallback
```

The BSSID belongs to the currently associated wireless radio. It is not the Mac's Private Wi-Fi MAC and it is not the adapter Hardware MAC.

Evidence precedence is:

```text
wifi_native (CoreWLAN + Location)
  > wifi (system_profiler current association)
  > local_configuration
```

`networksetup -listallhardwareports` remains authoritative for identifying the Wi-Fi BSD interface and its local Hardware MAC.

The native helper publishes a short-lived local cache only:

```text
~/Library/Caches/HomeNetTopo/wifi-current.json
```

The Python service accepts the cache only when it is a current-user-owned regular file, not group/world writable, at most 16 KiB, valid schema version 1, and no more than 20 seconds old. Missing, stale, denied, restricted, or invalid helper data cannot become BSSID evidence.

`GET /api/v1/capabilities` exposes only the helper state and activation URL. It does not expose the current SSID, BSSID, Hardware MAC, Private Wi-Fi MAC, or manual fallback value.

## Expected Wi-Fi topology

With fresh CoreWLAN evidence, the main path is:

```text
This Mac
  → en0
  → current Wi-Fi node (SSID / BSSID)
  → gateway
  → upstream
```

The Wi-Fi node can expose:

- SSID;
- BSSID;
- Channel;
- RSSI;
- Noise;
- PHY mode;
- transmit rate;
- role (`access point or relay`, or a user-confirmed `relay`).

A BSSID proves the current associated radio. It does **not**, by itself, prove that the physical device is a main AP rather than a relay. If you know the role from your actual network, `--wifi-role relay` records that local confirmation without replacing the automatically observed BSSID.

The Details panel separately displays the local interface Hardware MAC and Private Wi-Fi MAC so they cannot be mistaken for the BSSID.

## Passive evidence

The fixed Python command sources are:

```text
/sbin/ifconfig -a
/usr/sbin/netstat -rn -f inet
/usr/sbin/arp -an
/usr/sbin/networksetup -listallhardwareports
/usr/sbin/system_profiler -json -timeout 5 SPAirPortDataType
```

These command collectors run concurrent inside one collection operation. Interface, route, and ARP evidence establish material coherence. `networksetup` identifies Wi-Fi media and local hardware identity. `system_profiler` is optional current-association fallback. The native CoreWLAN cache is read after the command evidence and does not extend command latency.

Profiler failure alone does not invalidate a usable topology. Native helper state is represented as source `wifi_native`; when no automatic BSSID is available, missing/denied/stale native state becomes an actionable warning instead of an invented identity.

## Local identities and peers

All local IPv4 addresses, Private Wi-Fi MAC values, and Hardware MAC values belong to this Mac. If ARP or Nmap reports a local IP or local MAC again, HomeNetTopo excludes it from peer nodes and active host counts.

ARP maps an IP neighbor to a link-layer address. It cannot enumerate transparent switches. Different BSSID and gateway MAC values do not prove that they are different physical boxes because a single appliance may expose multiple interface MACs.

Without LLDP/CDP or managed-topology evidence, a non-Wi-Fi Ethernet path remains:

```text
This Mac → interface → Intermediate L2 path unknown → gateway → upstream
```

Other same-subnet devices are LAN peers, not transit hops.

## Active discovery

Active discovery is optional and separately confirmed. It uses only:

```text
<canonical-nmap-path> -sn -n --max-retries 1 --host-timeout 5s -oX - <validated-targets...>
```

Targets must be canonical RFC 1918 IPv4 networks equal to or contained by eligible non-tunnel local interface networks. Validation occurs before and after fresh passive collection. Adjacent sibling targets remain separate and are never widened into a new supernet.

The product does not perform port, service, OS, vulnerability, credential, packet-capture, public-internet, or reverse-DNS scanning.

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

Collection POSTs require JSON, `X-HomeNetTopo-Request: 1`, an accepted loopback Host, and matching same-origin signals when present. The service emits no permissive CORS headers.

Only one collection runs at a time. Successful snapshots replace the prior snapshot atomically. Failed collections preserve the previous snapshot. Snapshots are in-memory only.

## Deployment locations

```text
~/Library/Application Support/HomeNetTopo
~/Library/LaunchAgents/com.homenettopo.local.plist
~/Library/Logs/HomeNetTopo
~/Library/Caches/HomeNetTopo/wifi-current.json
~/Applications/HomeNetTopo Wi-Fi.app
```

The native helper registers `SMAppService.mainApp` for login launch. macOS may require user approval in Login Items; the helper UI provides a button that opens those settings.

The deployment path never uses `sudo` and never changes the Python service bind from `127.0.0.1`. The Xcode project, target, native source manifest, runtime file manifest, Apple build tools, and installation paths are fixed by `scripts/deploy.py`.

Manage the installation:

```text
python3 ./scripts/deploy.py status
python3 ./scripts/deploy.py restart
python3 ./scripts/deploy.py diagnose
python3 ./scripts/deploy.py uninstall
python3 ./scripts/deploy.py uninstall --purge-logs
```

Uninstall asks the native app to unregister its login item, removes the app and helper cache, and removes the Python LaunchAgent/runtime. Logs are retained unless `--purge-logs` is used.

## Verification

Source/test regression definitions:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend/core.test.mjs
python3 scripts/check.py
```

`python3 scripts/check.py` includes Python source compilation, metadata, Python tests, documentation/contract guards, native source/Xcode/privacy static checks, browser asset checks, Node frontend tests, and repository hygiene. It does not prove that the native app actually builds or receives Location permission.

Native acceptance requires an exact-revision macOS deployment that demonstrates:

- successful Xcode build and ad-hoc signing;
- visible Location authorization for `HomeNetTopo Wi-Fi`;
- current CoreWLAN SSID/BSSID in the helper;
- a fresh `wifi_native` cache;
- the same BSSID in the topology's connected Wi-Fi node;
- browser selection/details behavior.

## Privacy and repository hygiene

No cloud service, account, telemetry, CDN, or external frontend asset is required.

Do not commit real local IPs, SSIDs, BSSIDs, hostnames, MAC addresses, LaunchAgent plists, native cache files, logs, packet captures, Nmap output, exported snapshots, Xcode build products, or DerivedData. Synthetic test values stay inline with their owning tests.
