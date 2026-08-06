#!/usr/bin/env python3
"""Run repository-relative compile, contract, test, asset, and hygiene checks.

This is the single full-regression entrypoint. A stage reports PASS only after
it executes successfully. ``--python-only`` is development feedback and cannot
be cited as full-regression evidence.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED_PARTS = {"__pycache__", ".pytest_cache", "node_modules", ".venv", "coverage", "htmlcov", "test-results", "reports"}
PROHIBITED_SUFFIXES = {".pyc", ".pcap", ".pcapng", ".log", ".sqlite", ".db"}


@dataclass
class StageResult:
    """One executed regression stage and its user-visible result."""

    name: str
    status: str
    detail: str = ""


def run_process(argv: list[str]) -> None:
    """Run one repository command and normalize nonzero exits."""

    completed = subprocess.run(argv, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(argv)}")


def load_metadata() -> dict:
    """Load the compact product contract and require stable owner sections."""

    metadata = json.loads((ROOT / "metadata.json").read_text(encoding="utf-8"))
    required = {
        "name", "status", "runtime", "collection_api", "passive_evidence",
        "active_discovery", "snapshot_policy", "gateway_path", "graph_layout",
        "command_limits", "http_limits", "network_scope", "local_bind", "default_port",
    }
    missing = required - metadata.keys()
    if missing:
        raise RuntimeError(f"metadata missing keys: {sorted(missing)}")
    return metadata


def parse_metadata() -> None:
    """Regression stage wrapper for metadata loading."""

    load_metadata()


def _qualified_docstrings(path: Path) -> dict[str, str | None]:
    """Collect module, top-level, and class-method docstrings by qualified name."""

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
    """Require documentation at security, evidence, state, and deployment boundaries."""

    required: dict[str, tuple[str, ...]] = {
        "server.py": (
            "<module>", "ApiError", "PassiveParts", "AppState", "AppState.collect_passive_parts",
            "AppState.passive_refresh", "AppState.active_discover", "HomeNetTopoServer",
            "HomeNetTopoHandler", "HomeNetTopoHandler._validate_collection_headers",
            "HomeNetTopoHandler._serve_static", "canonical_mac_argument", "parse_args", "main",
        ),
        "homenettopo/commands.py": (
            "<module>", "CommandError", "CommandKind", "CommandSpec", "CommandResult",
            "NmapResolution", "wifi_interfaces_spec", "wifi_spec", "resolve_nmap", "nmap_spec", "run_command",
        ),
        "homenettopo/discovery.py": (
            "<module>", "ValidationError", "DiscoveryRequest", "ActiveHost", "validate_phase_a",
            "eligible_local_networks", "validate_phase_b", "parse_nmap_xml", "validate_active_hosts",
        ),
        "homenettopo/interfaces.py": (
            "<module>", "InterfaceAddress", "InterfaceFact", "WirelessAttachmentFact",
            "parse_ifconfig", "parse_wifi_hardware_ports", "merge_wireless_facts", "parse_airport_json",
        ),
        "homenettopo/routes.py": ("<module>", "RouteFact", "parse_routes"),
        "homenettopo/neighbors.py": ("<module>", "NeighborFact", "parse_neighbors"),
        "homenettopo/models.py": (
            "<module>", "ModelError", "Confidence", "NodeKind", "EdgeType", "Evidence",
            "SourceStatus", "NetworkDescriptor", "WarningItem", "Node", "Edge",
            "ActiveDiscoveryMetadata", "TopologySnapshot", "TopologySnapshot.validate", "TopologySnapshot.to_dict",
        ),
        "homenettopo/topology.py": ("<module>", "build_snapshot"),
        "scripts/deploy.py": (
            "<module>", "DeploymentError", "validate_source_root", "build_launch_agent", "stage_runtime",
            "replace_runtime", "install", "restart", "status", "uninstall", "parse_args", "main",
        ),
        "scripts/check.py": ("<module>", "StageResult", "documentation_guards", "consistency_guards", "main"),
    }
    for relative, symbols in required.items():
        docs = _qualified_docstrings(ROOT / relative)
        missing = [symbol for symbol in symbols if not docs.get(symbol)]
        if missing:
            raise RuntimeError(f"required code documentation missing from {relative}: {missing}")

    comment_contracts = {
        "web/core.mjs": ("Pure frontend state", "Lay out an evidence-backed path", "camera"),
        "web/app.js": ("Browser adapter for HomeNetTopo", "viewBox camera", "safe DOM/SVG"),
    }
    for relative, markers in comment_contracts.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in source]
        if missing:
            raise RuntimeError(f"required code comments missing from {relative}: {missing}")


def consistency_guards() -> None:
    """Check cross-owner safety, Wi-Fi identity, path, UI, and deployment contracts."""

    required_paths = (
        "server.py", "metadata.json", "AGENT.md", "README.md",
        "homenettopo/commands.py", "homenettopo/discovery.py", "homenettopo/interfaces.py",
        "homenettopo/models.py", "homenettopo/neighbors.py", "homenettopo/routes.py",
        "homenettopo/topology.py", "scripts/deploy.py", "web/index.html", "web/core.mjs",
        "web/app.js", "web/styles.css", "docs/api-spec.md", "docs/design.md", "docs/plan.md",
        "docs/questions.md", "tests/test_commands.py", "tests/test_interfaces.py",
        "tests/test_models.py", "tests/test_topology.py", "tests/test_discovery.py",
        "tests/test_server.py", "tests/test_static_security.py", "tests/test_web_contract.py",
        "tests/frontend/core.test.mjs",
    )
    missing = [path for path in required_paths if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(f"required paths missing: {missing}")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import server as server_module
    from homenettopo import commands, discovery, routes
    from homenettopo.interfaces import (
        InterfaceAddress,
        InterfaceFact,
        WirelessAttachmentFact,
        merge_wireless_facts,
        parse_airport_json,
        parse_ifconfig,
        parse_wifi_hardware_ports,
    )
    from homenettopo.models import ActiveDiscoveryMetadata, SourceStatus, SourceStatusValue
    from homenettopo.neighbors import NeighborFact
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
        "stdout limit": (limits["stdout_bytes"], commands.STDOUT_LIMIT),
        "stderr limit": (limits["stderr_bytes"], commands.STDERR_LIMIT),
        "kill grace": (limits["kill_grace_seconds"], commands.KILL_GRACE_SECONDS),
    }
    mismatches = [name for name, (documented, implemented) in expected_values.items() if documented != implemented]
    if mismatches:
        raise RuntimeError(f"metadata/source contract mismatch: {mismatches}")
    if commands.RFC1918_RANGES != discovery.RFC1918_RANGES:
        raise RuntimeError("command and discovery RFC1918 allowlists differ")
    if "RFC 1918" not in metadata["network_scope"]:
        raise RuntimeError("metadata network scope must explicitly identify RFC 1918")

    expected_wifi_interfaces = ("/usr/sbin/networksetup", "-listallhardwareports")
    expected_wifi = ("/usr/sbin/system_profiler", "-json", "-timeout", "5", "SPAirPortDataType")
    passive = metadata["passive_evidence"]
    if commands.wifi_interfaces_spec().argv != expected_wifi_interfaces or passive["wifi_interface_command"] != " ".join(expected_wifi_interfaces):
        raise RuntimeError("Wi-Fi interface command contract differs across source and metadata")
    if commands.wifi_spec().argv != expected_wifi or passive["wifi_detail_command"] != " ".join(expected_wifi):
        raise RuntimeError("Wi-Fi detail command contract differs across source and metadata")
    if not passive.get("commands_run_concurrently") or not passive.get("wifi_detail_failure_is_optional"):
        raise RuntimeError("metadata does not preserve concurrent optional Wi-Fi detail semantics")

    parsed_interface = parse_ifconfig(
        "en0: flags=8863<UP,RUNNING> mtu 1500\n"
        "    ether 02:00:00:00:10:01\n"
        "    inet 192.168.1.10 netmask 0xffffff00\n"
    )[0]
    if parsed_interface.current_mac_address != "02:00:00:00:10:01":
        raise RuntimeError("ifconfig current MAC is not parsed canonically")

    synthetic_ports = (
        "Hardware Port: Ethernet\nDevice: en5\nEthernet Address: 02:00:00:00:00:05\n\n"
        "Hardware Port: Wi-Fi\nDevice: en0\nEthernet Address: 02:00:00:00:20:01\n"
    )
    media = parse_wifi_hardware_ports(synthetic_ports)[0]
    if media.interface != "en0" or media.hardware_mac_address != "02:00:00:00:20:01" or media.bssid is not None:
        raise RuntimeError("networksetup hardware MAC is not separated from BSSID")

    synthetic_airport = json.dumps({
        "SPAirPortDataType": [{"spairport_airport_interfaces": [{
            "_name": "en0",
            "spairport_current_network_information": {
                "_name": "Synthetic Wi-Fi",
                "spairport_bssid": "02:AA:BB:CC:DD:01",
                "spairport_channel": "44 (5GHz, 80MHz)",
                "spairport_signal_noise": "-41 dBm / -91 dBm",
                "spairport_phymode": "802.11ax",
                "spairport_transmit_rate": "1200",
            },
        }]}],
    })
    observed = parse_airport_json(synthetic_airport)[0]
    if (
        observed.bssid != "02:aa:bb:cc:dd:01"
        or not observed.bssid_observed
        or observed.rssi_dbm != -41
        or observed.noise_dbm != -91
        or observed.transmit_rate_mbps != 1200
    ):
        raise RuntimeError("current Wi-Fi radio evidence is not parsed canonically")

    fallback = WirelessAttachmentFact(
        "en0", "02:aa:bb:cc:dd:55", "Configured Wi-Fi",
        associated=False, role="relay", configured=True,
    )
    merged = merge_wireless_facts((media,), (fallback,), (observed,))[0]
    if (
        merged.hardware_mac_address != media.hardware_mac_address
        or merged.bssid != observed.bssid
        or not merged.bssid_observed
        or merged.configured
        or merged.role != "relay"
    ):
        raise RuntimeError("automatic BSSID did not override local fallback while retaining role")

    interface = InterfaceFact(
        "en0", ("UP",), "physical",
        (InterfaceAddress("192.168.1.10", 24, "192.168.1.0/24"),),
        "02:00:00:00:10:01",
    )
    route = routes.RouteFact("0.0.0.0/0", "192.168.1.1", ("U", "G"), "en0", True)
    sources = (
        SourceStatus("interfaces", SourceStatusValue.OK),
        SourceStatus("routes", SourceStatusValue.OK),
        SourceStatus("neighbors", SourceStatusValue.OK),
        SourceStatus("wifi", SourceStatusValue.OK),
    )
    attachment = WirelessAttachmentFact(
        "en0", observed.bssid, observed.ssid,
        hardware_mac_address=media.hardware_mac_address,
        channel=observed.channel,
        rssi_dbm=observed.rssi_dbm,
        noise_dbm=observed.noise_dbm,
        phy_mode=observed.phy_mode,
        transmit_rate_mbps=observed.transmit_rate_mbps,
        bssid_observed=True,
    )
    metadata_active = ActiveDiscoveryMetadata(("192.168.1.0/24",), ("192.168.1.0/24",), True, 1, 3, 30)
    snapshot = build_snapshot(
        interfaces=(interface,),
        routes=(route,),
        neighbors=(
            NeighborFact("192.168.1.11", interface.current_mac_address, "en0", None, True),
            NeighborFact("192.168.1.12", media.hardware_mac_address, "en0", None, True),
            NeighborFact("192.168.1.20", "02:00:00:00:00:20", "en0", None, True),
        ),
        wireless_attachments=(attachment,),
        active_hosts=(
            discovery.ActiveHost("192.168.1.13", interface.current_mac_address),
            discovery.ActiveHost("192.168.1.30", "02:00:00:00:00:30"),
        ),
        active_metadata=metadata_active,
        sources=sources,
        collected_at="2026-08-03T00:00:00Z",
    )
    host = next(node for node in snapshot.nodes if node.kind.value == "local_host")
    iface = next(node for node in snapshot.nodes if node.kind.value == "interface")
    ap = next(node for node in snapshot.nodes if node.kind.value == "access_point")
    peers = {node.id for node in snapshot.nodes if node.kind.value == "device"}
    if set(host.mac_addresses) != {interface.current_mac_address, media.hardware_mac_address}:
        raise RuntimeError("local host MAC identity is incomplete")
    if iface.properties.get("private_wifi_mac_address") != interface.current_mac_address:
        raise RuntimeError("private Wi-Fi MAC was not distinguished from hardware MAC")
    if ap.properties.get("bssid") != observed.bssid or ap.mac_addresses != (observed.bssid,):
        raise RuntimeError("serving BSSID was not assigned only to the connected Wi-Fi node")
    if peers != {"device:192.168.1.20", "device:192.168.1.30"} or snapshot.active_discovery.hosts_reported_up != 1:
        raise RuntimeError("local MAC evidence was emitted as a peer or active host")

    validated_targets = ("192.168.1.0/24", "192.168.1.0/25")
    if commands._canonical_targets(validated_targets) != validated_targets:
        raise RuntimeError("command layer collapsed Phase B targets across owners")
    request = discovery.validate_phase_a({"networks": list(validated_targets), "operation_timeout_seconds": 30})
    overlap_interfaces = (
        interface,
        InterfaceFact("en1", ("UP",), "physical", (InterfaceAddress("192.168.1.2", 25, "192.168.1.0/25"),)),
    )
    effective = discovery.validate_phase_b(request, overlap_interfaces)
    if tuple(map(str, effective)) != validated_targets:
        raise RuntimeError("Phase B did not preserve adjacent sibling or overlapping-owner targets")

    texts = {
        name: (ROOT / path).read_text(encoding="utf-8")
        for name, path in {
            "server": "server.py", "agent": "AGENT.md", "api": "docs/api-spec.md",
            "design": "docs/design.md", "plan": "docs/plan.md", "questions": "docs/questions.md",
            "readme": "README.md", "interfaces": "homenettopo/interfaces.py",
            "topology": "homenettopo/topology.py", "core": "web/core.mjs",
            "app": "web/app.js", "html": "web/index.html", "deploy": "scripts/deploy.py",
        }.items()
    }
    for route_path in ("/api/v1/topology/refresh", "/api/v1/discover", "/api/v1/topology/export"):
        for owner in ("server", "api", "readme"):
            if route_path not in texts[owner]:
                raise RuntimeError(f"route contract mismatch for {route_path}: {owner}")

    for owner in ("agent", "api", "design", "readme"):
        lowered = texts[owner].lower()
        for phrase in (
            "hardware mac", "private wi-fi mac", "bssid", "gateway", "peer", "lldp",
            "rfc 1918", "adjacent sibling targets", "collection_failed", "networksetup",
            "concurrent", "timeout_sources", "launchagent",
        ):
            if phrase not in lowered:
                raise RuntimeError(f"Wi-Fi/path/safety contract mismatch in {owner}: missing {phrase}")

    for marker in (
        "ThreadPoolExecutor", "wifi_override", "merge_wireless_facts", "validate_active_hosts",
        '"wifi_local_fallback_configured"', '"timeout_sources"', "font-src 'self' data:",
        '"--wifi-interface"', '"--wifi-bssid"', '"--wifi-role"',
    ):
        if marker not in texts["server"]:
            raise RuntimeError(f"server orchestration contract missing: {marker}")
    for marker in (
        "current_mac_address", "hardware_mac_address", "bssid_observed", "merge_wireless_facts",
    ):
        if marker not in texts["interfaces"]:
            raise RuntimeError(f"Wi-Fi parser contract missing: {marker}")
    for marker in (
        "local_macs", "private_wifi_mac_address", '"bssid"', '"role"', "local_configuration",
    ):
        if marker not in texts["topology"]:
            raise RuntimeError(f"topology identity contract missing: {marker}")
    for marker in (
        "PROPERTY_LABELS", 'hardware_mac_address: "Hardware MAC"',
        'private_wifi_mac_address: "Private Wi-Fi MAC"', 'bssid: "BSSID"',
        'rssi_dbm: "RSSI"', 'transmit_rate_mbps: "Transmit rate"',
    ):
        if marker not in texts["app"]:
            raise RuntimeError(f"semantic Details contract missing: {marker}")
    for prohibited in ("l2_segment", "member_of_l2"):
        if prohibited in texts["core"] or prohibited in texts["app"]:
            raise RuntimeError(f"fabricated frontend topology marker returned: {prohibited}")

    test_contracts = {
        "tests/test_interfaces.py": (
            "test_wifi_hardware_ports_identify_adapter_hardware_mac_only",
            "test_airport_parser_keeps_current_radio_metrics_and_normalizes_bssid",
            "test_merge_preserves_hardware_mac_and_prefers_automatic_bssid",
        ),
        "tests/test_topology.py": (
            "test_local_ip_and_local_macs_are_host_identity_not_peer_devices",
            "test_wifi_bssid_is_serving_radio_not_local_interface_mac",
            "test_user_confirmed_relay_fallback_is_visible_without_claiming_observation",
            "test_tunnel_default_route_skips_l2_attachment_nodes",
        ),
        "tests/test_discovery.py": (
            "test_contained_targets_owned_by_overlapping_local_networks_remain_separate",
            "test_invalid_nmap_ipv4_or_mac_fails",
            "test_active_hosts_must_belong_to_effective_targets",
        ),
        "tests/test_server.py": (
            "test_capabilities_explain_link_path_sources",
            "test_real_active_discover_preserves_phase_b_effective_targets_order_and_wifi",
            "test_wifi_detail_timeout_degrades_without_failing_passive_collection",
            "test_material_timeouts_return_source_specific_504_details",
        ),
        "tests/test_static_security.py": (
            "test_wifi_fallback_is_validated_and_written_only_to_program_arguments",
            "test_runtime_copy_is_an_explicit_minimal_allowlist",
        ),
        "tests/test_web_contract.py": (
            "test_graph_nodes_show_local_ip_bssid_and_semantic_wifi_details",
            "test_canvas_uses_viewbox_camera_full_surface_pan_and_orthogonal_edges",
        ),
        "tests/frontend/core.test.mjs": (
            "presentation graph never invents an L2 transit device",
            "gateway path is ordered while peer devices stay in a separate group",
            "tunnel remains a visible direct L3 path",
        ),
    }
    for relative, markers in test_contracts.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        missing_markers = [marker for marker in markers if marker not in source]
        if missing_markers:
            raise RuntimeError(f"required regression definitions missing from {relative}: {missing_markers}")

    deploy = texts["deploy"]
    for prohibited in ("sudo", "shell=True", "0.0.0.0", "https://"):
        if prohibited in deploy:
            raise RuntimeError(f"deployment script violates local safety boundary: {prohibited}")
    for marker in (
        'LABEL = "com.homenettopo.local"', '"--bind",\n        "127.0.0.1"',
        '"--wifi-interface"', '"--wifi-bssid"', '"--wifi-ssid"', '"--wifi-role"',
        "validate_source_root(staging)", "ProxyHandler({})", "runtime_replaced = False",
        'run_launchctl("bootstrap"', "wait_for_health(port)",
    ):
        if marker not in deploy:
            raise RuntimeError(f"deployment script contract missing: {marker}")

    if re.search(r"(?m)^fixtures/\s+", texts["agent"]) or (ROOT / "fixtures").exists():
        raise RuntimeError("independent fixtures directory is not authorized")


def asset_guards() -> None:
    """Check CSP-compatible assets, safe DOM sinks, focus, camera, and capability UI."""

    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    app = (ROOT / "web/app.js").read_text(encoding="utf-8")
    core = (ROOT / "web/core.mjs").read_text(encoding="utf-8")
    css = (ROOT / "web/styles.css").read_text(encoding="utf-8")
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    if re.search(r"<script(?![^>]+src=)[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline script violates CSP")
    if re.search(r"<style[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline style violates CSP")
    if "font-src 'self' data:" not in server or "https:" in server.split("Content-Security-Policy", 1)[1].split(")", 1)[0]:
        raise RuntimeError("font CSP must allow local/data fonts without external origins")
    if "innerHTML" in app or "insertAdjacentHTML" in app:
        raise RuntimeError("HTML string sink is not allowed")
    for marker in (
        "focusStatusHeading", "focusDialogValidation", "requestAnimationFrame",
        'setAttribute("aria-invalid", "true")', "restoreFocus: false", "collectionInFlight",
        "loadCapabilities({ reportError: false })", 'setAttribute("aria-disabled", "true")',
        'removeAttribute("aria-disabled")', "Check Nmap setup", "renderNetworkGroup",
        'svgElement("path"', 'setAttribute("viewBox"', 'addEventListener("pointerdown"',
        "setPointerCapture(event.pointerId)", "PAN_THRESHOLD = 6", "preventFitUpscale",
    ):
        if marker not in app:
            raise RuntimeError(f"frontend contract missing: {marker}")
    if "passiveInFlight" in app or 'elements["refresh-button"].disabled = true' in app:
        raise RuntimeError("frontend regressed shared collection/focus behavior")
    for marker in ("PATH_EDGE_TYPES", "groups:", "fitCamera", "zoomCamera", "orthogonalEdgePath"):
        if marker not in core:
            raise RuntimeError(f"frontend state/layout contract missing: {marker}")
    for marker in ("node-access_point", "node-link_boundary", "group-lan_peers", "interface-kind-tunnel", "cursor: grab", "pointer-events: stroke"):
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
    """Reject tracked caches, reports, runtime exports, and local network data."""

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
    """Require the documented Node.js major version for full regression."""

    completed = subprocess.run(["node", "--version"], cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("Node.js 20+ is required for full regression")
    match = re.fullmatch(r"v(\d+)(?:\.\d+){2}\s*", completed.stdout)
    if not match or int(match.group(1)) < 20:
        raise RuntimeError("Node.js 20+ is required for full regression")
    return int(match.group(1))


def main() -> int:
    """Execute every configured stage and print one truthful summary."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--python-only", action="store_true", help="Skip frontend Node tests; not full regression evidence")
    args = parser.parse_args()

    stages: list[tuple[str, Callable[[], None]]] = [
        ("compile", lambda: run_process([sys.executable, "-m", "compileall", "-q", "server.py", "homenettopo", "tests", "scripts"])),
        ("metadata", parse_metadata),
        ("python-tests", lambda: run_process([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])),
        ("documentation", documentation_guards),
        ("contracts", consistency_guards),
        ("assets", asset_guards),
    ]
    if not args.python_only:
        stages.append(("node-version", lambda: node_version()))
        stages.append(("frontend-tests", lambda: run_process(["node", "--test", "tests/frontend/core.test.mjs"])))
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
        results.insert(-1, StageResult("frontend-tests", "NOT RUN", "--python-only is not full-regression evidence"))

    print("\nHomeNetTopo regression summary")
    for result in results:
        suffix = f" — {result.detail}" if result.detail else ""
        print(f"{result.status:8} {result.name}{suffix}")
    if failed:
        return 1
    if args.python_only:
        print("\nPython-only development checks completed; full regression was NOT RUN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
