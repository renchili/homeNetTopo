from __future__ import annotations

import http.client
import importlib.util
import plistlib
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from server import AppState, HomeNetTopoServer

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_PATH = ROOT / "scripts" / "deploy.py"


def load_deploy_module():
    """Load the deployment script without requiring scripts to be a package."""

    spec = importlib.util.spec_from_file_location("homenettopo_deploy", DEPLOY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("deployment module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class StaticSecurityTests(unittest.TestCase):
    """Exercise the fixed static-file allowlist and browser security headers."""

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
        csp = headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("font-src 'self' data:", csp)
        self.assertNotIn("font-src http:", csp)
        self.assertNotIn("font-src https:", csp)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_rejects_traversal_repeated_decoding_and_unknown_files(self):
        for path in ("/../AGENT.md", "/%2e%2e/AGENT.md", "/%252e%252e/AGENT.md", "/missing.js"):
            with self.subTest(path=path):
                status, _, _ = self.request(path)
                self.assertEqual(status, 404)

    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "web"
            root.mkdir()
            outside = Path(directory) / "outside.js"
            outside.write_text("secret", encoding="utf-8")
            (root / "app.js").symlink_to(outside)
            with mock.patch("server.WEB_ROOT", root):
                status, _, body = self.request("/app.js")
            self.assertEqual(status, 404)
            self.assertNotIn(b"secret", body)


class DeploymentScriptTests(unittest.TestCase):
    """Keep local deployment user-scoped, fixed-source, and loopback-only."""

    @classmethod
    def setUpClass(cls):
        cls.deploy = load_deploy_module()

    def make_runtime_source(self, root: Path) -> None:
        """Create the exact synthetic runtime files expected by the deployer."""

        for relative in self.deploy.RUNTIME_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative, encoding="utf-8")

    def make_native_source(self, root: Path) -> None:
        """Create the exact synthetic native source manifest expected by deployment."""

        for relative in self.deploy.NATIVE_SOURCE_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative, encoding="utf-8")

    def test_launch_agent_is_user_scoped_and_loopback_only(self):
        payload = self.deploy.build_launch_agent("/usr/local/bin/python3", 8765, None)
        arguments = payload["ProgramArguments"]
        self.assertEqual(payload["Label"], "com.homenettopo.local")
        self.assertEqual(arguments[:2], ["/usr/local/bin/python3", str(self.deploy.INSTALL_DIR / "server.py")])
        self.assertEqual(arguments[arguments.index("--bind") + 1], "127.0.0.1")
        self.assertEqual(arguments[arguments.index("--port") + 1], "8765")
        self.assertTrue(str(self.deploy.INSTALL_DIR).startswith(str(Path.home() / "Library")))
        self.assertTrue(str(self.deploy.PLIST_PATH).startswith(str(Path.home() / "Library" / "LaunchAgents")))
        self.assertEqual(payload["KeepAlive"], {"SuccessfulExit": False})

    def test_wifi_fallback_is_validated_and_written_only_to_program_arguments(self):
        bssid = "02:aa:bb:cc:dd:55"
        payload = self.deploy.build_launch_agent(
            "/usr/local/bin/python3",
            8765,
            None,
            wifi_interface="en0",
            wifi_bssid=bssid,
            wifi_ssid="Synthetic Wi-Fi",
            wifi_role="relay",
        )
        arguments = payload["ProgramArguments"]
        self.assertEqual(arguments[arguments.index("--wifi-interface") + 1], "en0")
        self.assertEqual(arguments[arguments.index("--wifi-bssid") + 1], bssid)
        self.assertEqual(arguments[arguments.index("--wifi-ssid") + 1], "Synthetic Wi-Fi")
        self.assertEqual(arguments[arguments.index("--wifi-role") + 1], "relay")
        self.assertNotIn(bssid, payload["EnvironmentVariables"].values())
        self.assertNotIn(bssid, payload["StandardOutPath"])
        self.assertEqual(self.deploy.validate_mac("02-AA-BB-CC-DD-55"), bssid)
        self.assertEqual(self.deploy.validate_interface("en0"), "en0")
        self.assertEqual(self.deploy.validate_ssid("Synthetic Wi-Fi"), "Synthetic Wi-Fi")
        for invalid in ("not-a-mac", "00:11:22:33:44"):
            with self.subTest(invalid=invalid), self.assertRaises(Exception):
                self.deploy.validate_mac(invalid)
        with self.assertRaises(Exception):
            self.deploy.validate_interface("en0;echo")
        with self.assertRaises(Exception):
            self.deploy.validate_ssid("")

    def test_runtime_copy_is_an_explicit_minimal_allowlist(self):
        self.assertEqual(
            self.deploy.RUNTIME_FILES,
            (
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
            ),
        )
        self.assertEqual(
            self.deploy.NATIVE_SOURCE_FILES,
            (
                "macos/HomeNetTopoApp/HomeNetTopoApp.swift",
                "macos/HomeNetTopoApp/AppDelegate.swift",
                "macos/HomeNetTopoApp/WiFiCollector.swift",
                "macos/HomeNetTopoApp/Info.plist",
                "macos/HomeNetTopoApp/HomeNetTopoApp.xcodeproj/project.pbxproj",
            ),
        )
        self.assertTrue(str(self.deploy.NATIVE_APP_PATH).startswith(str(Path.home() / "Applications")))
        self.assertEqual(self.deploy.NATIVE_APP_BUNDLE_ID, "com.homenettopo.wifi")

        source = DEPLOY_PATH.read_text(encoding="utf-8")
        self.assertNotIn("sudo", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("0.0.0.0", source)
        self.assertNotIn("https://", source)
        self.assertIn("ProxyHandler({})", source)
        self.assertIn("follow_symlinks=False", source)
        self.assertIn('PLUTIL_PATH = "/usr/bin/plutil"', source)
        self.assertIn('XCODEBUILD_PATH = "/usr/bin/xcodebuild"', source)
        self.assertIn('CODESIGN_PATH = "/usr/bin/codesign"', source)
        self.assertIn('OPEN_PATH = "/usr/bin/open"', source)
        self.assertIn('"-target",\n            NATIVE_TARGET', source)
        self.assertIn('"--sign", "-"', source)
        self.assertIn('run_launchctl("enable", service_target()', source)
        self.assertIn('run_launchctl("print-disabled", service_domain()', source)
        self.assertIn("Do not rerun as root", source)
        for marker in ("--wifi-interface", "--wifi-bssid", "--wifi-ssid", "--wifi-role"):
            self.assertIn(marker, source)

    def test_native_privacy_identity_and_login_item_sources_are_explicit(self):
        plist_path = ROOT / "macos" / "HomeNetTopoApp" / "Info.plist"
        with plist_path.open("rb") as handle:
            payload = plistlib.load(handle)
        self.assertIn("NSLocationUsageDescription", payload)
        self.assertIn("NSLocationWhenInUseUsageDescription", payload)
        self.assertIn("SSID", payload["NSLocationUsageDescription"])
        self.assertIn("BSSID", payload["NSLocationUsageDescription"])

        collector = (ROOT / "macos" / "HomeNetTopoApp" / "WiFiCollector.swift").read_text(encoding="utf-8")
        delegate = (ROOT / "macos" / "HomeNetTopoApp" / "AppDelegate.swift").read_text(encoding="utf-8")
        project = (ROOT / "macos" / "HomeNetTopoApp" / "HomeNetTopoApp.xcodeproj" / "project.pbxproj").read_text(encoding="utf-8")
        self.assertIn("CWWiFiClient.shared()", collector)
        self.assertIn("requestWhenInUseAuthorization()", collector)
        self.assertIn('"wifi-current.json"', collector)
        self.assertIn("SMAppService.mainApp", delegate)
        self.assertIn("PRODUCT_BUNDLE_IDENTIFIER = com.homenettopo.wifi", project)
        self.assertNotIn("CODE_SIGN_ENTITLEMENTS", project)

    def test_source_validation_rejects_symbolic_links_for_runtime_and_native_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_runtime_source(root)
            self.make_native_source(root)
            target = root / "outside.txt"
            target.write_text("outside", encoding="utf-8")

            runtime_candidate = root / "web" / "app.js"
            runtime_candidate.unlink()
            try:
                runtime_candidate.symlink_to(target)
            except OSError as exc:
                self.skipTest(f"symbolic links are unavailable: {exc}")
            with self.assertRaises(self.deploy.DeploymentError):
                self.deploy.validate_source_root(root)

            runtime_candidate.unlink()
            runtime_candidate.write_text("app", encoding="utf-8")
            native_candidate = root / "macos" / "HomeNetTopoApp" / "WiFiCollector.swift"
            native_candidate.unlink()
            native_candidate.symlink_to(target)
            with self.assertRaises(self.deploy.DeploymentError):
                self.deploy.validate_native_source_root(root)

    def test_loaded_service_must_stop_before_replacement(self):
        loaded = self.deploy.subprocess.CompletedProcess(("launchctl", "print"), 0, "", "")
        with mock.patch.object(
            self.deploy,
            "run_launchctl",
            side_effect=(loaded, self.deploy.DeploymentError("synthetic bootout failure")),
        ) as launchctl:
            with self.assertRaises(self.deploy.DeploymentError):
                self.deploy.bootout_if_loaded()
        self.assertEqual(launchctl.call_args_list[0], mock.call("print", self.deploy.service_target(), check=False))
        self.assertEqual(launchctl.call_args_list[1], mock.call("bootout", self.deploy.service_target(), check=True))

    def test_bootstrap_enables_and_cleans_stale_registration_before_loading(self):
        success = self.deploy.subprocess.CompletedProcess(("launchctl",), 0, "", "")
        absent = self.deploy.subprocess.CompletedProcess(("launchctl",), 3, "", "not loaded")
        with (
            mock.patch.object(self.deploy, "validate_launch_agent"),
            mock.patch.object(self.deploy, "run_launchctl", side_effect=(success, absent, success)) as launchctl,
        ):
            self.deploy.bootstrap_agent()
        self.assertEqual(
            launchctl.call_args_list,
            [
                mock.call("enable", self.deploy.service_target(), check=False),
                mock.call("bootout", self.deploy.service_domain(), str(self.deploy.PLIST_PATH), check=False),
                mock.call("bootstrap", self.deploy.service_domain(), str(self.deploy.PLIST_PATH), check=False),
            ],
        )

    def test_bootstrap_failure_reports_non_root_diagnostics(self):
        success = self.deploy.subprocess.CompletedProcess(("launchctl",), 0, "", "")
        absent = self.deploy.subprocess.CompletedProcess(("launchctl",), 3, "", "not loaded")
        failed = self.deploy.subprocess.CompletedProcess(("launchctl",), 5, "", "Bootstrap failed: 5: Input/output error")
        with (
            mock.patch.object(self.deploy, "validate_launch_agent"),
            mock.patch.object(self.deploy, "run_launchctl", side_effect=(success, absent, failed)),
            mock.patch.object(self.deploy, "launchd_diagnostics", return_value="synthetic diagnostics"),
            self.assertRaises(self.deploy.DeploymentError) as raised,
        ):
            self.deploy.bootstrap_agent()
        self.assertIn("Do not rerun as root", str(raised.exception))
        self.assertIn("synthetic diagnostics", str(raised.exception))

    def test_replace_failure_restores_previous_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            install = parent / "HomeNetTopo"
            staging = parent / "staging"
            install.mkdir()
            staging.mkdir()
            (install / "version.txt").write_text("old", encoding="utf-8")
            (staging / "version.txt").write_text("new", encoding="utf-8")
            original_rename = Path.rename

            def fail_staging_rename(path, target):
                if path == staging:
                    raise OSError("synthetic replacement failure")
                return original_rename(path, target)

            with (
                mock.patch.object(self.deploy, "INSTALL_DIR", install),
                mock.patch.object(Path, "rename", new=fail_staging_rename),
                self.assertRaises(OSError),
            ):
                self.deploy.replace_runtime(staging)
            self.assertEqual((install / "version.txt").read_text(encoding="utf-8"), "old")

    def test_port_validation_rejects_invalid_values(self):
        self.assertEqual(self.deploy.validate_port("8765"), 8765)
        for value in (0, 65536, "not-a-port"):
            with self.subTest(value=value), self.assertRaises(Exception):
                self.deploy.validate_port(value)


if __name__ == "__main__":
    unittest.main()
