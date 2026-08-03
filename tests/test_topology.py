import unittest

from homenettopo.discovery import ActiveHost
from homenettopo.interfaces import InterfaceAddress, InterfaceFact
from homenettopo.models import ActiveDiscoveryMetadata, SourceStatus, SourceStatusValue, WarningItem
from homenettopo.neighbors import NeighborFact
from homenettopo.routes import RouteFact
from homenettopo.topology import build_snapshot


class TopologyTests(unittest.TestCase):
    def parts(self, network="192.168.1.0/24"):
        net_prefix, prefix = network.split("/")
        base = net_prefix.rsplit(".", 1)[0]
        interfaces = (InterfaceFact("en0", ("UP",), "physical", (InterfaceAddress(f"{base}.10", int(prefix), network),)),)
        routes = (RouteFact("0.0.0.0/0", f"{base}.1", ("U", "G"), "en0", True),)
        neighbors = (NeighborFact(f"{base}.20", "02:00:00:00:00:20", "en0", None, True),)
        sources = (SourceStatus("interfaces", SourceStatusValue.OK), SourceStatus("routes", SourceStatusValue.OK), SourceStatus("neighbors", SourceStatusValue.OK))
        return interfaces, routes, neighbors, sources

    def test_builds_expected_kinds_and_inferred_membership(self):
        snapshot = build_snapshot(interfaces=self.parts()[0], routes=self.parts()[1], neighbors=self.parts()[2], sources=self.parts()[3], collected_at="2026-08-03T00:00:00Z")
        kinds = {node.kind.value for node in snapshot.nodes}
        self.assertTrue({"local_host", "interface", "subnet", "gateway", "device", "upstream_boundary"}.issubset(kinds))
        membership = next(edge for edge in snapshot.edges if edge.type.value == "member_of")
        self.assertFalse(membership.observed)
        self.assertIn("address_membership", {source.type for source in snapshot.sources})
        self.assertIn("route_inference", {source.type for source in snapshot.sources})

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
        self.assertEqual(route_edge.target, boundary.id)
        self.assertFalse(route_edge.observed)
        self.assertEqual(route_edge.evidence[0].source, "route_inference")

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
        snapshot = build_snapshot(interfaces=self.parts()[0], routes=self.parts()[1], neighbors=(), sources=self.parts()[3], active_hosts=(ActiveHost("192.168.1.30"),), active_metadata=metadata, collected_at="2026-08-03T00:00:00Z")
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
