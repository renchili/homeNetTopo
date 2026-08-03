from __future__ import annotations

import http.client
import json
import threading
import unittest
from unittest import mock

from homenettopo.models import ActiveDiscoveryMetadata, TopologySnapshot
from server import ApiError, AppState, HomeNetTopoServer


def empty_snapshot(*, mode="passive"):
    active = None
    if mode == "active":
        active = ActiveDiscoveryMetadata(("192.168.1.0/24",), ("192.168.1.0/24",), True, 5, 0, 30)
    return TopologySnapshot("1", f"{mode}-snapshot", "2026-08-03T00:00:00Z", mode, "darwin", False, (), (), (), (), (), active)


class RunningServer:
    def __enter__(self):
        self.state = AppState(port=0, nmap_path=None)
        self.server = HomeNetTopoServer(("127.0.0.1", 0), self.state)
        self.state.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, *, body=None, raw_body=None, headers=None, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        connection.putrequest(method, path, skip_host=True)
        connection.putheader("Host", host or f"127.0.0.1:{self.server.server_port}")
        payload = raw_body if raw_body is not None else (None if body is None else json.dumps(body).encode())
        for key, value in (headers or {}).items():
            connection.putheader(key, value)
        if payload is not None:
            connection.putheader("Content-Length", str(len(payload)))
        connection.endheaders(payload)
        response = connection.getresponse()
        data = response.read()
        result = response.status, dict(response.getheaders()), json.loads(data) if data else None
        connection.close()
        return result


COLLECTION_HEADERS = {"Content-Type": "application/json", "X-HomeNetTopo-Request": "1"}


class ServerTests(unittest.TestCase):
    def test_health_and_read_only_routes_are_command_free(self):
        with RunningServer() as running, mock.patch("server.run_command") as command:
            status, _, payload = running.request("GET", "/api/v1/health")
            self.assertEqual((status, payload["service"]), (200, "homeNetTopo"))
            running.state.snapshot = empty_snapshot()
            self.assertEqual(running.request("GET", "/api/v1/topology")[0], 200)
            self.assertEqual(running.request("GET", "/api/v1/topology/export")[0], 200)
            command.assert_not_called()

    def test_invalid_and_dns_rebinding_style_hosts_are_rejected(self):
        with RunningServer() as running:
            for host in ("attacker.example", f"home.example:{running.server.server_port}", "127.0.0.1"):
                with self.subTest(host=host):
                    status, _, payload = running.request("GET", "/api/v1/health", host=host)
                    self.assertEqual((status, payload["error"]["code"]), (400, "invalid_host"))

    def test_topology_miss_and_query_rejection(self):
        with RunningServer() as running:
            status, _, payload = running.request("GET", "/api/v1/topology")
            self.assertEqual((status, payload["error"]["code"]), (404, "not_found"))
            status, _, payload = running.request("GET", "/api/v1/topology?refresh=true")
            self.assertEqual((status, payload["error"]["code"]), (400, "bad_request"))

    def test_export_headers(self):
        with RunningServer() as running:
            running.state.snapshot = empty_snapshot()
            status, headers, _ = running.request("GET", "/api/v1/topology/export")
            self.assertEqual(status, 200)
            self.assertEqual(headers["Content-Disposition"], 'attachment; filename="home-network-topology.json"')
            self.assertEqual(headers["Cache-Control"], "no-store")

    def test_capabilities_on_unsupported_platform_do_not_probe_commands(self):
        with RunningServer() as running, mock.patch("server.platform.system", return_value="Linux"), mock.patch("server.resolve_nmap") as resolver, mock.patch("server.run_command") as command:
            status, _, payload = running.request("GET", "/api/v1/capabilities")
            self.assertEqual(status, 200)
            self.assertFalse(payload["passive_collection"])
            self.assertEqual(payload["active_discovery"]["unavailable_reason"], "unsupported_platform")
            resolver.assert_not_called()
            command.assert_not_called()

    def test_collection_header_content_type_origin_and_fetch_metadata_denials(self):
        cases = [
            ({"Content-Type": "application/json"}, 403),
            ({**COLLECTION_HEADERS, "Origin": "https://attacker.example"}, 403),
            ({**COLLECTION_HEADERS, "Sec-Fetch-Site": "cross-site"}, 403),
            ({"Content-Type": "text/plain", "X-HomeNetTopo-Request": "1"}, 415),
        ]
        with RunningServer() as running:
            for headers, expected in cases:
                with self.subTest(headers=headers):
                    status, response_headers, _ = running.request("POST", "/api/v1/topology/refresh", body={}, headers=headers)
                    self.assertEqual(status, expected)
                    self.assertNotIn("Access-Control-Allow-Origin", response_headers)

    def test_invalid_json_and_oversized_body(self):
        with RunningServer() as running:
            status, _, payload = running.request("POST", "/api/v1/topology/refresh", raw_body=b"{", headers=COLLECTION_HEADERS)
            self.assertEqual((status, payload["error"]["code"]), (400, "invalid_json"))
            status, _, payload = running.request("POST", "/api/v1/topology/refresh", raw_body=b"x" * (16 * 1024 + 1), headers=COLLECTION_HEADERS)
            self.assertEqual((status, payload["error"]["code"]), (413, "target_too_large"))

    def test_passive_refresh_success_and_no_nmap_path(self):
        with RunningServer() as running:
            running.state.passive_refresh = mock.Mock(return_value=empty_snapshot())
            running.state.active_discover = mock.Mock()
            status, _, payload = running.request("POST", "/api/v1/topology/refresh", body={}, headers=COLLECTION_HEADERS)
            self.assertEqual((status, payload["mode"]), (200, "passive"))
            running.state.passive_refresh.assert_called_once_with()
            running.state.active_discover.assert_not_called()

    def test_phase_a_rejection_happens_before_lock_and_active_method(self):
        with RunningServer() as running:
            running.state.active_discover = mock.Mock()
            status, _, payload = running.request("POST", "/api/v1/discover", body={"networks": ["8.8.8.0/24"]}, headers=COLLECTION_HEADERS)
            self.assertEqual((status, payload["error"]["code"]), (400, "invalid_target"))
            running.state.active_discover.assert_not_called()
            self.assertTrue(running.state.collection_lock.acquire(blocking=False))
            running.state.collection_lock.release()

    def test_active_success_and_failed_operation_preserve_previous_snapshot(self):
        with RunningServer() as running:
            previous = empty_snapshot()
            running.state.snapshot = previous
            running.state.active_discover = mock.Mock(return_value=empty_snapshot(mode="active"))
            body = {"networks": ["192.168.1.0/24"], "operation_timeout_seconds": 30}
            status, _, payload = running.request("POST", "/api/v1/discover", body=body, headers=COLLECTION_HEADERS)
            self.assertEqual((status, payload["mode"]), (200, "active"))
            running.state.snapshot = previous
            running.state.active_discover = mock.Mock(side_effect=ApiError(424, "dependency_unavailable", "Nmap is unavailable."))
            status, _, payload = running.request("POST", "/api/v1/discover", body=body, headers=COLLECTION_HEADERS)
            self.assertEqual((status, payload["error"]["code"]), (424, "dependency_unavailable"))
            self.assertIs(running.state.snapshot, previous)

    def test_collection_conflict_is_immediate(self):
        with RunningServer() as running:
            running.state.collection_lock.acquire()
            try:
                status, _, payload = running.request("POST", "/api/v1/topology/refresh", body={}, headers=COLLECTION_HEADERS)
            finally:
                running.state.collection_lock.release()
            self.assertEqual((status, payload["error"]["code"]), (409, "collection_in_progress"))

    def test_unsupported_collection_and_options(self):
        with RunningServer() as running, mock.patch("server.platform.system", return_value="Linux"):
            status, _, payload = running.request("POST", "/api/v1/topology/refresh", body={}, headers=COLLECTION_HEADERS)
            self.assertEqual((status, payload["error"]["code"]), (501, "unsupported_platform"))
        with RunningServer() as running:
            status, _, payload = running.request("OPTIONS", "/api/v1/discover")
            self.assertEqual((status, payload["error"]["code"]), (405, "method_not_allowed"))


if __name__ == "__main__":
    unittest.main()
