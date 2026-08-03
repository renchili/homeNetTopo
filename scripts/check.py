#!/usr/bin/env python3
"""Repository-relative full regression entrypoint."""

from __future__ import annotations

import argparse
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
    name: str
    status: str
    detail: str = ""


def run_process(argv: list[str]) -> None:
    completed = subprocess.run(argv, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(argv)}")


def load_metadata() -> dict:
    metadata = json.loads((ROOT / "metadata.json").read_text(encoding="utf-8"))
    required = {"name", "status", "runtime", "collection_api", "active_discovery", "snapshot_policy"}
    missing = required - metadata.keys()
    if missing:
        raise RuntimeError(f"metadata missing keys: {sorted(missing)}")
    return metadata


def parse_metadata() -> None:
    load_metadata()


def consistency_guards() -> None:
    required_paths = [
        "server.py",
        "homenettopo/commands.py",
        "homenettopo/discovery.py",
        "homenettopo/interfaces.py",
        "homenettopo/models.py",
        "homenettopo/neighbors.py",
        "homenettopo/routes.py",
        "homenettopo/topology.py",
        "web/index.html",
        "web/core.mjs",
        "web/app.js",
        "web/styles.css",
        "tests/frontend/core.test.mjs",
    ]
    missing = [path for path in required_paths if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(f"required paths missing: {missing}")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import server as server_module
    from homenettopo import commands, discovery

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

    server = (ROOT / "server.py").read_text(encoding="utf-8")
    api = (ROOT / "docs/api-spec.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agent = (ROOT / "AGENT.md").read_text(encoding="utf-8")
    commands_source = (ROOT / "homenettopo/commands.py").read_text(encoding="utf-8")
    models_source = (ROOT / "homenettopo/models.py").read_text(encoding="utf-8")
    topology_source = (ROOT / "homenettopo/topology.py").read_text(encoding="utf-8")

    for route in ("/api/v1/topology/refresh", "/api/v1/discover", "/api/v1/topology/export"):
        missing_owners = [name for name, text in (("server", server), ("api", api), ("readme", readme)) if route not in text]
        if missing_owners:
            raise RuntimeError(f"route contract mismatch for {route}: {missing_owners}")

    fixed_arguments = ("-sn", "-n", "--max-retries", "--host-timeout", "-oX")
    for value in fixed_arguments:
        missing_owners = [name for name, text in (("commands", commands_source), ("api", api), ("readme", readme)) if value not in text]
        if missing_owners:
            raise RuntimeError(f"Nmap contract mismatch for {value}: {missing_owners}")

    for value in ("route_inference", "address_membership"):
        if value not in topology_source or value not in api:
            raise RuntimeError(f"derived source contract mismatch: {value}")
    if "ROUTES_TO" not in models_source or "EdgeType.ROUTES_TO" not in topology_source or "routes_to" not in api:
        raise RuntimeError("routes_to contract is not connected across model, topology, and API")

    if re.search(r"(?m)^fixtures/\s+", agent) or (ROOT / "fixtures").exists():
        raise RuntimeError("independent fixtures directory is not authorized")


def asset_guards() -> None:
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    app = (ROOT / "web/app.js").read_text(encoding="utf-8")
    if re.search(r"<script(?![^>]+src=)[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline script violates CSP")
    if re.search(r"<style[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline style violates CSP")
    if "innerHTML" in app or "insertAdjacentHTML" in app:
        raise RuntimeError("HTML string sink is not allowed in the frontend adapter")
    for path in (ROOT / "web").iterdir():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        external = [url for url in re.findall(r"https?://[^\s\"')]+", text) if url != "http://www.w3.org/2000/svg"]
        if external:
            raise RuntimeError(f"external URL in {path.name}: {external[0]}")


def hygiene_guards() -> None:
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
    completed = subprocess.run(["node", "--version"], cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("Node.js 20+ is required for full regression")
    match = re.fullmatch(r"v(\d+)(?:\.\d+){2}\s*", completed.stdout)
    if not match or int(match.group(1)) < 20:
        raise RuntimeError("Node.js 20+ is required for full regression")
    return int(match.group(1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-only", action="store_true", help="Skip frontend Node tests; not full regression evidence")
    args = parser.parse_args()

    stages: list[tuple[str, Callable[[], None]]] = [
        ("compile", lambda: run_process([sys.executable, "-m", "compileall", "-q", "server.py", "homenettopo", "tests", "scripts"])),
        ("metadata", parse_metadata),
        ("python-tests", lambda: run_process([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])),
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
