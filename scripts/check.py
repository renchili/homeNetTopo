#!/usr/bin/env python3
"""Run repository-relative source, contract, test, asset, and hygiene checks.

A stage reports PASS only after it executes successfully. Native Xcode build,
Location authorization, and CoreWLAN runtime remain exact-revision macOS
acceptance checks; this script statically guards their source and build contract.
"""

from __future__ import annotations

import argparse
import ast
import json
import plistlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED_PARTS = {"__pycache__", ".pytest_cache", "node_modules", ".venv", "coverage", "htmlcov", "test-results", "reports", "DerivedData"}
PROHIBITED_SUFFIXES = {".pyc", ".pcap", ".pcapng", ".log", ".sqlite", ".db"}
NATIVE_PATHS = (
    "macos/HomeNetTopoApp/HomeNetTopoApp.swift",
    "macos/HomeNetTopoApp/AppDelegate.swift",
    "macos/HomeNetTopoApp/WiFiCollector.swift",
    "macos/HomeNetTopoApp/Info.plist",
    "macos/HomeNetTopoApp/HomeNetTopoApp.xcodeproj/project.pbxproj",
)


@dataclass
class StageResult:
    """One executed regression stage and its truthful result."""

    name: str
    status: str
    detail: str = ""


def run_process(argv: list[str]) -> None:
    """Run one repository command and normalize nonzero exits."""

    completed = subprocess.run(argv, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(argv)}")


def load_metadata() -> dict:
    """Load compact product metadata and require stable owner sections."""

    metadata = json.loads((ROOT / "metadata.json").read_text(encoding="utf-8"))
    required = {
        "name", "status", "runtime", "collection_api", "passive_evidence",
        "active_discovery", "snapshot_policy", "gateway_path", "graph_layout",
        "command_limits", "http_limits", "network_scope", "local_bind", "default_port",
        "native_wifi_helper",
    }
    missing = required - metadata.keys()
    if missing:
        raise RuntimeError(f"metadata missing keys: {sorted(missing)}")
    return metadata


def parse_metadata() -> None:
    """Regression stage wrapper for metadata loading."""

    load_metadata()


def _qualified_docstrings(path: Path) -> dict[str, str | None]:
    """Collect module, top-level, and class-method docstrings."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: dict[str, str | None] = {"<module>": ast.get_docstring(tree)}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = ast.get_docstring(node)
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[f"{node.name}.{child.name}"] = ast.get_docstring(child)
    return result


def documentation_guards() -> None:
    """Require docs at security, evidence, native, state, and deployment boundaries."""

    required: dict[str, tuple[str, ...]] = {
        "server.py": (
            "<module>", "ApiError", "PassiveParts", "NativeWiFiCacheState", "read_native_wifi_cache",
            "AppState", "AppState.native_wifi_state", "AppState.collect_passive_parts",
            "AppState.passive_refresh", "AppState.active_discover", "HomeNetTopoServer",
            "HomeNetTopoHandler", "HomeNetTopoHandler._validate_collection_headers",
            "HomeNetTopoHandler._serve_static", "parse_args", "main",
        ),
        "homenettopo/interfaces.py": (
            "<module>", "InterfaceAddress", "InterfaceFact", "WirelessAttachmentFact", "NativeWiFiEvidence",
            "parse_ifconfig", "parse_wifi_hardware_ports", "parse_native_wifi_json",
            "merge_wireless_facts", "parse_airport_json",
        ),
        "homenettopo/topology.py": ("<module>", "build_snapshot"),
        "scripts/deploy.py": (
            "<module>", "DeploymentError", "validate_source_root", "validate_native_source_root",
            "build_launch_agent", "stage_runtime", "build_native_app", "replace_native_app",
            "open_native_helper", "install", "restart", "status", "uninstall", "parse_args", "main",
        ),
        "scripts/check.py": ("<module>", "StageResult", "documentation_guards", "native_source_guards", "consistency_guards", "main"),
    }
    for relative, symbols in required.items():
        docs = _qualified_docstrings(ROOT / relative)
        missing = [symbol for symbol in symbols if not docs.get(symbol)]
        if missing:
            raise RuntimeError(f"required code documentation missing from {relative}: {missing}")

    comments = {
        "web/core.mjs": ("Pure frontend state", "evidence-backed layout", "camera"),
        "web/app.js": ("Browser adapter for HomeNetTopo", "safe DOM/SVG", "viewBox camera"),
    }
    for relative, markers in comments.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in source]
        if missing:
            raise RuntimeError(f"required code comments missing from {relative}: {missing}")


def native_source_guards() -> None:
    """Statically guard the CoreLocation/CoreWLAN app and fixed Xcode boundary."""

    missing = [path for path in NATIVE_PATHS if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(f"native helper paths missing: {missing}")

    app = (ROOT / NATIVE_PATHS[0]).read_text(encoding="utf-8")
    delegate = (ROOT / NATIVE_PATHS[1]).read_text(encoding="utf-8")
    collector = (ROOT / NATIVE_PATHS[2]).read_text(encoding="utf-8")
    project = (ROOT / NATIVE_PATHS[4]).read_text(encoding="utf-8")
    with (ROOT / NATIVE_PATHS[3]).open("rb") as handle:
        plist = plistlib.load(handle)

    for marker in (
        "import Combine", "CWWiFiClient.shared()", "requestWhenInUseAuthorization()",
        "interface.ssid()", "interface.bssid()", "interface.wlanChannel()", "interface.rssiValue()",
        "interface.noiseMeasurement()", "interface.transmitRate()", '"wifi-current.json"',
        "schemaVersion: 1", "cacheInterval: TimeInterval = 5",
    ):
        if marker not in collector:
            raise RuntimeError(f"native CoreWLAN collector contract missing: {marker}")
    for marker in ("import Combine", "SMAppService.mainApp", ".register()", ".unregister()", "openSystemSettingsLoginItems"):
        if marker not in delegate:
            raise RuntimeError(f"native login-item contract missing: {marker}")
    for marker in ("Request Location Access", "Refresh Wi-Fi", "BSSID", "RSSI"):
        if marker not in app:
            raise RuntimeError(f"native authorization UI contract missing: {marker}")
    for key in ("NSLocationUsageDescription", "NSLocationWhenInUseUsageDescription"):
        if not plist.get(key):
            raise RuntimeError(f"native privacy key missing: {key}")
    if plist.get("CFBundleURLTypes") is None:
        raise RuntimeError("native helper URL scheme is missing")
    for marker in (
        "PRODUCT_BUNDLE_IDENTIFIER = com.homenettopo.wifi", "CoreWLAN.framework",
        "CoreLocation.framework", "ServiceManagement.framework", "MACOSX_DEPLOYMENT_TARGET = 13.0",
    ):
        if marker not in project:
            raise RuntimeError(f"native Xcode project contract missing: {marker}")
    if "CODE_SIGN_ENTITLEMENTS" in project:
        raise RuntimeError("native helper unexpectedly introduced an entitlements contract")


def consistency_guards() -> None:
    """Check cross-owner Wi-Fi identity, path, UI, and deployment contracts."""

    required_paths = (
        "server.py", "metadata.json", "AGENT.md", "README.md", "homenettopo/commands.py",
        "homenettopo/discovery.py", "homenettopo/interfaces.py", "homenettopo/models.py",
        "homenettopo/neighbors.py", "homenettopo/routes.py", "homenettopo/topology.py",
        "scripts/deploy.py", "web/index.html", "web/core.mjs", "web/app.js", "web/styles.css",
        "docs/api-spec.md", "docs/design.md", "docs/plan.md", "docs/questions.md",
        "tests/test_interfaces.py", "tests/test_topology.py", "tests/test_server.py",
        "tests/test_static_security.py", "tests/test_web_contract.py", "tests/frontend/core.test.mjs",
        *NATIVE_PATHS,
    )
    missing = [path for path in required_paths if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(f"required paths missing: {missing}")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import server as server_module
    from homenettopo import commands, discovery
    from homenettopo.interfaces import (
        WirelessAttachmentFact,
        merge_wireless_facts,
        parse_airport_json,
        parse_ifconfig,
        parse_native_wifi_json,
        parse_wifi_hardware_ports,
    )
    from homenettopo.models import ActiveDiscoveryMetadata, SourceStatus, SourceStatusValue
    from homenettopo.neighbors import NeighborFact
    from homenettopo.routes import RouteFact
    from homenettopo.topology import build_snapshot

    metadata = load_metadata()
    active = metadata["active_discovery"]
    limits = metadata["command_limits"]
    expected_values = {
        "bind": (metadata["local_bind"], server_module.BIND_ADDRESS),
        "port": (metadata["default_port"], server_module.DEFAULT_PORT),
        "body bytes": (metadata["http_limits"]["max_json_body_bytes"], discovery.MAX_BODY_BYTES),
        "network count": (active["max_networks_per_request"], discovery.MAX_NETWORKS),
        "address count": (active["max_addresses_per_request"], discovery.MAX_ADDRESSES),
        "timeout default": (active["operation_timeout_default_seconds"], discovery.DEFAULT_OPERATION_TIMEOUT),
        "timeout minimum": (active["operation_timeout_min_seconds"], discovery.MIN_OPERATION_TIMEOUT),
        "timeout maximum": (active["operation_timeout_max_seconds"], discovery.MAX_OPERATION_TIMEOUT),
        "host timeout": (active["nmap_host_timeout_seconds"], commands.NMAP_HOST_TIMEOUT_SECONDS),
        "passive timeout": (limits["passive_timeout_seconds"], commands.PASSIVE_TIMEOUT_SECONDS),
        "wifi interface timeout": (limits["wifi_interface_timeout_seconds"], commands.WIFI_INTERFACES_TIMEOUT_SECONDS),
        "wifi timeout": (limits["wifi_timeout_seconds"], commands.WIFI_TIMEOUT_SECONDS),
    }
    mismatches = [name for name, (documented, implemented) in expected_values.items() if documented != implemented]
    if mismatches:
        raise RuntimeError(f"metadata/source contract mismatch: {mismatches}")
    helper = metadata["native_wifi_helper"]
    if helper.get("cache_max_age_seconds") != server_module.NATIVE_WIFI_MAX_AGE_SECONDS:
        raise RuntimeError("native Wi-Fi cache age differs between metadata and server")
    if helper.get("cache_path") != "~/Library/Caches/HomeNetTopo/wifi-current.json":
        raise RuntimeError("native Wi-Fi cache path contract differs")
    if commands.RFC1918_RANGES != discovery.RFC1918_RANGES or "RFC 1918" not in metadata["network_scope"]:
        raise RuntimeError("active-discovery RFC 1918 boundary differs")

    passive = metadata["passive_evidence"]
    expected_wifi_interfaces = ("/usr/sbin/networksetup", "-listallhardwareports")
    expected_wifi = ("/usr/sbin/system_profiler", "-json", "-timeout", "5", "SPAirPortDataType")
    if commands.wifi_interfaces_spec().argv != expected_wifi_interfaces or passive["wifi_interface_command"] != " ".join(expected_wifi_interfaces):
        raise RuntimeError("Wi-Fi interface command contract differs")
    if commands.wifi_spec().argv != expected_wifi or passive["wifi_detail_command"] != " ".join(expected_wifi):
        raise RuntimeError("Wi-Fi profiler command contract differs")

    interface = parse_ifconfig(
        "en0: flags=8863<UP,RUNNING> mtu 1500\n"
        "    ether 02:00:00:00:10:01\n"
        "    inet 192.168.1.10 netmask 0xffffff00\n"
    )[0]
    media = parse_wifi_hardware_ports("Hardware Port: Wi-Fi\nDevice: en0\nEthernet Address: 02:00:00:00:20:01\n")[0]
    profiler = parse_airport_json(json.dumps({
        "SPAirPortDataType": [{"spairport_airport_interfaces": [{
            "_name": "en0",
            "spairport_current_network_information": {"_name": "Profiler Wi-Fi", "spairport_bssid": "02:aa:bb:cc:dd:01"},
        }]}],
    }))[0]
    native = parse_native_wifi_json(json.dumps({
        "schema_version": 1,
        "collected_at": "2026-08-08T12:00:00Z",
        "authorization": "authorized",
        "wifi": {
            "interface": "en0", "ssid": "Native Wi-Fi", "bssid": "02:aa:bb:cc:dd:42",
            "hardware_mac_address": "02:00:00:00:20:99", "channel": "40", "rssi_dbm": -35,
            "noise_dbm": -90, "phy_mode": "802.11ax", "transmit_rate_mbps": 2401,
        },
    })).fact
    if native is None:
        raise RuntimeError("native Wi-Fi parser lost authorized association")
    fallback = WirelessAttachmentFact(
        "en0", "02:aa:bb:cc:dd:55", "Configured Wi-Fi",
        associated=False, role="relay", configured=True, evidence_source="local_configuration",
    )
    merged = merge_wireless_facts((media,), (profiler,), (native,), (fallback,))[0]
    expected_merge = (
        merged.bssid == "02:aa:bb:cc:dd:42"
        and merged.ssid == "Native Wi-Fi"
        and merged.hardware_mac_address == "02:00:00:00:20:01"
        and merged.role == "relay"
        and merged.evidence_source == "wifi_native"
        and merged.bssid_observed
        and not merged.configured
    )
    if not expected_merge:
        raise RuntimeError("native BSSID priority or local hardware identity regressed")

    snapshot = build_snapshot(
        interfaces=(interface,),
        routes=(RouteFact("0.0.0.0/0", "192.168.1.1", ("U", "G"), "en0", True),),
        neighbors=(
            NeighborFact("192.168.1.11", interface.current_mac_address, "en0", None, True),
            NeighborFact("192.168.1.12", media.hardware_mac_address, "en0", None, True),
            NeighborFact("192.168.1.20", "02:00:00:00:00:20", "en0", None, True),
        ),
        wireless_attachments=(merged,),
        active_hosts=(
            discovery.ActiveHost("192.168.1.13", interface.current_mac_address),
            discovery.ActiveHost("192.168.1.30", "02:00:00:00:00:30"),
        ),
        active_metadata=ActiveDiscoveryMetadata(("192.168.1.0/24",), ("192.168.1.0/24",), True, 1, 3, 30),
        sources=(
            SourceStatus("interfaces", SourceStatusValue.OK), SourceStatus("routes", SourceStatusValue.OK),
            SourceStatus("neighbors", SourceStatusValue.OK), SourceStatus("wifi_native", SourceStatusValue.OK),
        ),
        collected_at="2026-08-08T12:00:00Z",
    )
    host = next(node for node in snapshot.nodes if node.kind.value == "local_host")
    ap = next(node for node in snapshot.nodes if node.kind.value == "access_point")
    peers = {node.id for node in snapshot.nodes if node.kind.value == "device"}
    if set(host.mac_addresses) != {"02:00:00:00:10:01", "02:00:00:00:20:01"}:
        raise RuntimeError("local Private Wi-Fi MAC / Hardware MAC identity is incomplete")
    if ap.properties.get("bssid") != "02:aa:bb:cc:dd:42" or ap.properties.get("identity_source") != "wifi_native":
        raise RuntimeError("native serving BSSID was not assigned to the Wi-Fi node")
    if peers != {"device:192.168.1.20", "device:192.168.1.30"} or snapshot.active_discovery.hosts_reported_up != 1:
        raise RuntimeError("local identity was emitted as peer/active-host evidence")

    owner_paths = {
        "server": "server.py", "agent": "AGENT.md", "api": "docs/api-spec.md",
        "design": "docs/design.md", "readme": "README.md", "interfaces": "homenettopo/interfaces.py",
        "topology": "homenettopo/topology.py", "app": "web/app.js", "deploy": "scripts/deploy.py",
    }
    texts = {name: (ROOT / path).read_text(encoding="utf-8") for name, path in owner_paths.items()}
    for route in ("/api/v1/topology/refresh", "/api/v1/discover", "/api/v1/topology/export"):
        for owner in ("server", "api", "readme"):
            if route not in texts[owner]:
                raise RuntimeError(f"route contract mismatch for {route}: {owner}")
    for owner in ("agent", "api", "design", "readme"):
        lowered = texts[owner].lower()
        for phrase in (
            "corewlan", "corelocation", "location", "hardware mac", "private wi-fi mac", "bssid",
            "gateway", "peer", "lldp", "rfc 1918", "networksetup", "concurrent", "launchagent", "xcode",
        ):
            if phrase not in lowered:
                raise RuntimeError(f"Wi-Fi/path/deployment contract mismatch in {owner}: missing {phrase}")

    for marker in (
        "read_native_wifi_cache", "wifi_native", "corewlan_native_then_system_profiler",
        "homenettopo-wifi://authorize", "ThreadPoolExecutor", '"timeout_sources"', "font-src 'self' data:",
    ):
        if marker not in texts["server"]:
            raise RuntimeError(f"server native/collection contract missing: {marker}")
    for marker in ("parse_native_wifi_json", "evidence_source", "hardware_mac_address", "bssid_observed"):
        if marker not in texts["interfaces"]:
            raise RuntimeError(f"Wi-Fi evidence parser contract missing: {marker}")
    for marker in ("local_macs", "private_wifi_mac_address", "wifi_native", "identity_source"):
        if marker not in texts["topology"]:
            raise RuntimeError(f"topology identity contract missing: {marker}")
    for marker in (
        'hardware_mac_address: "Hardware MAC"', 'private_wifi_mac_address: "Private Wi-Fi MAC"',
        'bssid: "BSSID"', 'rssi_dbm: "RSSI"', 'transmit_rate_mbps: "Transmit rate"',
    ):
        if marker not in texts["app"]:
            raise RuntimeError(f"semantic Details contract missing: {marker}")

    deploy = texts["deploy"]
    for prohibited in ("sudo", "shell=True", "0.0.0.0", "https://"):
        if prohibited in deploy:
            raise RuntimeError(f"deployment script violates local safety boundary: {prohibited}")
    for marker in (
        'LABEL = "com.homenettopo.local"', 'NATIVE_APP_BUNDLE_ID = "com.homenettopo.wifi"',
        'XCODEBUILD_PATH = "/usr/bin/xcodebuild"', 'CODESIGN_PATH = "/usr/bin/codesign"',
        "NATIVE_SOURCE_FILES", "validate_native_source_root", "build_native_app", "replace_native_app",
        "open_native_helper", "ProxyHandler({})", 'run_launchctl("bootstrap"', "wait_for_health(port)",
    ):
        if marker not in deploy:
            raise RuntimeError(f"deployment script contract missing: {marker}")

    test_contracts = {
        "tests/test_interfaces.py": ("test_native_wifi_parser_keeps_current_corewlan_identity_and_metrics", "test_native_bssid_wins_profiler_while_user_confirmed_role_survives"),
        "tests/test_topology.py": ("test_local_ip_and_local_macs_are_host_identity_not_peer_devices", "test_native_corewlan_bssid_is_high_confidence_current_wifi_node"),
        "tests/test_server.py": ("test_native_wifi_cache_requires_fresh_owned_regular_data", "test_native_wifi_identity_wins_profiler_and_local_fallback"),
        "tests/test_static_security.py": ("test_native_privacy_identity_and_login_item_sources_are_explicit", "test_runtime_copy_is_an_explicit_minimal_allowlist"),
        "tests/test_web_contract.py": ("test_graph_nodes_show_local_ip_bssid_and_semantic_wifi_details", "test_canvas_uses_viewbox_camera_full_surface_pan_and_orthogonal_edges"),
    }
    for relative, markers in test_contracts.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        missing_markers = [marker for marker in markers if marker not in source]
        if missing_markers:
            raise RuntimeError(f"required regression definitions missing from {relative}: {missing_markers}")

    if (ROOT / "fixtures").exists():
        raise RuntimeError("independent fixtures directory is not authorized")


def asset_guards() -> None:
    """Check CSP-compatible assets, safe DOM sinks, focus, camera, and capability UI."""

    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    app = (ROOT / "web/app.js").read_text(encoding="utf-8")
    core = (ROOT / "web/core.mjs").read_text(encoding="utf-8")
    css = (ROOT / "web/styles.css").read_text(encoding="utf-8")
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    if re.search(r"<script(?![^>]+src=)[^>]*>", html, re.IGNORECASE) or re.search(r"<style[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline script/style violates CSP")
    if "font-src 'self' data:" not in server:
        raise RuntimeError("font CSP lost local/data allowance")
    if "innerHTML" in app or "insertAdjacentHTML" in app:
        raise RuntimeError("HTML string sink is not allowed")
    for marker in (
        "focusStatusHeading", "focusDialogValidation", "requestAnimationFrame", "collectionInFlight",
        "loadCapabilities({ reportError: false })", "Check Nmap setup", "renderNetworkGroup",
        'setAttribute("viewBox"', 'addEventListener("pointerdown"', "PAN_THRESHOLD = 6",
        "setPointerCapture(event.pointerId)", "preventFitUpscale",
    ):
        if marker not in app:
            raise RuntimeError(f"frontend contract missing: {marker}")
    for marker in ("PATH_EDGE_TYPES", "groups:", "fitCamera", "zoomCamera", "orthogonalEdgePath"):
        if marker not in core:
            raise RuntimeError(f"frontend layout contract missing: {marker}")
    for marker in ("node-access_point", "group-lan_peers", "interface-kind-tunnel", "cursor: grab", "pointer-events: stroke"):
        if marker not in css:
            raise RuntimeError(f"frontend visual contract missing: {marker}")
    for path in (ROOT / "web").iterdir():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        external = [url for url in re.findall(r"https?://[^\s\"')]+", text) if url != "http://www.w3.org/2000/svg"]
        if external:
            raise RuntimeError(f"external URL in {path.name}: {external[0]}")


def hygiene_guards() -> None:
    """Reject tracked caches, build products, exports, and runtime network data."""

    if (ROOT / "tests/__init__.py").exists():
        raise RuntimeError("tests/__init__.py is unnecessary for unittest discovery")
    completed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=False, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError("git ls-files failed")
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        path = Path(raw.decode("utf-8"))
        if PROHIBITED_PARTS.intersection(path.parts) or path.suffix.lower() in PROHIBITED_SUFFIXES:
            raise RuntimeError(f"prohibited tracked path: {path}")
        if path.name.startswith("home-network-topology") and path.suffix == ".json":
            raise RuntimeError(f"runtime export is tracked: {path}")


def node_version() -> int:
    """Require Node.js 20+ for frontend regression."""

    completed = subprocess.run(["node", "--version"], cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("Node.js 20+ is required for full source/test regression")
    match = re.fullmatch(r"v(\d+)(?:\.\d+){2}\s*", completed.stdout)
    if not match or int(match.group(1)) < 20:
        raise RuntimeError("Node.js 20+ is required for full source/test regression")
    return int(match.group(1))


def main() -> int:
    """Execute configured stages and print one truthful summary."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--python-only", action="store_true", help="Skip Node tests; not full source/test regression evidence")
    args = parser.parse_args()

    stages: list[tuple[str, Callable[[], None]]] = [
        ("compile", lambda: run_process([sys.executable, "-m", "compileall", "-q", "server.py", "homenettopo", "tests", "scripts"])),
        ("metadata", parse_metadata),
        ("python-tests", lambda: run_process([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])),
        ("documentation", documentation_guards),
        ("native-source", native_source_guards),
        ("contracts", consistency_guards),
        ("assets", asset_guards),
    ]
    if not args.python_only:
        stages.extend([
            ("node-version", lambda: node_version()),
            ("frontend-tests", lambda: run_process(["node", "--test", "tests/frontend/core.test.mjs"])),
        ])
    stages.append(("hygiene", hygiene_guards))

    results: list[StageResult] = []
    failed = False
    for name, action in stages:
        try:
            action()
        except Exception as exc:
            results.append(StageResult(name, "FAIL", str(exc)))
            failed = True
        else:
            results.append(StageResult(name, "PASS"))
    if args.python_only:
        results.insert(-1, StageResult("frontend-tests", "NOT RUN", "--python-only is not full source/test regression evidence"))

    print("\nHomeNetTopo source/test regression summary")
    for result in results:
        suffix = f" — {result.detail}" if result.detail else ""
        print(f"{result.status:8} {result.name}{suffix}")
    print("\nNative Xcode build, Location authorization, and CoreWLAN runtime require macOS deployment acceptance.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
