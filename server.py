#!/usr/bin/env python3
"""Serve HomeNetTopo on IPv4 loopback and own snapshot publication.

The handler exposes read-only state plus two protected collection POST routes.
Fixed command evidence is supplemented by a short-lived, Location-authorized
CoreWLAN cache published by the native macOS helper. A snapshot is published
only after a complete passive or active operation produces a validated model.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import stat
import threading
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from homenettopo import __version__
from homenettopo.commands import (
    CommandError,
    interfaces_spec,
    neighbors_spec,
    nmap_spec,
    resolve_nmap,
    routes_spec,
    run_command,
    wifi_interfaces_spec,
    wifi_spec,
)
from homenettopo.discovery import (
    MAX_BODY_BYTES,
    ValidationError,
    parse_nmap_xml,
    validate_active_hosts,
    validate_phase_a,
    validate_phase_b,
)
from homenettopo.interfaces import (
    InterfaceFact,
    WirelessAttachmentFact,
    merge_wireless_facts,
    parse_airport_json,
    parse_ifconfig,
    parse_native_wifi_json,
    parse_wifi_hardware_ports,
)
from homenettopo.models import ActiveDiscoveryMetadata, SourceStatus, SourceStatusValue, WarningItem
from homenettopo.neighbors import NeighborFact, parse_neighbors
from homenettopo.routes import RouteFact, parse_routes
from homenettopo.topology import build_snapshot

BIND_ADDRESS = "127.0.0.1"
DEFAULT_PORT = 8765
WEB_ROOT = Path(__file__).resolve().parent / "web"
NATIVE_WIFI_CACHE_PATH = Path.home() / "Library" / "Caches" / "HomeNetTopo" / "wifi-current.json"
NATIVE_WIFI_MAX_BYTES = 16 * 1024
NATIVE_WIFI_MAX_AGE_SECONDS = 20
NATIVE_WIFI_FUTURE_SKEW_SECONDS = 5
NATIVE_WIFI_LAUNCH_URL = "homenettopo-wifi://authorize"
STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/core.mjs": "core.mjs",
    "/styles.css": "styles.css",
}
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}
_MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")
_INTERFACE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class ApiError(RuntimeError):
    """HTTP-facing normalized error returned by the local API."""

    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class PassiveParts:
    """Fresh passive evidence plus source status and normalized failures."""

    interfaces: tuple[InterfaceFact, ...]
    routes: tuple[RouteFact, ...]
    neighbors: tuple[NeighborFact, ...]
    wireless_attachments: tuple[WirelessAttachmentFact, ...]
    sources: tuple[SourceStatus, ...]
    warnings: tuple[WarningItem, ...]
    failures: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class NativeWiFiCacheState:
    """Public-safe native-helper state plus an optional fresh association fact."""

    status: str
    message: str
    fact: WirelessAttachmentFact | None = None


def canonical_mac_argument(value: str) -> str:
    """Validate a locally configured BSSID without accepting loose notation."""

    normalized = value.strip().lower().replace("-", ":")
    if not _MAC_RE.fullmatch(normalized):
        raise argparse.ArgumentTypeError("Wi-Fi BSSID must be a canonical MAC address")
    return normalized


def interface_argument(value: str) -> str:
    """Validate a BSD interface name supplied through local configuration."""

    cleaned = value.strip()
    if not _INTERFACE_RE.fullmatch(cleaned):
        raise argparse.ArgumentTypeError("Wi-Fi interface name is invalid")
    return cleaned


def ssid_argument(value: str) -> str:
    """Validate a nonempty SSID without logging or persisting it in the repo."""

    cleaned = value.strip()
    if not cleaned or len(cleaned.encode("utf-8")) > 32:
        raise argparse.ArgumentTypeError("Wi-Fi SSID must be 1 to 32 UTF-8 bytes")
    return cleaned


def _native_state(status: str) -> NativeWiFiCacheState:
    """Return one normalized helper state without exposing local Wi-Fi values."""

    messages = {
        "ready": "Location-authorized CoreWLAN helper supplied fresh Wi-Fi identity.",
        "missing": "Open HomeNetTopo Wi-Fi and grant Location access to identify the current Wi-Fi radio.",
        "stale": "HomeNetTopo Wi-Fi helper data is stale; open or restart the helper.",
        "not_determined": "HomeNetTopo Wi-Fi still needs Location permission to read SSID and BSSID.",
        "denied": "Location access is denied for HomeNetTopo Wi-Fi; enable it in System Settings.",
        "restricted": "Location access for HomeNetTopo Wi-Fi is restricted by macOS.",
        "no_association": "The native helper is running, but no current Wi-Fi association is available.",
        "invalid": "HomeNetTopo Wi-Fi helper data is invalid and was ignored.",
        "unsupported": "Native Wi-Fi identity is available only on macOS.",
    }
    return NativeWiFiCacheState(status, messages[status])


def read_native_wifi_cache(
    path: Path = NATIVE_WIFI_CACHE_PATH,
    *,
    now: datetime | None = None,
) -> NativeWiFiCacheState:
    """Read a bounded, owned, fresh native CoreWLAN cache without executing code."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return _native_state("missing")
    except OSError:
        return _native_state("invalid")

    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        return _native_state("invalid")
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o022:
        return _native_state("invalid")
    if metadata.st_size <= 0 or metadata.st_size > NATIVE_WIFI_MAX_BYTES:
        return _native_state("invalid")

    try:
        text = path.read_bytes().decode("utf-8")
        evidence = parse_native_wifi_json(text)
        collected = datetime.fromisoformat(evidence.collected_at[:-1] + "+00:00")
    except (OSError, UnicodeError, ValueError):
        return _native_state("invalid")
    if collected.utcoffset() is None:
        return _native_state("invalid")

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = (current - collected.astimezone(timezone.utc)).total_seconds()
    if age < -NATIVE_WIFI_FUTURE_SKEW_SECONDS or age > NATIVE_WIFI_MAX_AGE_SECONDS:
        return _native_state("stale")
    if evidence.authorization != "authorized":
        return _native_state(evidence.authorization if evidence.authorization in {"not_determined", "denied", "restricted"} else "invalid")
    if evidence.fact is None:
        return _native_state("no_association")
    ready = _native_state("ready")
    return NativeWiFiCacheState(ready.status, ready.message, evidence.fact)


class AppState:
    """Own collection coordination and the latest immutable snapshot."""

    def __init__(
        self,
        *,
        port: int,
        nmap_path: str | None,
        wifi_override: WirelessAttachmentFact | None = None,
        native_wifi_cache_path: Path = NATIVE_WIFI_CACHE_PATH,
    ) -> None:
        self.port = port
        self.nmap_path = nmap_path
        self.wifi_override = wifi_override
        self.native_wifi_cache_path = native_wifi_cache_path
        self.snapshot = None
        self.collection_lock = threading.Lock()

    @property
    def supported(self) -> bool:
        """Return whether command collection is supported on this host."""

        return platform.system().lower() == "darwin"

    def native_wifi_state(self) -> NativeWiFiCacheState:
        """Return current helper state without starting a command or collection."""

        if not self.supported:
            return _native_state("unsupported")
        return read_native_wifi_cache(self.native_wifi_cache_path)

    def collect_passive_parts(self) -> PassiveParts:
        """Collect fixed evidence and merge the preferred native Wi-Fi identity.

        Independent command collectors run concurrently. The native cache is read
        after material coherence is established and never extends command latency.
        Fresh CoreWLAN evidence wins over profiler identity; profiler evidence wins
        over optional local configuration.
        """

        if not self.supported:
            raise ApiError(501, "unsupported_platform", "Collection is supported only on macOS.")

        values: dict[str, Any] = {}
        sources: list[SourceStatus] = []
        warnings: list[WarningItem] = []
        failures: list[tuple[str, str]] = []
        collectors: tuple[tuple[str, Any, Callable[[str], Any]], ...] = (
            ("interfaces", interfaces_spec(), parse_ifconfig),
            ("routes", routes_spec(), parse_routes),
            ("neighbors", neighbors_spec(), parse_neighbors),
            ("wifi_interfaces", wifi_interfaces_spec(), parse_wifi_hardware_ports),
            ("wifi", wifi_spec(), parse_airport_json),
        )

        with ThreadPoolExecutor(max_workers=len(collectors), thread_name_prefix="homenettopo-passive") as executor:
            futures = {name: executor.submit(run_command, spec) for name, spec, _ in collectors}
            for name, _, parser in collectors:
                try:
                    result = futures[name].result()
                    parsed = parser(result.stdout)
                    if name == "interfaces" and not parsed:
                        raise ValueError("No interface facts were parsed.")
                    values[name] = parsed
                except CommandError as exc:
                    failures.append((name, exc.code))
                    sources.append(SourceStatus(name, SourceStatusValue.FAILED, "Collection command failed."))
                    warnings.append(WarningItem(f"{name}_collection_failed", f"{name.replace('_', ' ').title()} evidence could not be collected.", name))
                except (ValueError, UnicodeError):
                    failures.append((name, "collection_failed"))
                    sources.append(SourceStatus(name, SourceStatusValue.FAILED, "Collected output could not be parsed."))
                    warnings.append(WarningItem(f"{name}_parse_failed", f"{name.replace('_', ' ').title()} evidence could not be parsed.", name))
                else:
                    sources.append(SourceStatus(name, SourceStatusValue.OK, duration_ms=result.duration_ms))

        material_names = ("interfaces", "routes", "neighbors")
        if not any(values.get(name) for name in material_names):
            material_failures = [(name, code) for name, code in failures if name in material_names]
            timeout_sources = sorted(name for name, code in material_failures if code == "command_timeout")
            details = {
                "failed_sources": sorted(name for name, _ in material_failures),
                "timeout_sources": timeout_sources,
            }
            if timeout_sources:
                joined = ", ".join(timeout_sources)
                raise ApiError(504, "command_timeout", f"Passive collection timed out in: {joined}.", details)
            raise ApiError(500, "collection_failed", "No coherent passive snapshot could be produced.", details)

        native = self.native_wifi_state()
        native_collection: tuple[WirelessAttachmentFact, ...] = ()
        if native.status == "ready" and native.fact is not None:
            native_collection = (native.fact,)
            sources.append(SourceStatus("wifi_native", SourceStatusValue.OK, native.message))
        else:
            sources.append(SourceStatus("wifi_native", SourceStatusValue.WARNING, native.message))

        override_collection = (self.wifi_override,) if self.wifi_override else ()
        wireless = merge_wireless_facts(
            values.get("wifi_interfaces", ()),
            values.get("wifi", ()),
            native_collection,
            override_collection,
        )
        if self.wifi_override:
            sources.append(SourceStatus("local_configuration", SourceStatusValue.OK, "Local Wi-Fi fallback is configured."))
        if native.status != "ready" and not any(item.bssid_observed for item in wireless):
            warnings.append(WarningItem(f"wifi_native_{native.status}", native.message, "wifi_native"))

        return PassiveParts(
            interfaces=values.get("interfaces", ()),
            routes=values.get("routes", ()),
            neighbors=values.get("neighbors", ()),
            wireless_attachments=wireless,
            sources=tuple(sources),
            warnings=tuple(warnings),
            failures=tuple(failures),
        )

    def passive_refresh(self):
        """Collect and atomically publish one passive or coherent partial snapshot."""

        parts = self.collect_passive_parts()
        snapshot = build_snapshot(
            interfaces=parts.interfaces,
            routes=parts.routes,
            neighbors=parts.neighbors,
            wireless_attachments=parts.wireless_attachments,
            sources=parts.sources,
            warnings=parts.warnings,
        )
        self.snapshot = snapshot
        return snapshot

    def active_discover(self, request):
        """Run fresh containment, bounded Nmap, then publish atomically."""

        parts = self.collect_passive_parts()
        interface_failure = dict(parts.failures).get("interfaces")
        if interface_failure == "command_timeout":
            raise ApiError(504, "command_timeout", "Interface collection timed out; active target containment could not be verified.", {"timeout_sources": ["interfaces"]})
        if interface_failure:
            raise ApiError(500, "collection_failed", "Interface evidence is unavailable; active target containment could not be verified.", {"failed_sources": ["interfaces"]})

        effective = validate_phase_b(request, parts.interfaces)
        resolution = resolve_nmap(self.nmap_path)
        if not resolution.path:
            raise ApiError(424, "dependency_unavailable", "Nmap is unavailable.", {"resolution_source": resolution.source})
        result = run_command(nmap_spec(resolution.path, (str(item) for item in effective), request.operation_timeout_seconds))
        hosts = validate_active_hosts(parse_nmap_xml(result.stdout), effective)
        metadata = ActiveDiscoveryMetadata(
            requested_networks=tuple(str(item) for item in request.networks),
            effective_networks=tuple(str(item) for item in effective),
            completed=True,
            duration_ms=result.duration_ms,
            hosts_reported_up=len(hosts),
            operation_timeout_seconds=request.operation_timeout_seconds,
        )
        snapshot = build_snapshot(
            interfaces=parts.interfaces,
            routes=parts.routes,
            neighbors=parts.neighbors,
            wireless_attachments=parts.wireless_attachments,
            sources=(*parts.sources, SourceStatus("nmap", SourceStatusValue.OK, duration_ms=result.duration_ms)),
            warnings=parts.warnings,
            active_hosts=hosts,
            active_metadata=metadata,
        )
        self.snapshot = snapshot
        return snapshot


class HomeNetTopoServer(ThreadingHTTPServer):
    """Threaded loopback server carrying one shared application state."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: AppState) -> None:
        self.state = state
        super().__init__(address, HomeNetTopoHandler)


class HomeNetTopoHandler(BaseHTTPRequestHandler):
    """Serve the fixed API and static allowlist with normalized errors."""

    server: HomeNetTopoServer

    def log_message(self, fmt: str, *args: object) -> None:
        """Write the standard local request log without changing response data."""

        print(f"{self.address_string()} - {fmt % args}")

    def _security_headers(self) -> None:
        """Apply the fixed no-store and same-origin browser policy."""

        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), usb=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; "
            "font-src 'self' data:; script-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'",
        )

    def _send_bytes(self, status: int, body: bytes, content_type: str, *, disposition: str | None = None) -> None:
        """Send one bounded in-memory response with fixed security headers."""

        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, status: int, payload: Any, *, disposition: str | None = None) -> None:
        """Serialize deterministic compact JSON and send it without caching."""

        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8", disposition=disposition)

    def _send_error_payload(self, error: ApiError, request_id: str) -> None:
        """Return the public error envelope without leaking command internals."""

        self._send_json(error.status, {"error": {"code": error.code, "message": str(error), "details": error.details, "request_id": request_id}})

    def _validate_host(self) -> None:
        """Reject missing, non-loopback, or DNS-rebinding-style Host values."""

        accepted = {f"127.0.0.1:{self.server.state.port}", f"localhost:{self.server.state.port}"}
        if self.headers.get("Host") not in accepted:
            raise ApiError(400, "invalid_host", "The request Host is not accepted.")

    def _validate_collection_headers(self) -> None:
        """Require JSON and same-origin signals before any command-triggering POST."""

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ApiError(415, "bad_request", "Content-Type must be application/json.")
        if self.headers.get("X-HomeNetTopo-Request") != "1":
            raise ApiError(403, "cross_origin_request", "The collection request is not authorized for this origin.")
        accepted_origins = {f"http://127.0.0.1:{self.server.state.port}", f"http://localhost:{self.server.state.port}"}
        origin = self.headers.get("Origin")
        if origin is not None and origin not in accepted_origins:
            raise ApiError(403, "cross_origin_request", "The request Origin is not accepted.")
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site is not None and fetch_site not in {"same-origin", "none"}:
            raise ApiError(403, "cross_origin_request", "Cross-site collection requests are not accepted.")

    def _read_json(self) -> Any:
        """Read one size-limited UTF-8 JSON body."""

        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ApiError(400, "bad_request", "Content-Length is required.")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ApiError(400, "bad_request", "Content-Length is invalid.") from exc
        if length < 0:
            raise ApiError(400, "bad_request", "Content-Length is invalid.")
        if length > MAX_BODY_BYTES:
            self.close_connection = True
            raise ApiError(413, "target_too_large", "The JSON request body exceeds 16 KiB.")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError(400, "invalid_json", "The request body is not valid JSON.") from exc

    def _acquire_collection(self) -> None:
        """Acquire the single collection owner without queuing another client."""

        if not self.server.state.collection_lock.acquire(blocking=False):
            raise ApiError(409, "collection_in_progress", "Another collection is already running.")

    @staticmethod
    def _command_error(exc: CommandError) -> ApiError:
        """Map normalized command failures to their fixed HTTP status."""

        statuses = {"command_timeout": 504, "dependency_unavailable": 424, "invalid_target": 400, "collection_failed": 500}
        return ApiError(statuses.get(exc.code, 500), exc.code, str(exc))

    def _handle_api(self, split: urllib.parse.SplitResult) -> bool:
        """Handle a fixed API route or return false for static delivery."""

        path = split.path
        if not path.startswith("/api/"):
            return False
        if split.query:
            raise ApiError(400, "bad_request", "API query parameters are not supported for this route.")

        if self.command == "GET" and path == "/api/v1/health":
            self._send_json(200, {"status": "ok", "service": "homeNetTopo", "version": __version__, "platform": platform.system().lower()})
            return True

        if self.command == "GET" and path == "/api/v1/capabilities":
            supported = self.server.state.supported
            resolution = resolve_nmap(self.server.state.nmap_path) if supported else None
            available = bool(supported and resolution and resolution.path)
            native = self.server.state.native_wifi_state()
            self._send_json(200, {
                "platform": platform.system().lower(),
                "passive_collection": supported,
                "active_discovery": {
                    "available": available,
                    "unavailable_reason": None if available else ("unsupported_platform" if not supported else "dependency_unavailable"),
                    "tool": "nmap",
                    "resolution_source": resolution.source if resolution else "unavailable",
                    "mode": "host-discovery-xml",
                    "max_networks_per_request": 32,
                    "max_addresses_per_request": 1024,
                    "operation_timeout_default_seconds": 30,
                    "operation_timeout_min_seconds": 5,
                    "operation_timeout_max_seconds": 120,
                    "host_timeout_seconds": 5,
                },
                "link_path": {
                    "wifi_interface_source": "networksetup",
                    "wifi_bssid_source": "corewlan_native_then_system_profiler",
                    "wifi_native_helper": {
                        "status": native.status,
                        "message": native.message,
                        "launch_url": NATIVE_WIFI_LAUNCH_URL,
                    },
                    "wifi_local_fallback_configured": self.server.state.wifi_override is not None,
                    "ethernet_adjacent_device_source": "not_available_without_lldp",
                },
                "bind": BIND_ADDRESS,
                "port": self.server.state.port,
                "external_assets_required": False,
                "reverse_dns_enabled": False,
                "annotations_supported": False,
            })
            return True

        if self.command == "GET" and path in {"/api/v1/topology", "/api/v1/topology/export"}:
            snapshot = self.server.state.snapshot
            if snapshot is None:
                raise ApiError(404, "not_found", "No topology snapshot is available.")
            disposition = 'attachment; filename="home-network-topology.json"' if path.endswith("/export") else None
            self._send_json(200, snapshot.to_dict(), disposition=disposition)
            return True

        if self.command == "POST" and path in {"/api/v1/topology/refresh", "/api/v1/discover"}:
            self._validate_collection_headers()
            body = self._read_json()
            request = None
            if path.endswith("/refresh"):
                if body != {}:
                    raise ApiError(400, "bad_request", "Passive refresh accepts an empty JSON object.")
            else:
                try:
                    request = validate_phase_a(body)
                except ValidationError as exc:
                    raise ApiError(exc.status, exc.code, str(exc), exc.details) from exc

            self._acquire_collection()
            try:
                snapshot = self.server.state.passive_refresh() if request is None else self.server.state.active_discover(request)
            except ValidationError as exc:
                raise ApiError(exc.status, exc.code, str(exc), exc.details) from exc
            except CommandError as exc:
                raise self._command_error(exc) from exc
            finally:
                self.server.state.collection_lock.release()
            self._send_json(200, snapshot.to_dict())
            return True

        raise ApiError(405, "method_not_allowed", "The method is not allowed for this API route.")

    def _serve_static(self, split: urllib.parse.SplitResult) -> None:
        """Serve only canonical regular files from the fixed web allowlist."""

        try:
            decoded = urllib.parse.unquote(split.path, errors="strict")
            decoded_twice = urllib.parse.unquote(decoded, errors="strict")
        except UnicodeError as exc:
            raise ApiError(404, "not_found", "Static resource not found.") from exc
        if decoded_twice != decoded or "\x00" in decoded or "\\" in decoded or ".." in decoded.split("/"):
            raise ApiError(404, "not_found", "Static resource not found.")
        filename = STATIC_FILES.get(decoded)
        if filename is None:
            raise ApiError(404, "not_found", "Static resource not found.")
        root = WEB_ROOT.resolve()
        candidate = (root / filename).resolve()
        if root not in candidate.parents or not candidate.is_file() or candidate.is_symlink():
            raise ApiError(404, "not_found", "Static resource not found.")
        self._send_bytes(200, candidate.read_bytes(), MIME_TYPES[candidate.suffix])

    def _dispatch(self) -> None:
        """Apply Host validation, route the request, and normalize all errors."""

        request_id = uuid.uuid4().hex[:16]
        try:
            self._validate_host()
            split = urllib.parse.urlsplit(self.path)
            if not self._handle_api(split):
                if self.command not in {"GET", "HEAD"}:
                    raise ApiError(405, "method_not_allowed", "The method is not allowed for this static route.")
                self._serve_static(split)
        except ApiError as error:
            self._send_error_payload(error, request_id)
        except Exception:
            self._send_error_payload(ApiError(500, "internal_error", "An internal error occurred."), request_id)

    def do_GET(self) -> None:
        self._dispatch()

    def do_HEAD(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_OPTIONS(self) -> None:
        self._dispatch()

    def do_PUT(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()


def parse_args() -> argparse.Namespace:
    """Parse fixed service options and optional local Wi-Fi fallback values."""

    parser = argparse.ArgumentParser(description="Serve a local HomeNetTopo web application.")
    parser.add_argument("--bind", default=BIND_ADDRESS)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--nmap-path")
    parser.add_argument("--wifi-interface", type=interface_argument)
    parser.add_argument("--wifi-bssid", type=canonical_mac_argument)
    parser.add_argument("--wifi-ssid", type=ssid_argument)
    parser.add_argument("--wifi-role", choices=("access-point", "relay"))
    return parser.parse_args()


def main() -> int:
    """Validate startup options and serve until interrupted."""

    args = parse_args()
    if args.bind != BIND_ADDRESS:
        raise SystemExit("HomeNetTopo first release binds only to 127.0.0.1")
    if not 1 <= args.port <= 65535:
        raise SystemExit("port must be between 1 and 65535")
    wifi_values_present = any((args.wifi_bssid, args.wifi_ssid, args.wifi_role))
    if wifi_values_present and not args.wifi_interface:
        raise SystemExit("--wifi-interface is required with Wi-Fi fallback values")
    wifi_override = None
    if wifi_values_present:
        role = "access point" if args.wifi_role == "access-point" else args.wifi_role
        wifi_override = WirelessAttachmentFact(
            interface=args.wifi_interface,
            bssid=args.wifi_bssid,
            ssid=args.wifi_ssid,
            associated=False,
            role=role,
            configured=True,
            evidence_source="local_configuration",
        )
    state = AppState(port=args.port, nmap_path=args.nmap_path, wifi_override=wifi_override)
    server = HomeNetTopoServer((args.bind, args.port), state)
    print(f"HomeNetTopo {__version__} listening on http://{args.bind}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
