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
            "HomeNetTopoHandler._serve_static", "parse_args", "main",
        ),
        "homenettopo/commands.py": (
            "<module>", "CommandError", "CommandKind", "CommandSpec", "CommandResult",
            "NmapResolution", "wifi_spec", "resolve_nmap", "nmap_spec", "run_command",
        ),
        "homenettopo/discovery.py": (
            "<module>", "ValidationError", "DiscoveryRequest", "ActiveHost", "validate_phase_a",
            "eligible_local_networks", "validate_phase_b", "parse_nmap_xml", "validate_active_hosts",
        ),
        "homenettopo/interfaces.py": (
            "<module>", "InterfaceAddress", "InterfaceFact", "WirelessAttachmentFact",
            "parse_ifconfig", "parse_airport_json",
        ),
        "homenettopo/routes.py": ("<module>", "RouteFact", "parse_routes"),
        "homenettopo/neighbors.py": ("<module>", "NeighborFact", "parse_neighbors"),
        "homenettopo/models.py": (
            "<module>", "ModelError", "Confidence", "NodeKind", "EdgeType", "Evidence",
            "SourceStatus", "NetworkDescriptor", "WarningItem", "Node", "Edge",
            "ActiveDiscoveryMetadata", "TopologySnapshot", "TopologySnapshot.validate",
            "TopologySnapshot.to_dict",
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

    core = (ROOT / "web/core.mjs").read_text(encoding="utf-8")
    app = (ROOT / "web/app.js").read_text(encoding="utf-8")
    comment_contracts = (
        ("web/core.mjs", core, ("Pure frontend state", "Apply one state action", "Lay out an evidence-backed path", "Return a camera rectangle", "orthogonal SVG path")),
        ("web/app.js", app, ("Browser adapter for HomeNetTopo", "Recheck Nmap when unavailable", "Render subnet context first", "viewBox camera")),
    )
    for owner, text, markers in comment_contracts:
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise RuntimeError(f"required code comments missing from {owner}: {missing}")


def consistency_guards() -> None:
    """Check cross-owner safety, path-evidence, UI, and deployment contracts."""

    required_paths = (
        "server.py", "metadata.json", "AGENT.md", "README.md",
        "homenettopo/commands.py", "homenettopo/discovery.py", "homenettopo/interfaces.py",
        "homenettopo/models.py", "homenettopo/neighbors.py", "homenettopo/routes.py",
        "homenettopo/topology.py", "scripts/deploy.py", "web/index.html", "web/core.mjs",
        "web/app.js", "web/styles.css", "docs/api-spec.md", "docs/design.md",
        "docs/plan.md", "docs/questions.md", "tests/test_commands.py",
        "tests/test_interfaces.py", "tests/test_models.py", "tests/test_topology.py",
        "tests/test_discovery.py", "tests/test_server.py", "tests/test_static_security.py",
        "tests/test_web_contract.py", "tests/frontend/core.test.mjs",
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
        parse_airport_json,
    )
    from homenettopo.models import SourceStatus, SourceStatusValue
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

    expected_wifi = ("/usr/sbin/system_profiler", "-json", "-timeout", "5", "SPAirPortDataType")
    if commands.wifi_spec().argv != expected_wifi or metadata["passive_evidence"]["wifi_command"] != " ".join(expected_wifi):
        raise RuntimeError("Wi-Fi command contract differs across source and metadata")
    synthetic_airport = json.dumps({
        "SPAirPortDataType": [{"spairport_airport_interfaces": [{
            "_name": "en0",
            "spairport_current_network_information": {
                "_name": "Synthetic Wi-Fi",
                "spairport_bssid": "02:AA:BB:CC:DD:01",
            },
            "spairport_airport_other_local_wireless_networks": [{
                "_name": "Ignored",
                "spairport_bssid": "02:aa:bb:cc:dd:99",
            }],
        }]}],
    })
    wifi_facts = parse_airport_json(synthetic_airport)
    if len(wifi_facts) != 1 or wifi_facts[0].bssid != "02:aa:bb:cc:dd:01":
        raise RuntimeError("current Wi-Fi BSSID evidence is not parsed canonically")

    interface = InterfaceFact("en0", ("UP",), "physical", (InterfaceAddress("192.168.1.10", 24, "192.168.1.0/24"),))
    route = routes.RouteFact("0.0.0.0/0", "192.168.1.1", ("U", "G"), "en0", True)
    base_sources = (
        SourceStatus("interfaces", SourceStatusValue.OK),
        SourceStatus("routes", SourceStatusValue.OK),
        SourceStatus("neighbors", SourceStatusValue.OK),
        SourceStatus("wifi", SourceStatusValue.OK),
    )
    wifi_snapshot = build_snapshot(
        interfaces=(interface,),
        routes=(route,),
        neighbors=(),
        wireless_attachments=(WirelessAttachmentFact("en0", "02:aa:bb:cc:dd:01", "Synthetic Wi-Fi"),),
        sources=base_sources,
        collected_at="2026-08-03T00:00:00Z",
    )
    wifi_kinds = {node.kind.value for node in wifi_snapshot.nodes}
    wifi_edges = {edge.type.value for edge in wifi_snapshot.edges}
    if "access_point" not in wifi_kinds or "interface_associated_with" not in wifi_edges or "attachment_reaches_gateway" not in wifi_edges:
        raise RuntimeError("Wi-Fi AP-to-gateway path is not connected")
    if "l2_segment" in wifi_kinds or "member_of_l2" in wifi_edges:
        raise RuntimeError("fabricated presentation L2 topology reappeared")

    unknown_snapshot = build_snapshot(
        interfaces=(interface,),
        routes=(route,),
        neighbors=(),
        sources=base_sources[:-1],
        collected_at="2026-08-03T00:00:00Z",
    )
    if not any(node.kind.value == "link_boundary" and node.label == "Intermediate L2 path unknown" for node in unknown_snapshot.nodes):
        raise RuntimeError("missing Ethernet/unknown intermediate path boundary")

    validated_targets = ("192.168.1.0/24", "192.168.1.0/25")
    if commands._canonical_targets(validated_targets) != validated_targets:
        raise RuntimeError("command layer collapsed Phase B targets across owners")
    overlap_request = discovery.validate_phase_a({"networks": list(validated_targets), "operation_timeout_seconds": 30})
    overlap_interfaces = (
        interface,
        InterfaceFact("en1", ("UP",), "physical", (InterfaceAddress("192.168.1.2", 25, "192.168.1.0/25"),)),
    )
    effective_targets = discovery.validate_phase_b(overlap_request, overlap_interfaces)
    if tuple(map(str, effective_targets)) != validated_targets:
        raise RuntimeError("Phase B did not preserve overlapping local owners")
    trusted_host = discovery.ActiveHost("192.168.1.20", "02:00:00:00:00:20")
    if discovery.validate_active_hosts((trusted_host,), effective_targets) != (trusted_host,):
        raise RuntimeError("active host validation changed trusted in-scope evidence")
    try:
        discovery.validate_active_hosts((discovery.ActiveHost("192.168.2.20"),), effective_targets)
    except discovery.ValidationError as exc:
        if (exc.code, exc.status) != ("collection_failed", 500):
            raise RuntimeError("out-of-range Nmap evidence uses the wrong error") from exc
    else:
        raise RuntimeError("active host validation accepted out-of-range evidence")

    invalid_mac_xml = (
        "<nmaprun><host><status state='up'/>"
        "<address addr='192.168.1.20' addrtype='ipv4'/>"
        "<address addr='not-a-mac' addrtype='mac'/></host></nmaprun>"
    )
    try:
        discovery.parse_nmap_xml(invalid_mac_xml)
    except discovery.ValidationError as exc:
        if (exc.code, exc.status) != ("collection_failed", 500):
            raise RuntimeError("invalid Nmap MAC uses the wrong error") from exc
    else:
        raise RuntimeError("Nmap parser accepted an invalid MAC")

    invalid_routes = "Routing tables\n\nInternet:\nDestination Gateway Flags Netif\nalpha beta gamma delta\n"
    try:
        routes.parse_routes(invalid_routes)
    except ValueError:
        pass
    else:
        raise RuntimeError("route parser accepted an unrecognized four-column row")

    texts = {
        "server": (ROOT / "server.py").read_text(encoding="utf-8"),
        "agent": (ROOT / "AGENT.md").read_text(encoding="utf-8"),
        "api": (ROOT / "docs/api-spec.md").read_text(encoding="utf-8"),
        "design": (ROOT / "docs/design.md").read_text(encoding="utf-8"),
        "plan": (ROOT / "docs/plan.md").read_text(encoding="utf-8"),
        "questions": (ROOT / "docs/questions.md").read_text(encoding="utf-8"),
        "readme": (ROOT / "README.md").read_text(encoding="utf-8"),
        "commands": (ROOT / "homenettopo/commands.py").read_text(encoding="utf-8"),
        "interfaces": (ROOT / "homenettopo/interfaces.py").read_text(encoding="utf-8"),
        "models": (ROOT / "homenettopo/models.py").read_text(encoding="utf-8"),
        "topology": (ROOT / "homenettopo/topology.py").read_text(encoding="utf-8"),
        "core": (ROOT / "web/core.mjs").read_text(encoding="utf-8"),
        "app": (ROOT / "web/app.js").read_text(encoding="utf-8"),
        "html": (ROOT / "web/index.html").read_text(encoding="utf-8"),
        "deploy": (ROOT / "scripts/deploy.py").read_text(encoding="utf-8"),
    }
    for route_path in ("/api/v1/topology/refresh", "/api/v1/discover", "/api/v1/topology/export"):
        for owner in ("server", "api", "readme"):
            if route_path not in texts[owner]:
                raise RuntimeError(f"route contract mismatch for {route_path}: {owner}")
    for argument in ("-sn", "-n", "--max-retries", "--host-timeout", "-oX"):
        for owner in ("commands", "api", "readme"):
            if argument not in texts[owner]:
                raise RuntimeError(f"Nmap contract mismatch for {argument}: {owner}")

    contract_owners = ("agent", "api", "design", "plan", "questions", "readme")
    for owner in contract_owners:
        lowered = texts[owner].lower()
        for phrase in ("bssid", "gateway", "intermediate l2 path unknown", "peer"):
            if phrase not in lowered:
                raise RuntimeError(f"gateway-path contract mismatch in {owner}: missing {phrase}")
        if "lldp" not in lowered:
            raise RuntimeError(f"adjacent-device evidence limit missing from {owner}")
    for owner in ("agent", "api", "design", "plan", "readme"):
        lowered = texts[owner].lower()
        for phrase in ("rfc 1918", "adjacent sibling targets", "collection_failed"):
            if phrase not in lowered:
                raise RuntimeError(f"active-discovery contract mismatch in {owner}: missing {phrase}")

    for marker in (
        "wireless_attachments",
        "wifi_spec()",
        "validate_active_hosts",
        "interface_failure",
        '"wifi_bssid_source": "system_profiler"',
    ):
        if marker not in texts["server"]:
            raise RuntimeError(f"server orchestration contract missing: {marker}")
    for marker in ("ACCESS_POINT", "LINK_BOUNDARY", "INTERFACE_ASSOCIATED_WITH", "ATTACHMENT_REACHES_GATEWAY"):
        if marker not in texts["models"]:
            raise RuntimeError(f"path schema marker missing: {marker}")
    for marker in ("WirelessAttachmentFact", "physical_identity_with_gateway", "link_path_inference", "Intermediate L2 path unknown"):
        if marker not in texts["topology"]:
            raise RuntimeError(f"path construction marker missing: {marker}")
    for prohibited in ("l2_segment", "member_of_l2"):
        if prohibited in texts["core"] or prohibited in texts["app"]:
            raise RuntimeError(f"fabricated frontend topology marker returned: {prohibited}")
    for marker in ("PATH_EDGE_TYPES", "not transit hops", "hiddenRelationshipCount", "groups:"):
        if marker not in texts["core"]:
            raise RuntimeError(f"frontend path/peer contract missing: {marker}")
    for marker in ("discover-capability", "Check Nmap setup", "handleDiscoverAction", "renderNetworkGroup"):
        owner = "html" if marker == "discover-capability" else "app"
        if marker not in texts[owner]:
            raise RuntimeError(f"active-capability UI contract missing: {marker}")

    test_contracts = {
        "tests/test_commands.py": ("wifi_spec", "test_passive_commands_are_absolute_and_typed"),
        "tests/test_interfaces.py": ("test_airport_parser_keeps_only_current_association", "test_airport_parser_preserves_redacted_association_without_guessing"),
        "tests/test_models.py": ("test_serializes_access_attachment_nodes_and_edges",),
        "tests/test_topology.py": (
            "test_wifi_bssid_creates_observed_ap_then_inferred_gateway_path",
            "test_redacted_wifi_identity_is_visible_without_guessing",
            "test_tunnel_default_route_skips_l2_attachment_nodes",
            "test_builds_expected_kinds_and_keeps_peers_out_of_gateway_path",
        ),
        "tests/test_discovery.py": (
            "test_contained_targets_owned_by_overlapping_local_networks_remain_separate",
            "test_invalid_nmap_ipv4_or_mac_fails",
            "test_active_hosts_must_belong_to_effective_targets",
        ),
        "tests/test_server.py": (
            "test_capabilities_explain_link_path_sources",
            "test_real_active_discover_preserves_phase_b_effective_targets_order_and_wifi",
            "test_malformed_interface_and_wifi_output_can_produce_coherent_partial_routes",
            "test_real_active_discover_rejects_untrusted_nmap_evidence_and_preserves_snapshot",
        ),
        "tests/test_web_contract.py": (
            "test_discovery_control_is_not_an_unexplained_placeholder",
            "test_gateway_path_and_peer_group_contract",
            "test_canvas_uses_viewbox_camera_full_surface_pan_and_orthogonal_edges",
        ),
        "tests/frontend/core.test.mjs": (
            "presentation graph never invents an L2 transit device",
            "gateway path is ordered while peer devices stay in a separate group",
            "unknown Ethernet attachment is explicit instead of a fabricated switch",
            "tunnel remains a visible direct L3 path",
        ),
    }
    for relative, markers in test_contracts.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        missing_markers = [marker for marker in markers if marker not in source]
        if missing_markers:
            raise RuntimeError(f"required regression definitions missing from {relative}: {missing_markers}")

    deploy_source = texts["deploy"]
    for owner in ("agent", "design", "plan", "readme"):
        if "scripts/deploy.py" not in texts[owner] or "LaunchAgent" not in texts[owner]:
            raise RuntimeError(f"deployment contract mismatch in {owner}")
    for prohibited in ("sudo", "shell=True", "0.0.0.0", "https://"):
        if prohibited in deploy_source:
            raise RuntimeError(f"deployment script violates local safety boundary: {prohibited}")
    for marker in (
        'LABEL = "com.homenettopo.local"',
        '"--bind",\n        "127.0.0.1"',
        '"homenettopo/__init__.py"',
        '"homenettopo/topology.py"',
        '"web/index.html"',
        '"web/styles.css"',
        "validate_source_root(staging)",
        "ProxyHandler({})",
        "runtime_replaced = False",
        'run_launchctl("bootstrap"',
        "wait_for_health(port)",
    ):
        if marker not in deploy_source:
            raise RuntimeError(f"deployment script contract missing: {marker}")

    if re.search(r"(?m)^fixtures/\s+", texts["agent"]) or (ROOT / "fixtures").exists():
        raise RuntimeError("independent fixtures directory is not authorized")


def asset_guards() -> None:
    """Check CSP-compatible assets, safe DOM sinks, focus, camera, and capability UI."""

    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    app = (ROOT / "web/app.js").read_text(encoding="utf-8")
    core = (ROOT / "web/core.mjs").read_text(encoding="utf-8")
    css = (ROOT / "web/styles.css").read_text(encoding="utf-8")
    if re.search(r"<script(?![^>]+src=)[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline script violates CSP")
    if re.search(r"<style[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline style violates CSP")
    if "innerHTML" in app or "insertAdjacentHTML" in app:
        raise RuntimeError("HTML string sink is not allowed")
    if 'id="status-heading" tabindex="-1"' not in html:
        raise RuntimeError("status surface lacks a focus owner")
    if 'id="dialog-error" class="field-error" role="alert" tabindex="-1"' not in html:
        raise RuntimeError("dialog lacks a focusable validation summary")
    for marker in (
        "focusStatusHeading", "focusDialogValidation", "requestAnimationFrame",
        'setAttribute("aria-invalid", "true")', "restoreFocus: false",
        "No peer devices observed", "Unsupported platform", "collectionInFlight",
        'collection: "passive"', 'collection: "active"',
        "loadCapabilities({ reportError: false })", 'setAttribute("aria-disabled", "true")',
        'removeAttribute("aria-disabled")', "Check Nmap setup", "Nmap: unavailable",
        "renderNetworkGroup", 'svgElement("path"', 'setAttribute("viewBox"',
        'addEventListener("pointerdown"', "setPointerCapture(event.pointerId)",
        'classList.add("is-panning")', "suppressGraphClick",
    ):
        if marker not in app:
            raise RuntimeError(f"frontend contract missing: {marker}")
    if app.index("loadCapabilities({ reportError: false })") > app.index('dispatch({ type: "PASSIVE_SUCCESS", snapshot })'):
        raise RuntimeError("capability recheck must finish before passive state release")
    if "passiveInFlight" in app or 'elements["refresh-button"].disabled = true' in app:
        raise RuntimeError("frontend regressed shared collection/focus behavior")
    for marker in (
        "collectionInFlight: null", 'collectionInFlight: "passive"',
        'collectionInFlight: "active"',
        "if (state.collectionInFlight && !action.collection) return state",
        "if (action.collection && state.collectionInFlight !== action.collection) return state",
        'unavailable_reason: "dependency_unavailable"', "available: false",
        "const recovered =", "PATH_EDGE_TYPES", "groups:", "fitCamera", "zoomCamera",
        "orthogonalEdgePath",
    ):
        if marker not in core:
            raise RuntimeError(f"frontend state/layout contract missing: {marker}")
    for marker in ("node-access_point", "node-link_boundary", "group-lan_peers", "interface-kind-tunnel", "cursor: grab", "cursor: grabbing", "pointer-events: stroke"):
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
