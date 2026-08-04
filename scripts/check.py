#!/usr/bin/env python3
"""Run repository-relative compile, contract, test, asset, and hygiene checks.

This script is the single full-regression entrypoint. A stage reports PASS only
when it actually executes successfully; ``--python-only`` remains development
feedback and is never full-regression evidence.
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
    """Load the compact product contract and require its stable top-level keys."""

    metadata = json.loads((ROOT / "metadata.json").read_text(encoding="utf-8"))
    required = {"name", "status", "runtime", "collection_api", "active_discovery", "snapshot_policy"}
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
    """Require useful documentation at the project's non-obvious boundaries."""

    required: dict[str, tuple[str, ...]] = {
        "server.py": (
            "<module>", "ApiError", "PassiveParts", "AppState", "AppState.collect_passive_parts",
            "AppState.passive_refresh", "AppState.active_discover", "HomeNetTopoServer",
            "HomeNetTopoHandler", "HomeNetTopoHandler._validate_collection_headers",
            "HomeNetTopoHandler._serve_static", "parse_args", "main",
        ),
        "homenettopo/commands.py": (
            "<module>", "CommandError", "CommandKind", "CommandSpec", "CommandResult",
            "NmapResolution", "resolve_nmap", "nmap_spec", "run_command",
        ),
        "homenettopo/discovery.py": (
            "<module>", "ValidationError", "DiscoveryRequest", "ActiveHost", "validate_phase_a",
            "eligible_local_networks", "validate_phase_b", "parse_nmap_xml", "validate_active_hosts",
        ),
        "homenettopo/interfaces.py": ("<module>", "InterfaceAddress", "InterfaceFact", "parse_ifconfig"),
        "homenettopo/routes.py": ("<module>", "RouteFact", "parse_routes"),
        "homenettopo/neighbors.py": ("<module>", "NeighborFact", "parse_neighbors"),
        "homenettopo/models.py": (
            "<module>", "ModelError", "Confidence", "NodeKind", "EdgeType", "Evidence", "Node", "Edge",
            "TopologySnapshot", "TopologySnapshot.validate", "TopologySnapshot.to_dict",
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
    for owner, text, markers in (
        ("web/core.mjs", core, ("Pure frontend state", "/**\n * Apply one state action", "Count the unique address union", "Place nodes in deterministic subnet-owned lanes")),
        ("web/app.js", app, ("Browser adapter for HomeNetTopo", "Capability recovery must finish", "HTML strings are never injected", "Render accessible selectable SVG")),
    ):
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise RuntimeError(f"required code comments missing from {owner}: {missing}")


def consistency_guards() -> None:
    """Check cross-owner contracts that unit tests alone cannot express."""

    required_paths = [
        "server.py",
        "homenettopo/commands.py",
        "homenettopo/discovery.py",
        "homenettopo/interfaces.py",
        "homenettopo/models.py",
        "homenettopo/neighbors.py",
        "homenettopo/routes.py",
        "homenettopo/topology.py",
        "scripts/deploy.py",
        "web/index.html",
        "web/core.mjs",
        "web/app.js",
        "web/styles.css",
        "tests/test_discovery.py",
        "tests/test_server.py",
        "tests/test_static_security.py",
        "tests/test_web_contract.py",
        "tests/frontend/core.test.mjs",
    ]
    missing = [path for path in required_paths if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(f"required paths missing: {missing}")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import server as server_module
    from homenettopo import commands, discovery, routes
    from homenettopo.interfaces import InterfaceAddress, InterfaceFact

    metadata = load_metadata()
    active = metadata["active_discovery"]
    command_limits = metadata["command_limits"]
    http_limits = metadata["http_limits"]
    expected_values = {
        "bind": (metadata["local_bind"], server_module.BIND_ADDRESS),
        "port": (metadata["default_port"], server_module.DEFAULT_PORT),
        "body bytes": (http_limits["max_json_body_bytes"], discovery.MAX_BODY_BYTES),
        "network count": (active["max_networks_per_request"], discovery.MAX_NETWORKS),
        "address count": (active["max_addresses_per_request"], discovery.MAX_ADDRESSES),
        "timeout default": (active["operation_timeout_default_seconds"], discovery.DEFAULT_OPERATION_TIMEOUT),
        "timeout minimum": (active["operation_timeout_min_seconds"], discovery.MIN_OPERATION_TIMEOUT),
        "timeout maximum": (active["operation_timeout_max_seconds"], discovery.MAX_OPERATION_TIMEOUT),
        "host timeout": (active["nmap_host_timeout_seconds"], commands.NMAP_HOST_TIMEOUT_SECONDS),
        "passive timeout": (command_limits["passive_timeout_seconds"], commands.PASSIVE_TIMEOUT_SECONDS),
        "stdout limit": (command_limits["stdout_bytes"], commands.STDOUT_LIMIT),
        "stderr limit": (command_limits["stderr_bytes"], commands.STDERR_LIMIT),
        "kill grace": (command_limits["kill_grace_seconds"], commands.KILL_GRACE_SECONDS),
    }
    mismatches = [name for name, (documented, implemented) in expected_values.items() if documented != implemented]
    if mismatches:
        raise RuntimeError(f"metadata/source contract mismatch: {mismatches}")
    if commands.RFC1918_RANGES != discovery.RFC1918_RANGES:
        raise RuntimeError("command and discovery RFC1918 allowlists differ")
    if "RFC 1918" not in metadata.get("network_scope", ""):
        raise RuntimeError("metadata network scope must explicitly identify RFC 1918")

    validated_targets = ("192.168.1.0/24", "192.168.1.0/25")
    if commands._canonical_targets(validated_targets) != validated_targets:
        raise RuntimeError("the command layer must preserve contained targets validated under distinct Phase B owners")

    overlap_request = discovery.validate_phase_a({
        "networks": list(validated_targets),
        "operation_timeout_seconds": 30,
    })
    overlap_interfaces = (
        InterfaceFact("en0", ("UP",), "physical", (InterfaceAddress("192.168.1.1", 24, "192.168.1.0/24"),)),
        InterfaceFact("en1", ("UP",), "physical", (InterfaceAddress("192.168.1.2", 25, "192.168.1.0/25"),)),
    )
    effective_targets = discovery.validate_phase_b(overlap_request, overlap_interfaces)
    if tuple(map(str, effective_targets)) != validated_targets:
        raise RuntimeError("Phase B must preserve targets owned by overlapping local networks")

    trusted_host = discovery.ActiveHost("192.168.1.20", "02:00:00:00:00:20")
    if discovery.validate_active_hosts((trusted_host,), effective_targets) != (trusted_host,):
        raise RuntimeError("active host validation changed an in-scope Nmap result")
    try:
        discovery.validate_active_hosts((discovery.ActiveHost("192.168.2.20"),), effective_targets)
    except discovery.ValidationError as exc:
        if exc.code != "collection_failed" or exc.status != 500:
            raise RuntimeError("out-of-range Nmap evidence uses the wrong normalized error") from exc
    else:
        raise RuntimeError("active host validation accepted a host outside effective targets")

    invalid_mac_xml = (
        "<nmaprun><host><status state='up'/>"
        "<address addr='192.168.1.20' addrtype='ipv4'/>"
        "<address addr='not-a-mac' addrtype='mac'/></host></nmaprun>"
    )
    try:
        discovery.parse_nmap_xml(invalid_mac_xml)
    except discovery.ValidationError as exc:
        if exc.code != "collection_failed" or exc.status != 500:
            raise RuntimeError("invalid Nmap MAC uses the wrong normalized error") from exc
    else:
        raise RuntimeError("the Nmap parser accepted an invalid MAC address")

    invalid_route_output = (
        "Routing tables\n\nInternet:\n"
        "Destination Gateway Flags Netif\n"
        "alpha beta gamma delta\n"
    )
    try:
        routes.parse_routes(invalid_route_output)
    except ValueError:
        pass
    else:
        raise RuntimeError("the route parser accepted an unrecognized four-column row")

    abbreviated_routes = routes.parse_routes(
        "Routing tables\n\nInternet:\n"
        "Destination Gateway Flags Netif Expire\n"
        "192.168.1/24 link#4 UCS en0 !\n"
    )
    if len(abbreviated_routes) != 1 or abbreviated_routes[0].destination != "192.168.1.0/24":
        raise RuntimeError("the route parser does not support the macOS abbreviated-network format")

    server = (ROOT / "server.py").read_text(encoding="utf-8")
    api = (ROOT / "docs/api-spec.md").read_text(encoding="utf-8")
    design = (ROOT / "docs/design.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs/plan.md").read_text(encoding="utf-8")
    questions = (ROOT / "docs/questions.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agent = (ROOT / "AGENT.md").read_text(encoding="utf-8")
    commands_source = (ROOT / "homenettopo/commands.py").read_text(encoding="utf-8")
    models_source = (ROOT / "homenettopo/models.py").read_text(encoding="utf-8")
    topology_source = (ROOT / "homenettopo/topology.py").read_text(encoding="utf-8")
    deploy_source = (ROOT / "scripts/deploy.py").read_text(encoding="utf-8")
    discovery_tests = (ROOT / "tests/test_discovery.py").read_text(encoding="utf-8")
    server_tests = (ROOT / "tests/test_server.py").read_text(encoding="utf-8")
    security_tests = (ROOT / "tests/test_static_security.py").read_text(encoding="utf-8")
    web_tests = (ROOT / "tests/test_web_contract.py").read_text(encoding="utf-8")
    frontend_tests = (ROOT / "tests/frontend/core.test.mjs").read_text(encoding="utf-8")

    for route in ("/api/v1/topology/refresh", "/api/v1/discover", "/api/v1/topology/export"):
        missing_owners = [name for name, text in (("server", server), ("api", api), ("readme", readme)) if route not in text]
        if missing_owners:
            raise RuntimeError(f"route contract mismatch for {route}: {missing_owners}")

    fixed_arguments = ("-sn", "-n", "--max-retries", "--host-timeout", "-oX")
    for value in fixed_arguments:
        missing_owners = [name for name, text in (("commands", commands_source), ("api", api), ("readme", readme)) if value not in text]
        if missing_owners:
            raise RuntimeError(f"Nmap contract mismatch for {value}: {missing_owners}")

    for owner, text in (("agent", agent), ("api", api), ("design", design), ("plan", plan)):
        for phrase in ("RFC 1918", "most-specific containing local network"):
            if phrase not in text:
                raise RuntimeError(f"active-target contract mismatch in {owner}: missing {phrase}")
    for owner, text in (("agent", agent), ("api", api), ("design", design), ("plan", plan), ("readme", readme)):
        if "adjacent sibling targets" not in text.lower():
            raise RuntimeError(f"active-target contract mismatch in {owner}: adjacent siblings are not explicit")

    evidence_contract_owners = (
        ("agent", agent),
        ("api", api),
        ("design", design),
        ("plan", plan),
        ("questions", questions),
    )
    for owner, text in evidence_contract_owners:
        lowered = text.lower()
        for phrase in ("effective target", "collection_failed", "mac"):
            if phrase not in lowered:
                raise RuntimeError(f"Nmap evidence contract mismatch in {owner}: missing {phrase}")
    for owner, text in evidence_contract_owners:
        lowered = text.lower()
        if "passive refresh" not in lowered or "capabil" not in lowered:
            raise RuntimeError(f"capability recovery contract mismatch in {owner}")

    for marker in ("failures: tuple[tuple[str, str], ...]", "validate_active_hosts", "interface_failure"):
        if marker not in server:
            raise RuntimeError(f"active orchestration boundary missing from server.py: {marker}")

    expected_test_markers = {
        "tests/test_discovery.py": (
            "test_contained_targets_owned_by_overlapping_local_networks_remain_separate",
            "test_invalid_nmap_ipv4_or_mac_fails",
            "test_active_hosts_must_belong_to_effective_targets",
        ),
        "tests/test_server.py": (
            "test_real_active_discover_rejects_phase_b_before_resolving_nmap",
            "test_real_active_discover_preserves_phase_b_effective_targets_and_order",
            "test_real_active_discover_command_failure_preserves_previous_snapshot",
            "test_real_active_discover_rejects_untrusted_nmap_evidence_and_preserves_snapshot",
            "test_real_active_discover_classifies_interface_source_failure_before_nmap",
        ),
        "tests/test_static_security.py": (
            "class DeploymentScriptTests",
            "test_launch_agent_is_user_scoped_and_loopback_only",
            "test_runtime_copy_is_an_explicit_minimal_allowlist",
            "test_source_validation_rejects_symbolic_links",
            "test_replace_failure_restores_previous_runtime",
        ),
        "tests/test_web_contract.py": (
            "test_status_and_validation_states_have_focus_owners_and_recovery_logic",
            "test_collection_coordination_and_capability_recheck_contract",
        ),
    }
    test_sources = {
        "tests/test_discovery.py": discovery_tests,
        "tests/test_server.py": server_tests,
        "tests/test_static_security.py": security_tests,
        "tests/test_web_contract.py": web_tests,
    }
    for path, markers in expected_test_markers.items():
        missing_markers = [marker for marker in markers if marker not in test_sources[path]]
        if missing_markers:
            raise RuntimeError(f"required regression definitions missing from {path}: {missing_markers}")
    for marker in (
        "collection state prevents interleaving and ignores stale completions",
        "runtime dependency failure disables and refreshed capabilities restore active discovery",
        "selection state is explicit and clearable",
        "eligible targets are sorted and unique address totals are stable",
        "export filename is deterministic for a snapshot timestamp",
    ):
        if marker not in frontend_tests:
            raise RuntimeError(f"frontend collection/recovery test is missing: {marker}")

    for value in ("route_inference", "address_membership"):
        if value not in topology_source or value not in api:
            raise RuntimeError(f"derived source contract mismatch: {value}")
    if "ROUTES_TO" not in models_source or "EdgeType.ROUTES_TO" not in topology_source or "routes_to" not in api:
        raise RuntimeError("routes_to contract is not connected across model, topology, and API")

    deployment_owners = (("agent", agent), ("design", design), ("plan", plan), ("readme", readme))
    for owner, text in deployment_owners:
        if "scripts/deploy.py" not in text or "LaunchAgent" not in text:
            raise RuntimeError(f"deployment contract mismatch in {owner}")
    for prohibited in ("sudo", "shell=True", "0.0.0.0", "https://"):
        if prohibited in deploy_source:
            raise RuntimeError(f"deployment script violates the local safety boundary: {prohibited}")
    for marker in (
        'LABEL = "com.homenettopo.local"',
        '"--bind",\n        "127.0.0.1"',
        '"homenettopo/__init__.py"',
        '"homenettopo/topology.py"',
        '"web/index.html"',
        '"web/styles.css"',
        'validate_source_root(staging)',
        'ProxyHandler({})',
        'runtime_replaced = False',
        'run_launchctl("bootstrap"',
        "wait_for_health(port)",
    ):
        if marker not in deploy_source:
            raise RuntimeError(f"deployment script contract missing: {marker}")

    if re.search(r"(?m)^fixtures/\s+", agent) or (ROOT / "fixtures").exists():
        raise RuntimeError("independent fixtures directory is not authorized")


def asset_guards() -> None:
    """Check CSP-compatible assets, safe DOM sinks, and focus contracts."""

    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    app = (ROOT / "web/app.js").read_text(encoding="utf-8")
    core = (ROOT / "web/core.mjs").read_text(encoding="utf-8")
    if re.search(r"<script(?![^>]+src=)[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline script violates CSP")
    if re.search(r"<style[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline style violates CSP")
    if "innerHTML" in app or "insertAdjacentHTML" in app:
        raise RuntimeError("HTML string sink is not allowed in the frontend adapter")
    if 'id="status-heading" tabindex="-1"' not in html:
        raise RuntimeError("the status surface lacks a programmatic focus owner")
    if 'id="dialog-error" class="field-error" role="alert" tabindex="-1"' not in html:
        raise RuntimeError("the discovery dialog lacks a focusable validation summary")
    for marker in (
        "focusStatusHeading",
        "focusDialogValidation",
        "requestAnimationFrame",
        'setAttribute("aria-invalid", "true")',
        "restoreFocus: false",
        "No neighbor devices observed",
        "Unsupported platform",
        "collectionInFlight",
        'collection: "passive"',
        'collection: "active"',
        "loadCapabilities({ reportError: false })",
        'setAttribute("aria-disabled", "true")',
        'removeAttribute("aria-disabled")',
        "Restore Nmap, then refresh passive to check again.",
    ):
        if marker not in app:
            raise RuntimeError(f"frontend focus/recovery contract missing: {marker}")
    recheck = app.index("loadCapabilities({ reportError: false })")
    completion = app.index('dispatch({ type: "PASSIVE_SUCCESS", snapshot })')
    if recheck > completion:
        raise RuntimeError("capability recheck must finish before passive collection state is released")
    if "passiveInFlight" in app:
        raise RuntimeError("passive-only concurrency state must not replace shared collection coordination")
    if 'elements["refresh-button"].disabled = true' in app:
        raise RuntimeError("collection loading must not remove the focused refresh trigger from navigation")
    for marker in (
        "collectionInFlight: null",
        'collectionInFlight: "passive"',
        'collectionInFlight: "active"',
        "if (state.collectionInFlight && !action.collection) return state",
        "if (action.collection && state.collectionInFlight !== action.collection) return state",
        'unavailable_reason: "dependency_unavailable"',
        "available: false",
        "const recovered =",
    ):
        if marker not in core:
            raise RuntimeError(f"frontend collection/capability state missing: {marker}")
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
        raise RuntimeError("tests/__init__.py is an unnecessary package marker for unittest discovery")
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
