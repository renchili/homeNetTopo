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


def parse_metadata() -> None:
    metadata = json.loads((ROOT / "metadata.json").read_text(encoding="utf-8"))
    required = {"name", "status", "runtime", "collection_api", "active_discovery", "snapshot_policy"}
    missing = required - metadata.keys()
    if missing:
        raise RuntimeError(f"metadata missing keys: {sorted(missing)}")


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
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    api = (ROOT / "docs/api-spec.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for route in ("/api/v1/topology/refresh", "/api/v1/discover", "/api/v1/topology/export"):
        if route not in server or route not in api or route not in readme:
            raise RuntimeError(f"route contract mismatch: {route}")
    for value in ("1024", "16 KiB", "operation_timeout_seconds", "--host-timeout 5s", "-oX"):
        if value not in api and value not in server:
            raise RuntimeError(f"public contract value missing: {value}")


def asset_guards() -> None:
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    if re.search(r"<script(?![^>]+src=)[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline script violates CSP")
    if re.search(r"<style[^>]*>", html, re.IGNORECASE):
        raise RuntimeError("inline style violates CSP")
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
