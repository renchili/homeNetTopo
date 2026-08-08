from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from homenettopo.commands import CommandError, CommandKind, CommandResult
from homenettopo.discovery import ValidationError, validate_phase_a
from homenettopo.interfaces import InterfaceAddress, InterfaceFact, WirelessAttachmentFact
from homenettopo.models import ActiveDiscoveryMetadata, SourceStatus, SourceStatusValue, TopologySnapshot
from server import (
    ApiError,
    AppState,
    HomeNetTopoServer,
    NativeWiFiCacheState,
    PassiveParts,
    read_native_wifi_cache,
)


def empty_snapshot(*, mode="passive"):
    active = None
    if mode == "active":
        active = ActiveDiscoveryMetadata(("192.168.1.0/24",), ("192.168.1.0/24",), True, 5, 0, 30)
    return TopologySnapshot("1", f"{mode}-snapshot", "2026-08-03T00:00:00Z", mode, "darwin", False, (), (), (), (), (), active)


def interface_fact(network: str, name: str, kind: str = "physical") -> InterfaceFact:
    parsed = __import__("ipaddress").IPv4Network(network)
    address = str(next(parsed.hosts())) if parsed.num_addresses > 2 else str(parsed.network_address)
    return InterfaceFact(name, ("UP",), kind, (InterfaceAddress(address, parsed.prefixlen, str(parsed)),))


def passive_parts(*interfaces: InterfaceFact, failures=(), wireless_attachments=()) -> PassiveParts:
    return PassiveParts(
        interfaces=tuple(interfaces),
        routes=(),
        neighbors=(),
        wireless_attachments=tuple(wireless_attachments),
        sources=(
            SourceStatus("interfaces", SourceStatusValue.OK),
            SourceStatus("routes", SourceStatusValue.OK),
            SourceStatus("neighbors", SourceStatusValue.OK),
            SourceStatus("wifi_interfaces", SourceStatusValue.OK),
            SourceStatus("wifi", SourceStatusValue.OK),
        ),
        warnings=(),
        failures=tuple(failures),
    )


def failed_interface_parts(code: str) -> PassiveParts:
    return PassiveParts(
        interfaces=(),
        routes=(),
        neighbors=(),
        wireless_attachments=(),
        sources=(
            SourceStatus("interfaces", SourceStatusValue.FAILED, "Interface evidence failed."),
            SourceStatus("routes", SourceStatusValue.OK),
            SourceStatus("neighbors", SourceStatusValue.OK),
            SourceStatus("wifi_interfaces", SourceStatusValue.OK),
            SourceStatus("wifi", SourceStatusValue.OK),
        ),
        warnings=(),
        failures=(("interfaces", code),),
    )


def nmap_xml(address: str, mac: str | None = None) -> str:
    mac_element = f'<address addr="{mac}" addrtype="mac"/>' if mac else ""
    return f'<nmaprun><host><status state="up"/><address addr="{address}" addrtype="ipv4"/>{mac_element}</host></nmaprun>'


def hardware_ports(interface: str = "en0") -> str:
    return f"Hardware Port: Wi-Fi\nDevice: {interface}\nEthernet Address: 02:00:00:00:20:01\n"


def airport_json(*, bssid: str | None) -> str:
    current = {"_name": "Automatic Wi-Fi"}
    if bssid is not None:
        current["spairport_bssid"] = bssid
    return json.dumps({
        "SPAirPortDataType": [{
            "spairport_airport_interfaces": [{
                "_name": "en0",
                "spairport_current_network_information": current,
            }],
        }],
    })


def native_cache_payload(timestamp: str, *, authorization="authorized", bssid="02:aa:bb:cc:dd:42", wifi=True) -> bytes:
    association = None
    if wifi:
        association = {
            "interface": "en0",
            "ssid": "Native Wi-Fi",
            "bssid": bssid,
            "hardware_mac_address": "02:00:00:00:20:01",
            "channel": "40",
            "rssi_dbm": -35,
            "noise_dbm": -90,
            "phy_mode": "802.11ax",
            "transmit_rate_mbps": 2401,
        }
    return json.dumps({
        "schema_version": 1,
        "collected_at": timestamp,
        "authorization": authorization,
        "wifi": association,
    }).encode()


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

    def test_capabilities_explain_native_wifi_source_without_disclosing_identity(self):
        with RunningServer() as running, mock.patch("server.platform.system", return_value="Linux"), mock.patch("server.resolve_nmap") as resolver, mock.patch("server.run_command") as command:
            status, _, payload = running.request("GET", "/api/v1/capabilities")
            self.assertEqual(status, 200)
            self.assertFalse(payload["passive_collection"])
            self.assertEqual(payload["active_discovery"]["unavailable_reason"], "unsupported_platform")
            self.assertEqual(payload["link_path"]["wifi_interface_source"], "networksetup")
            self.assertEqual(payload["link_path"]["wifi_bssid_source"], "corewlan_native_then_system_profiler")
            self.assertFalse(payload["link_path"]["wifi_local_fallback_configured"])
            helper = payload["link_path"]["wifi_native_helper"]
            self.assertEqual(helper["status"], "unsupported")
            self.assertEqual(helper["launch_url"], "homenettopo-wifi://authorize")
            self.assertNotIn("ssid", json.dumps(helper).lower())
            self.assertNotIn("bssid", json.dumps(helper).lower())
            self.assertIn("lldp", payload["link_path"]["ethernet_adjacent_device_source"])
            resolver.assert_not_called()
            command.assert_not_called()

    def test_native_wifi_cache_requires_fresh_owned_regular_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wifi-current.json"
            path.write_bytes(native_cache_payload("2026-08-08T12:00:00Z"))
            path.chmod(0o600)
            fresh = read_native_wifi_cache(path, now=datetime(2026, 8, 8, 12, 0, 10, tzinfo=timezone.utc))
            self.assertEqual(fresh.status, "ready")
            self.assertEqual(fresh.fact.bssid if fresh.fact else None, "02:aa:bb:cc:dd:42")
            stale = read_native_wifi_cache(path, now=datetime(2026, 8, 8, 12, 0, 25, tzinfo=timezone.utc))
            self.assertEqual(stale.status, "stale")
            path.chmod(0o666)
            self.assertEqual(read_native_wifi_cache(path, now=datetime(2026, 8, 8, 12, 0, 10, tzinfo=timezone.utc)).status, "invalid")
            self.assertEqual(path.stat().st_uid, os.getuid())

    def test_native_wifi_denied_state_is_actionable_but_contains_no_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wifi-current.json"
            path.write_bytes(native_cache_payload("2026-08-08T12:00:00Z", authorization="denied", wifi=False))
            path.chmod(0o600)
            state = read_native_wifi_cache(path, now=datetime(2026, 8, 8, 12, 0, 10, tzinfo=timezone.utc))
            self.assertEqual(state.status, "denied")
            self.assertIsNone(state.fact)
            self.assertIn("Location", state.message)

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

    def test_real_active_discover_rejects_phase_b_before_resolving_nmap(self):
        state = AppState(port=8765, nmap_path=None)
        previous = empty_snapshot()
        state.snapshot = previous
        request = validate_phase_a({"networks": ["192.168.2.0/24"], "operation_timeout_seconds": 30})
        parts = passive_parts(interface_fact("192.168.1.0/24", "en0"))
        with (
            mock.patch.object(state, "collect_passive_parts", return_value=parts),
            mock.patch("server.resolve_nmap") as resolver,
            mock.patch("server.run_command") as command,
            self.assertRaises(ValidationError),
        ):
            state.active_discover(request)
        resolver.assert_not_called()
        command.assert_not_called()
        self.assertIs(state.snapshot, previous)

    def test_real_active_discover_preserves_phase_b_effective_targets_order_and_wifi(self):
        state = AppState(port=8765, nmap_path=None)
        request = validate_phase_a({"networks": ["192.168.1.0/24", "192.168.1.0/25"], "operation_timeout_seconds": 30})
        parts = passive_parts(
            interface_fact("192.168.1.0/24", "en0"),
            interface_fact("192.168.1.0/25", "en1"),
            wireless_attachments=(WirelessAttachmentFact("en0", "02:00:00:00:00:01", "Synthetic Wi-Fi"),),
        )
        order: list[str] = []
        captured: dict[str, object] = {}

        def collect():
            order.append("collect")
            return parts

        def resolve(_explicit):
            order.append("resolve")
            return mock.Mock(path="/opt/homebrew/bin/nmap", source="explicit")

        def make_spec(path, networks, timeout):
            order.append("spec")
            captured["path"] = path
            captured["networks"] = tuple(networks)
            captured["timeout"] = timeout
            return object()

        def run(_spec):
            order.append("run")
            return CommandResult(nmap_xml("192.168.1.20", "02:00:00:00:00:20"), "", 0, 7)

        with (
            mock.patch.object(state, "collect_passive_parts", side_effect=collect),
            mock.patch("server.resolve_nmap", side_effect=resolve),
            mock.patch("server.nmap_spec", side_effect=make_spec),
            mock.patch("server.run_command", side_effect=run),
        ):
            snapshot = state.active_discover(request)

        self.assertEqual(order, ["collect", "resolve", "spec", "run"])
        self.assertEqual(captured["networks"], ("192.168.1.0/24", "192.168.1.0/25"))
        self.assertEqual(snapshot.active_discovery.effective_networks, captured["networks"])
        self.assertEqual(snapshot.active_discovery.hosts_reported_up, 1)
        self.assertTrue(any(node.kind.value == "access_point" for node in snapshot.nodes))
        self.assertIs(state.snapshot, snapshot)

    def test_real_active_discover_command_failure_preserves_previous_snapshot(self):
        state = AppState(port=8765, nmap_path=None)
        previous = empty_snapshot()
        state.snapshot = previous
        request = validate_phase_a({"networks": ["192.168.1.0/24"], "operation_timeout_seconds": 30})
        parts = passive_parts(interface_fact("192.168.1.0/24", "en0"))
        with (
            mock.patch.object(state, "collect_passive_parts", return_value=parts),
            mock.patch("server.resolve_nmap", return_value=mock.Mock(path="/opt/homebrew/bin/nmap", source="explicit")),
            mock.patch("server.nmap_spec", return_value=object()),
            mock.patch("server.run_command", side_effect=CommandError("collection_failed", "Nmap failed.")),
            self.assertRaises(CommandError),
        ):
            state.active_discover(request)
        self.assertIs(state.snapshot, previous)

    def test_real_active_discover_rejects_untrusted_nmap_evidence_and_preserves_snapshot(self):
        cases = (nmap_xml("192.168.2.20", "02:00:00:00:00:20"), nmap_xml("192.168.1.20", "not-a-mac"))
        for output in cases:
            with self.subTest(output=output):
                state = AppState(port=8765, nmap_path=None)
                previous = empty_snapshot()
                state.snapshot = previous
                request = validate_phase_a({"networks": ["192.168.1.0/24"], "operation_timeout_seconds": 30})
                parts = passive_parts(interface_fact("192.168.1.0/24", "en0"))
                with (
                    mock.patch.object(state, "collect_passive_parts", return_value=parts),
                    mock.patch("server.resolve_nmap", return_value=mock.Mock(path="/opt/homebrew/bin/nmap", source="explicit")),
                    mock.patch("server.nmap_spec", return_value=object()),
                    mock.patch("server.run_command", return_value=CommandResult(output, "", 0, 7)),
                    self.assertRaises(ValidationError) as raised,
                ):
                    state.active_discover(request)
                self.assertEqual((raised.exception.code, raised.exception.status), ("collection_failed", 500))
                self.assertIs(state.snapshot, previous)

    def test_real_active_discover_classifies_interface_source_failure_before_nmap(self):
        for source_code, expected_status, expected_code in (("collection_failed", 500, "collection_failed"), ("command_timeout", 504, "command_timeout")):
            with self.subTest(source_code=source_code):
                state = AppState(port=8765, nmap_path=None)
                previous = empty_snapshot()
                state.snapshot = previous
                request = validate_phase_a({"networks": ["192.168.1.0/24"], "operation_timeout_seconds": 30})
                with (
                    mock.patch.object(state, "collect_passive_parts", return_value=failed_interface_parts(source_code)),
                    mock.patch("server.resolve_nmap") as resolver,
                    mock.patch("server.run_command") as command,
                    self.assertRaises(ApiError) as raised,
                ):
                    state.active_discover(request)
                self.assertEqual((raised.exception.status, raised.exception.code), (expected_status, expected_code))
                resolver.assert_not_called()
                command.assert_not_called()
                self.assertIs(state.snapshot, previous)

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

    def test_empty_successful_command_outputs_are_not_coherent(self):
        state = AppState(port=8765, nmap_path=None)
        empty = CommandResult("", "", 0, 1)

        def run(spec):
            if spec.kind is CommandKind.WIFI_INTERFACES:
                return CommandResult(hardware_ports(), "", 0, 1)
            if spec.kind is CommandKind.WIFI:
                return CommandResult('{"SPAirPortDataType": []}', "", 0, 1)
            return empty

        with (
            mock.patch("server.platform.system", return_value="Darwin"),
            mock.patch("server.run_command", side_effect=run),
            self.assertRaises(ApiError) as raised,
        ):
            state.collect_passive_parts()
        self.assertEqual(raised.exception.code, "collection_failed")
        self.assertEqual(raised.exception.details["timeout_sources"], [])

    def test_malformed_interface_and_wifi_detail_can_produce_coherent_partial_routes(self):
        state = AppState(port=8765, nmap_path=None)

        def run(spec):
            outputs = {
                CommandKind.INTERFACES: "not ifconfig output\n",
                CommandKind.ROUTES: "Routing tables\n\nInternet:\nDestination Gateway Flags Netif Expire\ndefault 192.0.2.1 UGScg en0\n",
                CommandKind.NEIGHBORS: "",
                CommandKind.WIFI_INTERFACES: hardware_ports(),
                CommandKind.WIFI: "not json",
            }
            return CommandResult(outputs[spec.kind], "", 0, 1)

        with mock.patch("server.platform.system", return_value="Darwin"), mock.patch("server.run_command", side_effect=run):
            parts = state.collect_passive_parts()
        self.assertEqual(len(parts.routes), 1)
        self.assertEqual(parts.wireless_attachments[0].interface, "en0")
        statuses = {source.type: source.status.value for source in parts.sources}
        self.assertEqual(statuses["interfaces"], "failed")
        self.assertEqual(statuses["routes"], "ok")
        self.assertEqual(statuses["wifi_interfaces"], "ok")
        self.assertEqual(statuses["wifi"], "failed")
        self.assertEqual(statuses["wifi_native"], "warning")
        self.assertEqual(dict(parts.failures)["interfaces"], "collection_failed")
        self.assertEqual(dict(parts.failures)["wifi"], "collection_failed")

    def test_wifi_detail_timeout_degrades_without_failing_passive_collection(self):
        state = AppState(port=8765, nmap_path=None)

        def run(spec):
            if spec.kind is CommandKind.INTERFACES:
                return CommandResult("en0: flags=8863<UP,RUNNING> mtu 1500\n    inet 192.168.1.10 netmask 0xffffff00\n", "", 0, 1)
            if spec.kind is CommandKind.ROUTES:
                return CommandResult("Routing tables\n\nInternet:\nDestination Gateway Flags Netif\ndefault 192.168.1.1 UGScg en0\n", "", 0, 1)
            if spec.kind is CommandKind.NEIGHBORS:
                return CommandResult("", "", 0, 1)
            if spec.kind is CommandKind.WIFI_INTERFACES:
                return CommandResult(hardware_ports(), "", 0, 1)
            raise CommandError("command_timeout", "Synthetic profiler timeout.")

        with mock.patch("server.platform.system", return_value="Darwin"), mock.patch("server.run_command", side_effect=run):
            parts = state.collect_passive_parts()
        self.assertEqual(parts.wireless_attachments[0].interface, "en0")
        self.assertFalse(parts.wireless_attachments[0].associated)
        self.assertEqual(dict(parts.failures)["wifi"], "command_timeout")
        self.assertEqual(next(source.status for source in parts.sources if source.type == "wifi_native"), SourceStatusValue.WARNING)

    def test_native_wifi_identity_wins_profiler_and_local_fallback(self):
        fallback = WirelessAttachmentFact(
            "en0",
            "02:aa:bb:cc:dd:55",
            "Configured Wi-Fi",
            associated=False,
            role="relay",
            configured=True,
            evidence_source="local_configuration",
        )
        native_fact = WirelessAttachmentFact(
            "en0",
            "02:aa:bb:cc:dd:42",
            "Native Wi-Fi",
            associated=True,
            hardware_mac_address="02:00:00:00:20:99",
            channel="40",
            rssi_dbm=-35,
            noise_dbm=-90,
            phy_mode="802.11ax",
            transmit_rate_mbps=2401,
            bssid_observed=True,
            evidence_source="wifi_native",
        )
        state = AppState(port=8765, nmap_path=None, wifi_override=fallback)

        def run(spec):
            if spec.kind is CommandKind.INTERFACES:
                return CommandResult(
                    "en0: flags=8863<UP,RUNNING> mtu 1500\n"
                    "    ether 02:00:00:00:10:01\n"
                    "    inet 192.168.1.10 netmask 0xffffff00\n",
                    "", 0, 1,
                )
            if spec.kind is CommandKind.ROUTES:
                return CommandResult("Routing tables\n\nInternet:\nDestination Gateway Flags Netif\ndefault 192.168.1.1 UGScg en0\n", "", 0, 1)
            if spec.kind is CommandKind.NEIGHBORS:
                return CommandResult("", "", 0, 1)
            if spec.kind is CommandKind.WIFI_INTERFACES:
                return CommandResult(hardware_ports(), "", 0, 1)
            return CommandResult(airport_json(bssid="02:aa:bb:cc:dd:01"), "", 0, 1)

        native_state = NativeWiFiCacheState("ready", "Synthetic native evidence.", native_fact)
        with (
            mock.patch("server.platform.system", return_value="Darwin"),
            mock.patch("server.run_command", side_effect=run),
            mock.patch.object(state, "native_wifi_state", return_value=native_state),
        ):
            parts = state.collect_passive_parts()
        wifi = parts.wireless_attachments[0]
        self.assertEqual(wifi.bssid, "02:aa:bb:cc:dd:42")
        self.assertEqual(wifi.ssid, "Native Wi-Fi")
        self.assertEqual(wifi.role, "relay")
        self.assertEqual(wifi.evidence_source, "wifi_native")
        self.assertTrue(wifi.bssid_observed)
        self.assertFalse(wifi.configured)
        self.assertEqual(wifi.hardware_mac_address, "02:00:00:00:20:01", "networksetup hardware MAC remains authoritative")
        self.assertEqual(next(source.status for source in parts.sources if source.type == "wifi_native"), SourceStatusValue.OK)

    def test_local_wifi_fallback_fills_missing_bssid_when_automatic_identity_absent(self):
        fallback = WirelessAttachmentFact(
            "en0",
            "02:aa:bb:cc:dd:55",
            "Configured Wi-Fi",
            associated=False,
            role="relay",
            configured=True,
            evidence_source="local_configuration",
        )
        state = AppState(port=8765, nmap_path=None, wifi_override=fallback)

        def run(spec):
            if spec.kind is CommandKind.INTERFACES:
                return CommandResult("en0: flags=8863<UP,RUNNING> mtu 1500\n    inet 192.168.1.10 netmask 0xffffff00\n", "", 0, 1)
            if spec.kind is CommandKind.ROUTES:
                return CommandResult("Routing tables\n\nInternet:\nDestination Gateway Flags Netif\ndefault 192.168.1.1 UGScg en0\n", "", 0, 1)
            if spec.kind is CommandKind.NEIGHBORS:
                return CommandResult("", "", 0, 1)
            if spec.kind is CommandKind.WIFI_INTERFACES:
                return CommandResult(hardware_ports(), "", 0, 1)
            return CommandResult(airport_json(bssid=None), "", 0, 1)

        with (
            mock.patch("server.platform.system", return_value="Darwin"),
            mock.patch("server.run_command", side_effect=run),
            mock.patch.object(state, "native_wifi_state", return_value=NativeWiFiCacheState("missing", "Synthetic missing helper.")),
        ):
            parts = state.collect_passive_parts()
        wifi = parts.wireless_attachments[0]
        self.assertEqual(wifi.bssid, "02:aa:bb:cc:dd:55")
        self.assertEqual(wifi.role, "relay")
        self.assertTrue(wifi.configured)
        self.assertFalse(wifi.bssid_observed)
        self.assertEqual(wifi.evidence_source, "local_configuration")
        self.assertIn("local_configuration", {source.type for source in parts.sources})

    def test_material_timeouts_return_source_specific_504_details(self):
        state = AppState(port=8765, nmap_path=None)

        def run(spec):
            if spec.kind in {CommandKind.INTERFACES, CommandKind.ROUTES, CommandKind.NEIGHBORS}:
                raise CommandError("command_timeout", "Synthetic timeout.")
            if spec.kind is CommandKind.WIFI_INTERFACES:
                return CommandResult(hardware_ports(), "", 0, 1)
            return CommandResult('{"SPAirPortDataType": []}', "", 0, 1)

        with (
            mock.patch("server.platform.system", return_value="Darwin"),
            mock.patch("server.run_command", side_effect=run),
            self.assertRaises(ApiError) as raised,
        ):
            state.collect_passive_parts()
        self.assertEqual((raised.exception.status, raised.exception.code), (504, "command_timeout"))
        self.assertEqual(raised.exception.details["timeout_sources"], ["interfaces", "neighbors", "routes"])
        self.assertIn("interfaces", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
