import unittest

from homenettopo.discovery import ActiveHost
from homenettopo.interfaces import InterfaceAddress, InterfaceFact, WirelessAttachmentFact
from homenettopo.models import ActiveDiscoveryMetadata, SourceStatus, SourceStatusValue, WarningItem
from homenettopo.neighbors import NeighborFact
from homenettopo.routes import RouteFact
from homenettopo.topology import build_snapshot


class TopologyTests(unittest.TestCase):
    def parts(self, network="192.168.1.0/24", *, interface_kind="physical", interface_name="en0"):
        net_prefix, prefix = network.split("/")
        base = net_prefix.rsplit(".", 1)[0]
        interfaces = (
            InterfaceFact(interface_name, ("UP",), interface_kind, (InterfaceAddress(f"{base}.10", int(prefix), network),)),
        )
        routes = (RouteFact("0.0.0.0/0", f"{base}.1", ("U", "G"), interface_name, True),)
        neighbors = (NeighborFact(f"{base}.20", "02:00:00:00:00:20", interface_name, None, True),)
        sources = (
            SourceStatus("interfaces", SourceStatusValue.OK),
            SourceStatus("routes", SourceStatusValue.OK),
            SourceStatus("neighbors", SourceStatusValue.OK),
        )
        return interfaces, routes, neighbors, sources

    def test_builds_expected_kinds_and_keeps_peers_out_of_gateway_path(self):
        interfaces, routes, neighbors, sources = self.parts()
        snapshot = build_snapshot(
            interfaces=interfaces,
            routes=routes,
            neighbors=neighbors,
            sources=sources,
            collected_at="2026-08-03T00:00:00Z",
        )
        kinds = {node.kind.value for node in snapshot.nodes}
        self.assertTrue({"local_host", "interface", "link_boundary", "subnet", "gateway", "device", "upstream_boundary"}.issubset(kinds))
        membership = next(edge for edge in snapshot.edges if edge.type.value == "member_of")
        self.assertFalse(membership.observed)
        self.assertEqual(membership.source, "device:192.168.1.20")
        self.assertFalse(any(edge.source == membership.source and edge.type.value in {"interface_reaches_link", "attachment_reaches_gateway"} for edge in snapshot.edges))
        self.assertIn("address_membership", {source.type for source in snapshot.sources})
        self.assertIn("route_inference", {source.type for source in snapshot.sources})
        self.assertIn("link_path_inference", {source.type for source in snapshot.sources})

    def test_local_addresses_are_host_identity_not_peer_devices(self):
        interfaces, routes, _, sources = self.parts()
        local_address = interfaces[0].addresses[0].address
        metadata = ActiveDiscoveryMetadata(("192.168.1.0/24",), ("192.168.1.0/24",), True, 10, 2, 30)
        snapshot = build_snapshot(
            interfaces=interfaces,
            routes=routes,
            neighbors=(
                NeighborFact(local_address, "02:00:00:00:00:10", "en0", "this-mac.local", True),
                NeighborFact("192.168.1.20", "02:00:00:00:00:20", "en0", None, True),
            ),
            sources=(
                *sources,
                SourceStatus("wifi_interfaces", SourceStatusValue.OK),
                SourceStatus("wifi", SourceStatusValue.FAILED, "Collected output could not be parsed."),
            ),
            warnings=(WarningItem("wifi_parse_failed", "Wifi evidence could not be parsed.", "wifi"),),
            wireless_attachments=(WirelessAttachmentFact("en0", None, None, associated=False),),
            active_hosts=(ActiveHost(local_address), ActiveHost("192.168.1.30")),
            active_metadata=metadata,
            collected_at="2026-08-03T00:00:00Z",
        )

        local_host = next(node for node in snapshot.nodes if node.kind.value == "local_host")
        device_ids = {node.id for node in snapshot.nodes if node.kind.value == "device"}
        source_statuses = {source.type: source.status for source in snapshot.sources}

        self.assertIn(local_address, local_host.addresses)
        self.assertNotIn(f"device:{local_address}", device_ids)
        self.assertEqual(device_ids, {"device:192.168.1.20", "device:192.168.1.30"})
        self.assertEqual(snapshot.active_discovery.hosts_reported_up, 1)
        self.assertFalse(snapshot.partial)
        self.assertEqual(source_statuses["wifi"], SourceStatusValue.WARNING)
        self.assertFalse(any(warning.source in {"wifi", "wifi_interfaces"} for warning in snapshot.warnings))

    def test_wifi_bssid_creates_observed_ap_then_inferred_gateway_path(self):
        interfaces, routes, neighbors, sources = self.parts()
        attachments = (WirelessAttachmentFact("en0", "02:00:00:00:00:01", "Synthetic Wi-Fi"),)
        snapshot = build_snapshot(
            interfaces=interfaces,
            routes=routes,
            neighbors=neighbors,
            wireless_attachments=attachments,
            sources=(*sources, SourceStatus("wifi", SourceStatusValue.OK)),
            collected_at="2026-08-03T00:00:00Z",
        )
        access_point = next(node for node in snapshot.nodes if node.kind.value == "access_point")
        self.assertEqual(access_point.mac_addresses, ("02:00:00:00:00:01",))
        self.assertEqual(access_point.properties["ssid"], "Synthetic Wi-Fi")
        associated = next(edge for edge in snapshot.edges if edge.type.value == "interface_associated_with")
        toward_gateway = next(edge for edge in snapshot.edges if edge.type.value == "attachment_reaches_gateway")
        self.assertTrue(associated.observed)
        self.assertEqual(associated.target, access_point.id)
        self.assertFalse(toward_gateway.observed)
        self.assertEqual(toward_gateway.source, access_point.id)
        self.assertEqual(access_point.properties["physical_identity_with_gateway"], "unknown")
        self.assertFalse(any(node.kind.value == "link_boundary" for node in snapshot.nodes))

    def test_redacted_wifi_identity_is_visible_without_guessing(self):
        interfaces, routes, neighbors, sources = self.parts()
        snapshot = build_snapshot(
            interfaces=interfaces,
            routes=routes,
            neighbors=neighbors,
            wireless_attachments=(WirelessAttachmentFact("en0", None, None),),
            sources=(*sources, SourceStatus("wifi", SourceStatusValue.OK)),
            collected_at="2026-08-03T00:00:00Z",
        )
        access_point = next(node for node in snapshot.nodes if node.kind.value == "access_point")
        self.assertEqual(access_point.mac_addresses, ())
        self.assertEqual(access_point.properties["identity_source"], "association_without_bssid")
        self.assertTrue(access_point.properties["association_observed"])
        self.assertIn("identity unavailable", access_point.label)

    def test_wifi_media_only_evidence_does_not_fall_back_to_unknown_l2_transit(self):
        interfaces, routes, neighbors, sources = self.parts()
        snapshot = build_snapshot(
            interfaces=interfaces,
            routes=routes,
            neighbors=neighbors,
            wireless_attachments=(WirelessAttachmentFact("en0", None, None, associated=False),),
            sources=(*sources, SourceStatus("wifi_interfaces", SourceStatusValue.OK)),
            collected_at="2026-08-03T00:00:00Z",
        )
        access_point = next(node for node in snapshot.nodes if node.kind.value == "access_point")
        associated = next(edge for edge in snapshot.edges if edge.type.value == "interface_associated_with")
        self.assertEqual(access_point.interface_names, ("en0",))
        self.assertEqual(access_point.properties["identity_source"], "wifi_interface_and_default_route")
        self.assertFalse(access_point.properties["association_observed"])
        self.assertFalse(associated.observed)
        self.assertEqual(associated.evidence[0].source, "wifi_interfaces")
        self.assertEqual(associated.properties["inference"], "wifi_interface_plus_default_route")
        self.assertFalse(any(node.kind.value == "link_boundary" for node in snapshot.nodes))
        self.assertNotEqual(access_point.label, "Intermediate L2 path unknown")

    def test_same_observed_mac_can_link_ap_and_gateway_identity(self):
        interfaces, routes, _, sources = self.parts()
        shared_mac = "02:00:00:00:00:01"
        snapshot = build_snapshot(
            interfaces=interfaces,
            routes=routes,
            neighbors=(NeighborFact("192.168.1.1", shared_mac, "en0", None, True),),
            wireless_attachments=(WirelessAttachmentFact("en0", shared_mac, "Synthetic Wi-Fi"),),
            sources=(*sources, SourceStatus("wifi", SourceStatusValue.OK)),
            collected_at="2026-08-03T00:00:00Z",
        )
        access_point = next(node for node in snapshot.nodes if node.kind.value == "access_point")
        path_edge = next(edge for edge in snapshot.edges if edge.type.value == "attachment_reaches_gateway")
        self.assertEqual(access_point.properties["physical_identity_with_gateway"], "same_mac")
        self.assertEqual(path_edge.properties["physical_identity_relation"], "same_mac")

    def test_tunnel_default_route_skips_l2_attachment_nodes(self):
        interfaces, routes, neighbors, sources = self.parts("100.64.0.2/32", interface_kind="tunnel", interface_name="utun4")
        routes = (RouteFact("0.0.0.0/0", "100.64.0.2", ("U", "G"), "utun4", True),)
        snapshot = build_snapshot(
            interfaces=interfaces,
            routes=routes,
            neighbors=neighbors,
            sources=sources,
            collected_at="2026-08-03T00:00:00Z",
        )
        self.assertFalse(any(node.kind.value in {"access_point", "link_boundary"} for node in snapshot.nodes))
        edge = next(edge for edge in snapshot.edges if edge.type.value == "interface_reaches_gateway")
        self.assertEqual(edge.source, "interface:utun4")
        self.assertEqual(edge.properties["path_kind"], "tunnel")

    def test_specific_route_creates_routes_to_boundary(self):
        interfaces, default_routes, neighbors, sources = self.parts()
        routes = (*default_routes, RouteFact("10.10.0.0/16", "192.168.1.1", ("U", "G"), "en0", False))
        snapshot = build_snapshot(
            interfaces=interfaces,
            routes=routes,
            neighbors=neighbors,
            sources=sources,
            collected_at="2026-08-03T00:00:00Z",
        )
        boundary = next(node for node in snapshot.nodes if node.label == "10.10.0.0/16")
        route_edge = next(edge for edge in snapshot.edges if edge.type.value == "routes_to")
        gateway = next(node for node in snapshot.nodes if node.kind.value == "gateway")
        self.assertEqual(route_edge.target, boundary.id)
        self.assertFalse(route_edge.observed)
        self.assertEqual(route_edge.evidence[0].source, "route_inference")
        self.assertTrue(gateway.properties["default_gateway"], "non-default routes must not erase default-gateway status")

    def test_same_input_is_deterministic(self):
        kwargs = dict(interfaces=self.parts()[0], routes=self.parts()[1], neighbors=self.parts()[2], sources=self.parts()[3], collected_at="2026-08-03T00:00:00Z")
        self.assertEqual(build_snapshot(**kwargs).to_dict(), build_snapshot(**kwargs).to_dict())

    def test_snapshot_id_changes_when_snapshot_content_changes(self):
        kwargs = dict(interfaces=self.parts()[0], routes=self.parts()[1], neighbors=self.parts()[2], sources=self.parts()[3], collected_at="2026-08-03T00:00:00Z")
        baseline = build_snapshot(**kwargs)
        warned = build_snapshot(**kwargs, warnings=(WarningItem("test_warning", "Synthetic warning", "test"),))
        self.assertNotEqual(baseline.snapshot_id, warned.snapshot_id)

    def test_active_evidence_supplements_passive(self):
        metadata = ActiveDiscoveryMetadata(("192.168.1.0/24",), ("192.168.1.0/24",), True, 10, 1, 30)
        snapshot = build_snapshot(
            interfaces=self.parts()[0],
            routes=self.parts()[1],
            neighbors=(),
            sources=self.parts()[3],
            active_hosts=(ActiveHost("192.168.1.30"),),
            active_metadata=metadata,
            collected_at="2026-08-03T00:00:00Z",
        )
        self.assertEqual(snapshot.mode, "active")
        self.assertTrue(any(node.id == "device:192.168.1.30" for node in snapshot.nodes))

    def test_gateway_and_neighbor_evidence_merge_into_one_gateway_node(self):
        interfaces, routes, _, sources = self.parts()
        neighbors = (NeighborFact("192.168.1.1", "02:00:00:00:00:01", "en0", "router.local", True),)
        snapshot = build_snapshot(interfaces=interfaces, routes=routes, neighbors=neighbors, sources=sources, collected_at="2026-08-03T00:00:00Z")
        gateway = next(node for node in snapshot.nodes if node.id == "gateway:192.168.1.1")
        self.assertEqual(gateway.label, "router.local")
        self.assertEqual(gateway.mac_addresses, ("02:00:00:00:00:01",))
        self.assertFalse(any(node.id == "device:192.168.1.1" for node in snapshot.nodes))

    def test_special_and_documentation_networks_are_visible_but_not_active_eligible(self):
        cases = ("192.0.2.0/24", "127.0.0.0/8", "169.254.0.0/16")
        for network in cases:
            with self.subTest(network=network):
                interfaces, routes, neighbors, sources = self.parts(network)
                snapshot = build_snapshot(interfaces=interfaces, routes=routes, neighbors=neighbors, sources=sources, collected_at="2026-08-03T00:00:00Z")
                self.assertFalse(snapshot.networks[0].eligible_for_active_discovery)


if __name__ == "__main__":
    unittest.main()
