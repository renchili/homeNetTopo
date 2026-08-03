from __future__ import annotations

import http.client
import threading
import unittest

from server import AppState, HomeNetTopoServer


class StaticSecurityTests(unittest.TestCase):
    def setUp(self):
        self.state = AppState(port=0, nmap_path=None)
        self.server = HomeNetTopoServer(("127.0.0.1", 0), self.state)
        self.state.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        connection.putrequest("GET", path, skip_host=True)
        connection.putheader("Host", f"localhost:{self.server.server_port}")
        connection.endheaders()
        response = connection.getresponse()
        body = response.read()
        headers = dict(response.getheaders())
        connection.close()
        return response.status, headers, body

    def test_serves_only_explicit_assets_with_security_headers(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Home Net Topology", body)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_rejects_traversal_and_repeated_decoding(self):
        for path in ("/../AGENT.md", "/%2e%2e/AGENT.md", "/%252e%252e/AGENT.md", "/missing.js"):
            with self.subTest(path=path):
                status, _, _ = self.request(path)
                self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
