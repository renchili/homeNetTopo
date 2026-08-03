from __future__ import annotations

import json
import unittest

from homenettopo.models import (
    ActiveDiscoveryMetadata,
    Confidence,
    Edge,
    EdgeType,
    Evidence,
    ModelError,
    NetworkDescriptor,
    Node,
    NodeKind,
    SourceStatus,
    SourceStatusValue,
    TopologySnapshot,
)


class ModelTests(unittest.TestCase):
    def snapshot(self, nodes=(), edges=(), networks=(), sources=None, collected_at="2026-08-03T00:00:00Z"):
        source_items = (SourceStatus("interfaces", SourceStatusValue.OK),) if sources is None else tuple(sources)
        return TopologySnapshot("1", "id", collected_at, "passive", "darwin", False, (), source_items, tuple(networks), tuple(nodes), tuple(edges))

    def test_serializes_nested_enums_as_json_and_omits_inactive_metadata(self):
        node = Node("local", NodeKind.LOCAL_HOST, "Mac", confidence=Confidence.HIGH)
        payload = self.snapshot((node,)).to_dict()
        self.assertEqual(payload["nodes"][0]["kind"], "local_host")
        self.assertEqual(payload["sources"][0]["status"], "ok")
        self.assertNotIn("active_discovery", payload)
        json.dumps(payload)

    def test_rejects_duplicate_node_ids(self):
        node = Node("same", NodeKind.DEVICE, "One")
        with self.assertRaises(ModelError):
            self.snapshot((node, node)).validate()

    def test_rejects_missing_edge_endpoint(self):
        node = Node("a", NodeKind.DEVICE, "A")
        edge = Edge("edge", "a", "missing", EdgeType.MEMBER_OF, False, Confidence.MEDIUM)
        with self.assertRaises(ModelError):
            self.snapshot((node,), (edge,)).validate()

    def test_rejects_non_utc_or_malformed_timestamp(self):
        for value in ("2026-08-03T00:00:00+08:00", "not-a-time"):
            with self.subTest(value=value), self.assertRaises(ModelError):
                self.snapshot(collected_at=value).validate()

    def test_rejects_noncanonical_network_and_wrong_address_count(self):
        cases = (
            NetworkDescriptor("192.168.1.1/24", "en0", "physical", True, "eligible", 256),
            NetworkDescriptor("192.168.1.0/24", "en0", "physical", True, "eligible", 255),
        )
        for network in cases:
            with self.subTest(network=network), self.assertRaises(ModelError):
                self.snapshot(networks=(network,)).validate()

    def test_rejects_invalid_addresses_macs_and_evidence_timestamps(self):
        cases = (
            Node("bad-address", NodeKind.DEVICE, "Bad", addresses=("999.1.1.1",)),
            Node("bad-mac", NodeKind.DEVICE, "Bad", mac_addresses=("AA:BB:CC:DD:EE:FF",)),
            Node("bad-evidence", NodeKind.DEVICE, "Bad", evidence=(Evidence("test", "bad", "yesterday"),)),
        )
        for node in cases:
            with self.subTest(node=node), self.assertRaises(ModelError):
                self.snapshot(nodes=(node,)).validate()

    def test_rejects_duplicate_source_types(self):
        sources = (
            SourceStatus("interfaces", SourceStatusValue.OK),
            SourceStatus("interfaces", SourceStatusValue.FAILED),
        )
        with self.assertRaises(ModelError):
            self.snapshot(sources=sources).validate()

    def test_active_metadata_enforces_fixed_command_contract(self):
        metadata = ActiveDiscoveryMetadata(("192.168.1.0/24",), ("192.168.1.0/24",), True, 1, 1, 30, host_timeout_seconds=6)
        snapshot = TopologySnapshot("1", "id", "2026-08-03T00:00:00Z", "active", "darwin", False, (), (), (), (), (), metadata)
        with self.assertRaises(ModelError):
            snapshot.validate()


if __name__ == "__main__":
    unittest.main()
