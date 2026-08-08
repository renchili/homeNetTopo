#!/usr/bin/env python3
"""Deploy HomeNetTopo and its current-user macOS Wi-Fi identity helper.

The Python service remains a loopback-only per-user LaunchAgent. Installation
also builds a small native CoreLocation/CoreWLAN app, ad-hoc signs it, installs
it under ``~/Applications``, and opens it so the user can grant Location access
required by modern macOS for SSID/BSSID. No administrator privilege is used.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import plistlib
import re
import shutil
import stat
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
NATIVE_CACHE_DIR = Path.home() / "Library" / "Caches" / "HomeNetTopo"
USER_APPLICATIONS_DIR = Path.home() / "Applications"
NATIVE_APP_NAME = "HomeNetTopo Wi-Fi.app"
NATIVE_APP_PATH = USER_APPLICATIONS_DIR / NATIVE_APP_NAME
NATIVE_APP_BUNDLE_ID = "com.homenettopo.wifi"
NATIVE_PROJECT = SOURCE_ROOT / "macos" / "HomeNetTopoApp" / "HomeNetTopoApp.xcodeproj"
NATIVE_TARGET = "HomeNetTopoApp"
NATIVE_BUILD_LOG = LOG_DIR / "native-build.log"
XCODEBUILD_PATH = "/usr/bin/xcodebuild"
CODESIGN_PATH = "/usr/bin/codesign"
OPEN_PATH = "/usr/bin/open"
NATIVE_BUILD_TIMEOUT_SECONDS = 120
NATIVE_UNREGISTER_TIMEOUT_SECONDS = 10
RUNTIME_FILES = (
    "server.py",
    "metadata.json",
    "scripts/deploy.py",
    "homenettopo/__init__.py",
    "homenettopo/commands.py",
    "homenettopo/discovery.py",
    "homenettopo/interfaces.py",
    "homenettopo/models.py",
    "homenettopo/neighbors.py",
    "homenettopo/routes.py",
    "homenettopo/topology.py",
    "web/index.html",
    "web/app.js",
    "web/core.mjs",
    "web/styles.css",
)
NATIVE_SOURCE_FILES = (
    "macos/HomeNetTopoApp/HomeNetTopoApp.swift",
    "macos/HomeNetTopoApp/AppDelegate.swift",
    "macos/HomeNetTopoApp/WiFiCollector.swift",
    "macos/HomeNetTopoApp/Info.plist",
    "macos/HomeNetTopoApp/HomeNetTopoApp.xcodeproj/project.pbxproj",
)
DEFAULT_PORT = 8765
HEALTH_TIMEOUT_SECONDS = 10
MAX_HEALTH_BYTES = 4096
MAX_DIAGNOSTIC_BYTES = 8192
PLUTIL_PATH = "/usr/bin/plutil"
_MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")
_INTERFACE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


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


def validate_mac(value: str) -> str:
    """Return one canonical locally configured BSSID."""

    normalized = value.strip().lower().replace("-", ":")
    if not _MAC_RE.fullmatch(normalized):
        raise argparse.ArgumentTypeError("Wi-Fi BSSID must be a canonical MAC address")
    return normalized


def validate_interface(value: str) -> str:
    """Return one safe BSD interface name."""

    cleaned = value.strip()
    if not _INTERFACE_RE.fullmatch(cleaned):
        raise argparse.ArgumentTypeError("Wi-Fi interface name is invalid")
    return cleaned


def validate_ssid(value: str) -> str:
    """Return a nonempty SSID within the IEEE 802.11 byte limit."""

    cleaned = value.strip()
    if not cleaned or len(cleaned.encode("utf-8")) > 32:
        raise argparse.ArgumentTypeError("Wi-Fi SSID must be 1 to 32 UTF-8 bytes")
    return cleaned


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


def _validate_regular_sources(root: Path, relatives: Sequence[str], label: str) -> None:
    """Require a fixed source manifest of contained regular non-symlink files."""

    root = root.resolve()
    missing: list[str] = []
    for relative in relatives:
        source = root / relative
        if source.is_symlink():
            raise DeploymentError(f"{label} source contains a symbolic link: {relative}")
        if not source.exists():
            missing.append(relative)
            continue
        if not source.is_file():
            raise DeploymentError(f"{label} source is not a regular file: {relative}")
        try:
            source.resolve().relative_to(root)
        except ValueError as exc:
            raise DeploymentError(f"{label} source escapes the repository: {source}") from exc
    if missing:
        raise DeploymentError(f"{label} source paths are missing: {', '.join(missing)}")


def validate_source_root(root: Path = SOURCE_ROOT) -> None:
    """Verify every deployable Python/web runtime file is safe and present."""

    _validate_regular_sources(root, RUNTIME_FILES, "Runtime")


def validate_native_source_root(root: Path = SOURCE_ROOT) -> None:
    """Verify the explicitly approved native helper source manifest."""

    _validate_regular_sources(root, NATIVE_SOURCE_FILES, "Native helper")


def build_launch_agent(
    python_path: str,
    port: int,
    nmap_path: str | None,
    *,
    wifi_interface: str | None = None,
    wifi_bssid: str | None = None,
    wifi_ssid: str | None = None,
    wifi_role: str | None = None,
) -> dict[str, Any]:
    """Build the deterministic Python user LaunchAgent property list."""

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
    if wifi_interface:
        arguments.extend(("--wifi-interface", wifi_interface))
    if wifi_bssid:
        arguments.extend(("--wifi-bssid", wifi_bssid))
    if wifi_ssid:
        arguments.extend(("--wifi-ssid", wifi_ssid))
    if wifi_role:
        arguments.extend(("--wifi-role", wifi_role))
    return {
        "Label": LABEL,
        "ProgramArguments": arguments,
        "WorkingDirectory": str(INSTALL_DIR),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 5,
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
        "StandardOutPath": str(LOG_DIR / "service.log"),
        "StandardErrorPath": str(LOG_DIR / "service-error.log"),
    }


def service_domain() -> str:
    """Return the current GUI launchd domain without elevated privileges."""

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


def bootout_if_loaded(*, check: bool = True) -> bool:
    """Stop the loaded Python service; absence is safe, shutdown failure is not."""

    loaded = run_launchctl("print", service_target(), check=False)
    if loaded.returncode != 0:
        return False
    stopped = run_launchctl("bootout", service_target(), check=check)
    return stopped.returncode == 0


def stage_runtime(root: Path = SOURCE_ROOT) -> Path:
    """Copy and revalidate the exact runtime files in a temporary sibling tree."""

    validate_source_root(root)
    INSTALL_DIR.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".HomeNetTopo-stage-", dir=INSTALL_DIR.parent))
    try:
        for relative in RUNTIME_FILES:
            source = root / relative
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
        validate_source_root(staging)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return staging


def replace_runtime(staging: Path) -> Path | None:
    """Atomically replace the installed runtime while retaining rollback data."""

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
    """Restore the previous Python/web runtime after a deployment failure."""

    shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    if backup and backup.exists():
        backup.rename(INSTALL_DIR)


def _require_system_executable(path: str, label: str) -> None:
    """Require one fixed Apple development/deployment executable."""

    candidate = Path(path)
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise DeploymentError(f"{label} is unavailable: {path}")


def _run_native_build(argv: Sequence[str]) -> None:
    """Run one fixed native build command with a total timeout and local log."""

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    NATIVE_BUILD_LOG.write_text("", encoding="utf-8")
    NATIVE_BUILD_LOG.chmod(0o600)
    try:
        with NATIVE_BUILD_LOG.open("a", encoding="utf-8") as log:
            completed = subprocess.run(
                tuple(argv),
                check=False,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=NATIVE_BUILD_TIMEOUT_SECONDS,
            )
    except subprocess.TimeoutExpired as exc:
        raise DeploymentError(f"Native Wi-Fi helper build timed out. Check {NATIVE_BUILD_LOG}.") from exc
    if completed.returncode != 0:
        raise DeploymentError(f"Native Wi-Fi helper build failed. Check {NATIVE_BUILD_LOG}.")


def _validate_built_native_app(path: Path) -> None:
    """Require the expected bundle identity, privacy keys, and executable."""

    plist_path = path / "Contents" / "Info.plist"
    if path.is_symlink() or not path.is_dir() or not plist_path.is_file() or plist_path.is_symlink():
        raise DeploymentError("Native Wi-Fi helper build did not produce a valid application bundle.")
    try:
        with plist_path.open("rb") as handle:
            payload = plistlib.load(handle)
        executable_name = payload["CFBundleExecutable"]
        bundle_id = payload["CFBundleIdentifier"]
    except (OSError, KeyError, TypeError, plistlib.InvalidFileException) as exc:
        raise DeploymentError("Native Wi-Fi helper Info.plist is invalid.") from exc
    executable = path / "Contents" / "MacOS" / executable_name
    if bundle_id != NATIVE_APP_BUNDLE_ID:
        raise DeploymentError("Native Wi-Fi helper bundle identifier is unexpected.")
    if not payload.get("NSLocationUsageDescription") or not payload.get("NSLocationWhenInUseUsageDescription"):
        raise DeploymentError("Native Wi-Fi helper is missing Location privacy descriptions.")
    if executable.is_symlink() or not executable.is_file() or not os.access(executable, os.X_OK):
        raise DeploymentError("Native Wi-Fi helper executable is unavailable after build.")


def build_native_app(root: Path = SOURCE_ROOT) -> tuple[Path, Path]:
    """Build and ad-hoc sign the approved native CoreWLAN helper sources."""

    validate_native_source_root(root)
    _require_system_executable(XCODEBUILD_PATH, "Xcode command-line build tool")
    _require_system_executable(CODESIGN_PATH, "macOS code signing tool")
    build_root = Path(tempfile.mkdtemp(prefix=".HomeNetTopo-native-build-"))
    try:
        project = root / "macos" / "HomeNetTopoApp" / "HomeNetTopoApp.xcodeproj"
        _run_native_build((
            XCODEBUILD_PATH,
            "-quiet",
            "-project",
            str(project),
            "-target",
            NATIVE_TARGET,
            "-configuration",
            "Release",
            f"SYMROOT={build_root / 'Build'}",
            f"OBJROOT={build_root / 'Obj'}",
            "CODE_SIGNING_ALLOWED=NO",
            "CODE_SIGNING_REQUIRED=NO",
        ))
        app = build_root / "Build" / "Release" / NATIVE_APP_NAME
        _validate_built_native_app(app)
        signed = subprocess.run(
            (CODESIGN_PATH, "--force", "--deep", "--sign", "-", "--timestamp=none", str(app)),
            check=False,
            capture_output=True,
            text=True,
        )
        if signed.returncode != 0:
            raise DeploymentError("Could not ad-hoc sign the native Wi-Fi helper.")
        verified = subprocess.run(
            (CODESIGN_PATH, "--verify", "--deep", "--strict", str(app)),
            check=False,
            capture_output=True,
            text=True,
        )
        if verified.returncode != 0:
            raise DeploymentError("Native Wi-Fi helper signature verification failed.")
        return build_root, app
    except Exception:
        shutil.rmtree(build_root, ignore_errors=True)
        raise


def replace_native_app(built_app: Path) -> Path | None:
    """Atomically install the built helper under the current user's Applications."""

    _validate_built_native_app(built_app)
    USER_APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=".HomeNetTopo-WiFi-stage-", dir=USER_APPLICATIONS_DIR))
    staged_app = staging_root / NATIVE_APP_NAME
    backup = NATIVE_APP_PATH.with_name(f"{NATIVE_APP_NAME}.previous-{os.getpid()}")
    shutil.rmtree(backup, ignore_errors=True)
    previous: Path | None = None
    try:
        shutil.copytree(built_app, staged_app, symlinks=True)
        _validate_built_native_app(staged_app)
        if NATIVE_APP_PATH.exists():
            NATIVE_APP_PATH.rename(backup)
            previous = backup
        staged_app.rename(NATIVE_APP_PATH)
        return previous
    except Exception:
        if previous and previous.exists() and not NATIVE_APP_PATH.exists():
            previous.rename(NATIVE_APP_PATH)
        raise
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def restore_native_app(backup: Path | None) -> None:
    """Restore the previous native helper after a later deployment failure."""

    shutil.rmtree(NATIVE_APP_PATH, ignore_errors=True)
    if backup and backup.exists():
        backup.rename(NATIVE_APP_PATH)


def open_native_helper() -> None:
    """Open the installed helper in the GUI so Location authorization can prompt."""

    _require_system_executable(OPEN_PATH, "macOS open tool")
    if not NATIVE_APP_PATH.is_dir():
        raise DeploymentError("Native Wi-Fi helper is not installed.")
    completed = subprocess.run(
        (OPEN_PATH, str(NATIVE_APP_PATH)),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        raise DeploymentError("Could not open the native Wi-Fi helper for Location authorization.")


def unregister_native_login_item() -> None:
    """Ask the installed helper to unregister its own SMAppService login item."""

    if not NATIVE_APP_PATH.is_dir() or not Path(OPEN_PATH).is_file():
        return
    try:
        subprocess.run(
            (OPEN_PATH, "-W", "-n", str(NATIVE_APP_PATH), "--args", "--unregister-login-item"),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=NATIVE_UNREGISTER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        pass


def write_plist(payload: dict[str, Any]) -> None:
    """Write the Python LaunchAgent plist through an atomic same-directory replace."""

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
    """Read the configured port from the installed Python LaunchAgent arguments."""

    try:
        with PLIST_PATH.open("rb") as handle:
            arguments = plistlib.load(handle)["ProgramArguments"]
        index = arguments.index("--port")
        return validate_port(arguments[index + 1])
    except (OSError, KeyError, ValueError, IndexError, argparse.ArgumentTypeError) as exc:
        raise DeploymentError("The installed LaunchAgent does not contain a valid port.") from exc


def _run_plutil() -> subprocess.CompletedProcess[str]:
    """Validate the installed plist with the macOS property-list parser."""

    return subprocess.run(
        (PLUTIL_PATH, "-lint", str(PLIST_PATH)),
        check=False,
        capture_output=True,
        text=True,
    )


def validate_launch_agent() -> None:
    """Reject a plist or referenced runtime that launchd cannot safely load."""

    if PLIST_PATH.is_symlink() or not PLIST_PATH.is_file():
        raise DeploymentError(f"LaunchAgent plist is missing or not a regular file: {PLIST_PATH}")
    plist_stat = PLIST_PATH.stat()
    if plist_stat.st_uid != os.getuid():
        raise DeploymentError("LaunchAgent plist is not owned by the current user.")
    if stat.S_IMODE(plist_stat.st_mode) & 0o022:
        raise DeploymentError("LaunchAgent plist must not be writable by group or other users.")

    lint = _run_plutil()
    if lint.returncode != 0:
        detail = lint.stderr.strip() or lint.stdout.strip() or "plutil rejected the plist"
        raise DeploymentError(f"LaunchAgent plist validation failed: {detail}")

    try:
        with PLIST_PATH.open("rb") as handle:
            payload = plistlib.load(handle)
        arguments = payload["ProgramArguments"]
        python_path = Path(arguments[0])
        server_path = Path(arguments[1])
        working_directory = Path(payload["WorkingDirectory"])
        stdout_parent = Path(payload["StandardOutPath"]).parent
        stderr_parent = Path(payload["StandardErrorPath"]).parent
    except (OSError, KeyError, IndexError, TypeError, plistlib.InvalidFileException) as exc:
        raise DeploymentError("LaunchAgent plist is missing required runtime fields.") from exc

    if payload.get("Label") != LABEL:
        raise DeploymentError("LaunchAgent label does not match the deployment label.")
    if not python_path.is_file() or not os.access(python_path, os.X_OK):
        raise DeploymentError(f"LaunchAgent Python executable is unavailable: {python_path}")
    if server_path.is_symlink() or not server_path.is_file():
        raise DeploymentError(f"LaunchAgent server entrypoint is unavailable: {server_path}")
    if not working_directory.is_dir():
        raise DeploymentError(f"LaunchAgent working directory is unavailable: {working_directory}")
    if not stdout_parent.is_dir() or not stderr_parent.is_dir():
        raise DeploymentError(f"LaunchAgent log directory is unavailable: {LOG_DIR}")


def _tail(path: Path) -> str:
    """Return a bounded UTF-8 tail suitable for local deployment diagnostics."""

    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - MAX_DIAGNOSTIC_BYTES))
            return handle.read(MAX_DIAGNOSTIC_BYTES).decode("utf-8", errors="replace").strip()
    except OSError as exc:
        return f"unavailable: {exc}"


def launchd_diagnostics() -> str:
    """Collect bounded non-privileged deployment diagnostics without Wi-Fi data."""

    lines = [
        "LaunchAgent diagnostics:",
        f"  domain: {service_domain()}",
        f"  target: {service_target()}",
        f"  plist: {PLIST_PATH}",
        f"  runtime: {INSTALL_DIR}",
        f"  native-app: {NATIVE_APP_PATH}",
        f"  python: {sys.executable}",
    ]
    lint = _run_plutil() if PLIST_PATH.exists() else None
    if lint is None:
        lines.append("  plutil: plist is absent")
    else:
        lint_detail = lint.stdout.strip() or lint.stderr.strip() or f"exit {lint.returncode}"
        lines.append(f"  plutil: {lint_detail}")
    disabled = run_launchctl("print-disabled", service_domain(), check=False)
    disabled_detail = disabled.stdout.strip() or disabled.stderr.strip() or f"exit {disabled.returncode}"
    lines.append(f"  print-disabled: {disabled_detail[:MAX_DIAGNOSTIC_BYTES]}")
    current = run_launchctl("print", service_target(), check=False)
    current_detail = current.stdout.strip() or current.stderr.strip() or f"exit {current.returncode}"
    lines.append(f"  service-state: {current_detail[:MAX_DIAGNOSTIC_BYTES]}")
    lines.append(f"  service-error.log: {_tail(LOG_DIR / 'service-error.log')}")
    lines.append(f"  service.log: {_tail(LOG_DIR / 'service.log')}")
    lines.append(f"  native-build.log: {_tail(NATIVE_BUILD_LOG)}")
    return "\n".join(lines)


def bootstrap_agent() -> None:
    """Enable, clean stale registration, validate, and bootstrap the user agent."""

    validate_launch_agent()
    enabled = run_launchctl("enable", service_target(), check=False)
    if enabled.returncode != 0:
        detail = enabled.stderr.strip() or enabled.stdout.strip() or "launchctl enable failed"
        raise DeploymentError(f"Could not enable the current-user LaunchAgent: {detail}\n{launchd_diagnostics()}")
    run_launchctl("bootout", service_domain(), str(PLIST_PATH), check=False)
    loaded = run_launchctl("bootstrap", service_domain(), str(PLIST_PATH), check=False)
    if loaded.returncode != 0:
        detail = loaded.stderr.strip() or loaded.stdout.strip() or "launchctl bootstrap failed"
        raise DeploymentError(
            f"LaunchAgent bootstrap failed: {detail}\n"
            "Do not rerun as root; this is a current-user LaunchAgent.\n"
            f"{launchd_diagnostics()}"
        )


def wait_for_health(port: int, timeout_seconds: int = HEALTH_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Wait for the loopback health endpoint without using environment proxies."""

    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/api/v1/health"
    last_error: Exception | None = None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(url, headers={"Host": f"127.0.0.1:{port}"})
            with opener.open(request, timeout=1) as response:
                body = response.read(MAX_HEALTH_BYTES + 1)
            if len(body) > MAX_HEALTH_BYTES:
                raise ValueError("health response exceeded the configured limit")
            payload = json.loads(body.decode("utf-8"))
            if payload.get("status") == "ok" and payload.get("service") == "homeNetTopo":
                return payload
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise DeploymentError(
        f"Service did not become healthy at {url}. Check {LOG_DIR}. Last error: {last_error}\n"
        f"{launchd_diagnostics()}"
    )


def install(
    port: int,
    nmap_path: str | None,
    *,
    wifi_interface: str | None = None,
    wifi_bssid: str | None = None,
    wifi_ssid: str | None = None,
    wifi_role: str | None = None,
) -> None:
    """Build helper, install runtime, activate launchd, and open authorization UI."""

    require_supported_host()
    if any((wifi_bssid, wifi_ssid, wifi_role)) and not wifi_interface:
        raise DeploymentError("--wifi-interface is required with Wi-Fi fallback values")
    python_path = canonical_executable(sys.executable)
    assert python_path is not None
    resolved_nmap = canonical_executable(nmap_path)
    payload = build_launch_agent(
        python_path,
        port,
        resolved_nmap,
        wifi_interface=wifi_interface,
        wifi_bssid=wifi_bssid,
        wifi_ssid=wifi_ssid,
        wifi_role=wifi_role,
    )

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    build_root, built_app = build_native_app()
    staging = stage_runtime()
    previous_plist = PLIST_PATH.read_bytes() if PLIST_PATH.exists() else None
    runtime_backup: Path | None = None
    native_backup: Path | None = None
    runtime_replaced = False
    native_replaced = False

    try:
        bootout_if_loaded()
        runtime_backup = replace_runtime(staging)
        runtime_replaced = True
        native_backup = replace_native_app(built_app)
        native_replaced = True
        write_plist(payload)
        bootstrap_agent()
        run_launchctl("kickstart", "-k", service_target())
        health = wait_for_health(port)
        open_native_helper()
    except Exception:
        bootout_if_loaded(check=False)
        run_launchctl("bootout", service_domain(), str(PLIST_PATH), check=False)
        if runtime_replaced:
            restore_runtime(runtime_backup)
        if native_replaced:
            restore_native_app(native_backup)
        restore_plist(previous_plist)
        if previous_plist is not None and INSTALL_DIR.exists():
            run_launchctl("enable", service_target(), check=False)
            restored = run_launchctl("bootstrap", service_domain(), str(PLIST_PATH), check=False)
            if restored.returncode == 0:
                run_launchctl("kickstart", "-k", service_target(), check=False)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    else:
        if runtime_backup:
            shutil.rmtree(runtime_backup, ignore_errors=True)
        if native_backup:
            shutil.rmtree(native_backup, ignore_errors=True)
        print(f"HomeNetTopo {health.get('version', '')} is running at http://127.0.0.1:{port}")
        print(f"Installed runtime: {INSTALL_DIR}")
        print(f"Wi-Fi identity helper: {NATIVE_APP_PATH}")
        print("Grant Location access in the opened helper, then refresh the topology page.")
    finally:
        shutil.rmtree(build_root, ignore_errors=True)


def restart() -> None:
    """Restart an existing Python deployment and verify its health endpoint."""

    require_supported_host()
    if not INSTALL_DIR.is_dir() or not PLIST_PATH.is_file():
        raise DeploymentError("HomeNetTopo is not installed. Run the install command first.")
    port = plist_port()
    bootout_if_loaded()
    bootstrap_agent()
    run_launchctl("kickstart", "-k", service_target())
    wait_for_health(port)
    print(f"HomeNetTopo restarted at http://127.0.0.1:{port}")


def status() -> None:
    """Print launchd state and probe the configured loopback health endpoint."""

    require_supported_host()
    completed = run_launchctl("print", service_target(), check=False)
    if completed.returncode != 0:
        raise DeploymentError(
            "HomeNetTopo is not loaded in the current user launchd domain.\n"
            f"{launchd_diagnostics()}"
        )
    print(completed.stdout.rstrip())
    health = wait_for_health(plist_port(), timeout_seconds=2)
    print(json.dumps(health, indent=2, sort_keys=True))
    print(f"Native Wi-Fi helper installed: {NATIVE_APP_PATH.is_dir()}")


def diagnose() -> None:
    """Print bounded launchd, native-build, path, and service-log diagnostics."""

    require_supported_host()
    print(launchd_diagnostics())


def uninstall(purge_logs: bool) -> None:
    """Remove the current-user service, native helper, runtime, and helper cache."""

    require_supported_host()
    bootout_if_loaded()
    run_launchctl("bootout", service_domain(), str(PLIST_PATH), check=False)
    unregister_native_login_item()
    PLIST_PATH.unlink(missing_ok=True)
    shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    shutil.rmtree(NATIVE_APP_PATH, ignore_errors=True)
    shutil.rmtree(NATIVE_CACHE_DIR, ignore_errors=True)
    if purge_logs:
        shutil.rmtree(LOG_DIR, ignore_errors=True)
    print("HomeNetTopo was removed from the current user account.")
    if not purge_logs and LOG_DIR.exists():
        print(f"Logs were retained at {LOG_DIR}; pass --purge-logs to remove them.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse deployment actions without accepting arbitrary commands or paths."""

    parser = argparse.ArgumentParser(description="Deploy HomeNetTopo as a per-user macOS application and service.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    install_parser = subparsers.add_parser("install", help="Build and install/update the current user deployment.")
    install_parser.add_argument("--port", type=validate_port, default=DEFAULT_PORT)
    install_parser.add_argument("--nmap-path", help="Optional explicit Nmap executable path.")
    install_parser.add_argument("--wifi-interface", type=validate_interface, help="BSD Wi-Fi interface for a last-resort local fallback, for example en0.")
    install_parser.add_argument("--wifi-bssid", type=validate_mac, help="Fallback BSSID used only if native and profiler collection omit it.")
    install_parser.add_argument("--wifi-ssid", type=validate_ssid, help="Optional fallback SSID stored only in the local LaunchAgent plist.")
    install_parser.add_argument("--wifi-role", choices=("access-point", "relay"), help="Optional user-confirmed role of the connected Wi-Fi node.")
    subparsers.add_parser("restart", help="Restart the installed Python service.")
    subparsers.add_parser("status", help="Show launchd state, helper installation, and health response.")
    subparsers.add_parser("diagnose", help="Show bounded deployment diagnostics.")
    uninstall_parser = subparsers.add_parser("uninstall", help="Remove the current user deployment.")
    uninstall_parser.add_argument("--purge-logs", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one deployment action and convert failures into a concise CLI error."""

    args = parse_args(argv)
    try:
        if args.action == "install":
            install(
                args.port,
                args.nmap_path,
                wifi_interface=args.wifi_interface,
                wifi_bssid=args.wifi_bssid,
                wifi_ssid=args.wifi_ssid,
                wifi_role=args.wifi_role,
            )
        elif args.action == "restart":
            restart()
        elif args.action == "status":
            status()
        elif args.action == "diagnose":
            diagnose()
        else:
            uninstall(args.purge_logs)
    except (DeploymentError, OSError, subprocess.SubprocessError) as exc:
        print(f"deployment failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
