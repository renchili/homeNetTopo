import unittest

from homenettopo.discovery import ActiveHost
from homenettopo.interfaces import InterfaceAddress, InterfaceFact
from homenettopo.models import ActiveDiscoveryMetadata, SourceStatus, SourceStatusValue
from homenettopo.neighbors import NeighborFact
from homenettopo.routes import RouteFact
from homenettopo.topology import build_snapshot


class TopologyTests(unittest.TestCase):
    def parts(self, network="192.168.1.0/24"):
        prefix = int(network.split("/")[1])
        base = network.rsplit(".", 1)[0]
        interfaces = (InterfaceFact("en0", ("UP",), "physical", (InterfaceAddress(f"{base}.10", prefix, network),)),)
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

    def test_same_input_is_deterministic(self):
        kwargs = dict(interfaces=self.parts()[0], routes=self.parts()[1], neighbors=self.parts()[2], sources=self.parts()[3], collected_at="2026-08-03T00:00:00Z")
        self.assertEqual(build_snapshot(**kwargs).to_dict(), build_snapshot(**kwargs).to_dict())

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

    def test_documentation_network_is_visible_but_not_active_eligible(self):
        interfaces, routes, neighbors, sources = self.parts("192.0.2.0/24")
        snapshot = build_snapshot(interfaces=interfaces, routes=routes, neighbors=neighbors, sources=sources, collected_at="2026-08-03T00:00:00Z")
        self.assertFalse(snapshot.networks[0].eligible_for_active_discovery)


if __name__ == "__main__":
    unittest.main()
