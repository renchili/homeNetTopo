#!/usr/bin/env python3
"""Loopback-only HomeNetTopo HTTP service."""

from __future__ import annotations

import argparse
import json
import platform
import threading
import urllib.parse
import uuid
from dataclasses import dataclass
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
)
from homenettopo.discovery import MAX_BODY_BYTES, ValidationError, parse_nmap_xml, validate_phase_a, validate_phase_b
from homenettopo.interfaces import InterfaceFact, parse_ifconfig
from homenettopo.models import ActiveDiscoveryMetadata, SourceStatus, SourceStatusValue, WarningItem
from homenettopo.neighbors import NeighborFact, parse_neighbors
from homenettopo.routes import RouteFact, parse_routes
from homenettopo.topology import build_snapshot

BIND_ADDRESS = "127.0.0.1"
DEFAULT_PORT = 8765
WEB_ROOT = Path(__file__).resolve().parent / "web"
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


class ApiError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class PassiveParts:
    interfaces: tuple[InterfaceFact, ...]
    routes: tuple[RouteFact, ...]
    neighbors: tuple[NeighborFact, ...]
    sources: tuple[SourceStatus, ...]
    warnings: tuple[WarningItem, ...]


class AppState:
    def __init__(self, *, port: int, nmap_path: str | None) -> None:
        self.port = port
        self.nmap_path = nmap_path
        self.snapshot = None
        self.collection_lock = threading.Lock()

    @property
    def supported(self) -> bool:
        return platform.system().lower() == "darwin"

    def collect_passive_parts(self) -> PassiveParts:
        if not self.supported:
            raise ApiError(501, "unsupported_platform", "Collection is supported only on macOS.")

        values: dict[str, Any] = {}
        sources: list[SourceStatus] = []
        warnings: list[WarningItem] = []
        failure_codes: list[str] = []
        collectors: tuple[tuple[str, Any, Callable[[str], Any]], ...] = (
            ("interfaces", interfaces_spec(), parse_ifconfig),
            ("routes", routes_spec(), parse_routes),
            ("neighbors", neighbors_spec(), parse_neighbors),
        )

        for name, spec, parser in collectors:
            try:
                result = run_command(spec)
                parsed = parser(result.stdout)
                if name == "interfaces" and not parsed:
                    raise ValueError("No interface facts were parsed.")
                values[name] = parsed
            except CommandError as exc:
                failure_codes.append(exc.code)
                sources.append(SourceStatus(name, SourceStatusValue.FAILED, "Collection command failed."))
                warnings.append(WarningItem(f"{name}_collection_failed", f"{name.title()} evidence could not be collected.", name))
            except (ValueError, UnicodeError):
                failure_codes.append("collection_failed")
                sources.append(SourceStatus(name, SourceStatusValue.FAILED, "Collected output could not be parsed."))
                warnings.append(WarningItem(f"{name}_parse_failed", f"{name.title()} evidence could not be parsed.", name))
            else:
                sources.append(SourceStatus(name, SourceStatusValue.OK, duration_ms=result.duration_ms))

        if not any(values.get(name) for name in ("interfaces", "routes", "neighbors")):
            if "command_timeout" in failure_codes:
                raise ApiError(504, "command_timeout", "Passive collection timed out before a coherent snapshot could be produced.")
            raise ApiError(500, "collection_failed", "No coherent passive snapshot could be produced.")

        return PassiveParts(
            interfaces=values.get("interfaces", ()),
            routes=values.get("routes", ()),
            neighbors=values.get("neighbors", ()),
            sources=tuple(sources),
            warnings=tuple(warnings),
        )

    def passive_refresh(self):
        parts = self.collect_passive_parts()
        snapshot = build_snapshot(
            interfaces=parts.interfaces,
            routes=parts.routes,
            neighbors=parts.neighbors,
            sources=parts.sources,
            warnings=parts.warnings,
        )
        self.snapshot = snapshot
        return snapshot

    def active_discover(self, request):
        parts = self.collect_passive_parts()
        effective = validate_phase_b(request, parts.interfaces)
        resolution = resolve_nmap(self.nmap_path)
        if not resolution.path:
            raise ApiError(424, "dependency_unavailable", "Nmap is unavailable.", {"resolution_source": resolution.source})
        result = run_command(
            nmap_spec(
                resolution.path,
                (str(item) for item in effective),
                request.operation_timeout_seconds,
            )
        )
        hosts = parse_nmap_xml(result.stdout)
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
            sources=(*parts.sources, SourceStatus("nmap", SourceStatusValue.OK, duration_ms=result.duration_ms)),
            warnings=parts.warnings,
            active_hosts=hosts,
            active_metadata=metadata,
        )
        self.snapshot = snapshot
        return snapshot


class HomeNetTopoServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: AppState) -> None:
        self.state = state
        super().__init__(address, HomeNetTopoHandler)


class HomeNetTopoHandler(BaseHTTPRequestHandler):
    server: HomeNetTopoServer

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), usb=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )

    def _send_bytes(self, status: int, body: bytes, content_type: str, *, disposition: str | None = None) -> None:
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
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8", disposition=disposition)

    def _send_error_payload(self, error: ApiError, request_id: str) -> None:
        self._send_json(
            error.status,
            {"error": {"code": error.code, "message": str(error), "details": error.details, "request_id": request_id}},
        )

    def _validate_host(self) -> None:
        accepted = {f"127.0.0.1:{self.server.state.port}", f"localhost:{self.server.state.port}"}
        if self.headers.get("Host") not in accepted:
            raise ApiError(400, "invalid_host", "The request Host is not accepted.")

    def _validate_collection_headers(self) -> None:
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
        body = self.rfile.read(length)
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError(400, "invalid_json", "The request body is not valid JSON.") from exc

    def _acquire_collection(self) -> None:
        if not self.server.state.collection_lock.acquire(blocking=False):
            raise ApiError(409, "collection_in_progress", "Another collection is already running.")

    @staticmethod
    def _command_error(exc: CommandError) -> ApiError:
        statuses = {
            "command_timeout": 504,
            "dependency_unavailable": 424,
            "invalid_target": 400,
            "collection_failed": 500,
        }
        return ApiError(statuses.get(exc.code, 500), exc.code, str(exc))

    def _handle_api(self, split: urllib.parse.SplitResult) -> bool:
        path = split.path
        if not path.startswith("/api/"):
            return False
        if split.query:
            raise ApiError(400, "bad_request", "API query parameters are not supported for this route.")

        if self.command == "GET" and path == "/api/v1/health":
            self._send_json(200, {
                "status": "ok",
                "service": "homeNetTopo",
                "version": __version__,
                "platform": platform.system().lower(),
            })
            return True

        if self.command == "GET" and path == "/api/v1/capabilities":
            supported = self.server.state.supported
            resolution = resolve_nmap(self.server.state.nmap_path) if supported else None
            available = bool(supported and resolution and resolution.path)
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
    parser = argparse.ArgumentParser(description="Serve a local HomeNetTopo web application.")
    parser.add_argument("--bind", default=BIND_ADDRESS)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--nmap-path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.bind != BIND_ADDRESS:
        raise SystemExit("HomeNetTopo first release binds only to 127.0.0.1")
    if not 1 <= args.port <= 65535:
        raise SystemExit("port must be between 1 and 65535")
    state = AppState(port=args.port, nmap_path=args.nmap_path)
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
