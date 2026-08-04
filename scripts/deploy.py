#!/usr/bin/env python3
"""Deploy HomeNetTopo as a per-user macOS LaunchAgent.

The deployment intentionally stays inside the current user's Library directory,
never requests administrator privileges, and keeps the service bound to
127.0.0.1.  It copies only the explicit runtime allowlist below, so tests,
repository metadata, and local development artifacts are not deployed.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence

LABEL = "com.homenettopo.local"
SOURCE_ROOT = Path(__file__).resolve().parents[1]
INSTALL_DIR = Path.home() / "Library" / "Application Support" / "HomeNetTopo"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_DIR = Path.home() / "Library" / "Logs" / "HomeNetTopo"
RUNTIME_FILES = ("server.py", "metadata.json", "scripts/deploy.py")
RUNTIME_DIRS = ("homenettopo", "web")
DEFAULT_PORT = 8765
HEALTH_TIMEOUT_SECONDS = 10


class DeploymentError(RuntimeError):
    """Raised when a deployment operation cannot complete safely."""


def validate_port(value: int | str) -> int:
    """Return a validated TCP port or raise an argparse-compatible error."""

    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def require_supported_host() -> None:
    """Reject deployment outside the product's supported macOS boundary."""

    if platform.system() != "Darwin":
        raise DeploymentError("HomeNetTopo deployment is supported only on macOS.")
    if sys.version_info < (3, 10):
        raise DeploymentError("Python 3.10 or newer is required.")


def canonical_executable(value: str | None) -> str | None:
    """Resolve an optional executable without accepting directories or aliases."""

    if value is None:
        return None
    path = Path(value).expanduser().resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise DeploymentError(f"Executable is unavailable: {path}")
    return str(path)


def validate_source_root(root: Path = SOURCE_ROOT) -> None:
    """Verify that every explicitly deployable runtime path exists."""

    missing = [relative for relative in (*RUNTIME_FILES, *RUNTIME_DIRS) if not (root / relative).exists()]
    if missing:
        raise DeploymentError(f"Runtime source paths are missing: {', '.join(missing)}")


def build_launch_agent(python_path: str, port: int, nmap_path: str | None) -> dict[str, Any]:
    """Build the deterministic user LaunchAgent property list."""

    arguments = [
        python_path,
        str(INSTALL_DIR / "server.py"),
        "--bind",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    if nmap_path:
        arguments.extend(("--nmap-path", nmap_path))
    return {
        "Label": LABEL,
        "ProgramArguments": arguments,
        "WorkingDirectory": str(INSTALL_DIR),
        "RunAtLoad": True,
        # Restart only after an unexpected exit; a normal stop remains stopped.
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 5,
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
        "StandardOutPath": str(LOG_DIR / "service.log"),
        "StandardErrorPath": str(LOG_DIR / "service-error.log"),
    }


def service_domain() -> str:
    """Return the current GUI launchd domain without using elevated privileges."""

    return f"gui/{os.getuid()}"


def service_target() -> str:
    """Return the launchd target used by status and kickstart operations."""

    return f"{service_domain()}/{LABEL}"


def run_launchctl(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run launchctl with captured output and normalized deployment errors."""

    completed = subprocess.run(
        ("/bin/launchctl", *arguments),
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "launchctl failed"
        raise DeploymentError(detail)
    return completed


def bootout_if_loaded() -> None:
    """Remove the current user service when present; absence is not an error."""

    run_launchctl("bootout", service_domain(), str(PLIST_PATH), check=False)


def stage_runtime(root: Path = SOURCE_ROOT) -> Path:
    """Copy the runtime allowlist into a temporary sibling directory."""

    INSTALL_DIR.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".HomeNetTopo-stage-", dir=INSTALL_DIR.parent))
    try:
        for relative in RUNTIME_FILES:
            source = root / relative
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=True)
        for relative in RUNTIME_DIRS:
            shutil.copytree(root / relative, staging / relative, symlinks=False)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return staging


def replace_runtime(staging: Path) -> Path | None:
    """Atomically replace the installed tree while retaining a rollback copy."""

    backup = INSTALL_DIR.with_name(f"{INSTALL_DIR.name}.previous-{os.getpid()}")
    shutil.rmtree(backup, ignore_errors=True)
    previous: Path | None = None
    if INSTALL_DIR.exists():
        INSTALL_DIR.rename(backup)
        previous = backup
    try:
        staging.rename(INSTALL_DIR)
    except Exception:
        if previous and previous.exists():
            previous.rename(INSTALL_DIR)
        raise
    return previous


def restore_runtime(backup: Path | None) -> None:
    """Restore the previous runtime after a failed launchd activation."""

    shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    if backup and backup.exists():
        backup.rename(INSTALL_DIR)


def write_plist(payload: dict[str, Any]) -> None:
    """Write the LaunchAgent plist through an atomic same-directory replace."""

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{LABEL}.", suffix=".plist", dir=PLIST_PATH.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            plistlib.dump(payload, handle, sort_keys=True)
        temporary.chmod(0o600)
        os.replace(temporary, PLIST_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def restore_plist(previous: bytes | None) -> None:
    """Restore or remove the prior plist during deployment rollback."""

    if previous is None:
        PLIST_PATH.unlink(missing_ok=True)
        return
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_bytes(previous)
    PLIST_PATH.chmod(0o600)


def plist_port() -> int:
    """Read the configured port from the installed LaunchAgent arguments."""

    try:
        with PLIST_PATH.open("rb") as handle:
            arguments = plistlib.load(handle)["ProgramArguments"]
        index = arguments.index("--port")
        return validate_port(arguments[index + 1])
    except (OSError, KeyError, ValueError, IndexError, argparse.ArgumentTypeError) as exc:
        raise DeploymentError("The installed LaunchAgent does not contain a valid port.") from exc


def wait_for_health(port: int, timeout_seconds: int = HEALTH_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Wait for the loopback health endpoint after launchd starts the service."""

    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/api/v1/health"
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(url, headers={"Host": f"127.0.0.1:{port}"})
            with urllib.request.urlopen(request, timeout=1) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") == "ok" and payload.get("service") == "homeNetTopo":
                return payload
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise DeploymentError(
        f"Service did not become healthy at {url}. Check {LOG_DIR}. Last error: {last_error}"
    )


def install(port: int, nmap_path: str | None) -> None:
    """Install runtime files, activate launchd, and verify loopback health."""

    require_supported_host()
    validate_source_root()
    python_path = canonical_executable(sys.executable)
    assert python_path is not None
    resolved_nmap = canonical_executable(nmap_path)
    payload = build_launch_agent(python_path, port, resolved_nmap)
    staging = stage_runtime()
    previous_plist = PLIST_PATH.read_bytes() if PLIST_PATH.exists() else None
    backup: Path | None = None
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    bootout_if_loaded()
    try:
        backup = replace_runtime(staging)
        write_plist(payload)
        run_launchctl("bootstrap", service_domain(), str(PLIST_PATH))
        run_launchctl("kickstart", "-k", service_target())
        health = wait_for_health(port)
    except Exception:
        bootout_if_loaded()
        restore_runtime(backup)
        restore_plist(previous_plist)
        if previous_plist is not None and INSTALL_DIR.exists():
            run_launchctl("bootstrap", service_domain(), str(PLIST_PATH), check=False)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    else:
        if backup:
            shutil.rmtree(backup, ignore_errors=True)
        print(f"HomeNetTopo {health.get('version', '')} is running at http://127.0.0.1:{port}")
        print(f"Installed runtime: {INSTALL_DIR}")
        print(f"LaunchAgent: {PLIST_PATH}")
        print(f"Logs: {LOG_DIR}")


def restart() -> None:
    """Restart an existing deployment and verify its health endpoint."""

    require_supported_host()
    if not INSTALL_DIR.is_dir() or not PLIST_PATH.is_file():
        raise DeploymentError("HomeNetTopo is not installed. Run the install command first.")
    port = plist_port()
    bootout_if_loaded()
    run_launchctl("bootstrap", service_domain(), str(PLIST_PATH))
    run_launchctl("kickstart", "-k", service_target())
    wait_for_health(port)
    print(f"HomeNetTopo restarted at http://127.0.0.1:{port}")


def status() -> None:
    """Print launchd state and probe the configured loopback health endpoint."""

    require_supported_host()
    completed = run_launchctl("print", service_target(), check=False)
    if completed.returncode != 0:
        raise DeploymentError("HomeNetTopo is not loaded in the current user launchd domain.")
    print(completed.stdout.rstrip())
    health = wait_for_health(plist_port(), timeout_seconds=2)
    print(json.dumps(health, indent=2, sort_keys=True))


def uninstall(purge_logs: bool) -> None:
    """Remove the user LaunchAgent and deployed runtime without using sudo."""

    require_supported_host()
    bootout_if_loaded()
    PLIST_PATH.unlink(missing_ok=True)
    shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    if purge_logs:
        shutil.rmtree(LOG_DIR, ignore_errors=True)
    print("HomeNetTopo was removed from the current user account.")
    if not purge_logs and LOG_DIR.exists():
        print(f"Logs were retained at {LOG_DIR}; pass --purge-logs to remove them.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse deployment actions without accepting arbitrary commands or paths."""

    parser = argparse.ArgumentParser(description="Deploy HomeNetTopo as a per-user macOS LaunchAgent.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    install_parser = subparsers.add_parser("install", help="Install or update the current user deployment.")
    install_parser.add_argument("--port", type=validate_port, default=DEFAULT_PORT)
    install_parser.add_argument("--nmap-path", help="Optional explicit Nmap executable path.")

    subparsers.add_parser("restart", help="Restart the installed service.")
    subparsers.add_parser("status", help="Show launchd state and the health response.")

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove the current user deployment.")
    uninstall_parser.add_argument("--purge-logs", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one deployment action and convert failures into a concise CLI error."""

    args = parse_args(argv)
    try:
        if args.action == "install":
            install(args.port, args.nmap_path)
        elif args.action == "restart":
            restart()
        elif args.action == "status":
            status()
        else:
            uninstall(args.purge_logs)
    except (DeploymentError, OSError, subprocess.SubprocessError) as exc:
        print(f"deployment failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
