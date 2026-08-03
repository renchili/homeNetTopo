from __future__ import annotations

import http.client
import json
import threading
import unittest
from unittest import mock

from homenettopo.models import TopologySnapshot
from server import AppState, HomeNetTopoServer


def empty_snapshot():
    return TopologySnapshot("1", "snapshot", "2026-08-03T00:00:00Z", "passive", "darwin", False, (), (), (), (), ())


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

    def request(self, method, path, *, body=None, headers=None, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        connection.putrequest(method, path, skip_host=True)
        connection.putheader("Host", host or f"127.0.0.1:{self.server.server_port}")
        payload = None if body is None else json.dumps(body).encode()
        for key, value in (headers or {}).items():
            connection.putheader(key, value)
        if payload is not None:
            connection.putheader("Content-Length", str(len(payload)))
        connection.endheaders(payload)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, dict(response.getheaders()), json.loads(data) if data else None


class ServerTests(unittest.TestCase):
    def test_health_is_command_free(self):
        with RunningServer() as running, mock.patch("server.run_command") as command:
            status, _, payload = running.request("GET", "/api/v1/health")
            self.assertEqual(status, 200)
            self.assertEqual(payload["service"], "homeNetTopo")
            command.assert_not_called()

    def test_invalid_host_is_rejected(self):
        with RunningServer() as running:
            status, _, payload = running.request("GET", "/api/v1/health", host="attacker.example")
            self.assertEqual(status, 400)
            self.assertEqual(payload["error"]["code"], "invalid_host")

    def test_read_only_topology_hit_and_miss(self):
        with RunningServer() as running:
            status, _, payload = running.request("GET", "/api/v1/topology")
            self.assertEqual((status, payload["error"]["code"]), (404, "not_found"))
            running.state.snapshot = empty_snapshot()
            status, _, payload = running.request("GET", "/api/v1/topology")
            self.assertEqual(status, 200)
            self.assertEqual(payload["snapshot_id"], "snapshot")

    def test_refresh_requires_custom_header(self):
        with RunningServer() as running:
            status, _, payload = running.request("POST", "/api/v1/topology/refresh", body={}, headers={"Content-Type": "application/json"})
            self.assertEqual(status, 403)
            self.assertEqual(payload["error"]["code"], "cross_origin_request")

    def test_refresh_rejects_cross_site_fetch_metadata(self):
        with RunningServer() as running:
            headers = {"Content-Type": "application/json", "X-HomeNetTopo-Request": "1", "Sec-Fetch-Site": "cross-site"}
            status, _, payload = running.request("POST", "/api/v1/topology/refresh", body={}, headers=headers)
            self.assertEqual(status, 403)
            self.assertEqual(payload["error"]["code"], "cross_origin_request")

    def test_refresh_success_and_no_nmap(self):
        with RunningServer() as running:
            running.state.passive_refresh = mock.Mock(return_value=empty_snapshot())
            headers = {"Content-Type": "application/json", "X-HomeNetTopo-Request": "1"}
            status, response_headers, payload = running.request("POST", "/api/v1/topology/refresh", body={}, headers=headers)
            self.assertEqual(status, 200)
            self.assertEqual(payload["mode"], "passive")
            self.assertNotIn("Access-Control-Allow-Origin", response_headers)
            running.state.passive_refresh.assert_called_once_with()

    def test_collection_conflict_is_immediate(self):
        with RunningServer() as running:
            running.state.collection_lock.acquire()
            try:
                headers = {"Content-Type": "application/json", "X-HomeNetTopo-Request": "1"}
                status, _, payload = running.request("POST", "/api/v1/topology/refresh", body={}, headers=headers)
            finally:
                running.state.collection_lock.release()
            self.assertEqual(status, 409)
            self.assertEqual(payload["error"]["code"], "collection_in_progress")

    def test_options_is_not_preflight_bypass(self):
        with RunningServer() as running:
            status, _, payload = running.request("OPTIONS", "/api/v1/discover")
            self.assertEqual(status, 405)
            self.assertEqual(payload["error"]["code"], "method_not_allowed")


if __name__ == "__main__":
    unittest.main()
