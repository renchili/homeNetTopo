from __future__ import annotations

import unittest

from homenettopo.models import Confidence, Edge, EdgeType, ModelError, Node, NodeKind, TopologySnapshot


class ModelTests(unittest.TestCase):
    def snapshot(self, nodes=(), edges=()):
        return TopologySnapshot("1", "id", "2026-08-03T00:00:00Z", "passive", "darwin", False, (), (), (), tuple(nodes), tuple(edges))

    def test_serializes_enums(self):
        node = Node("local", NodeKind.LOCAL_HOST, "Mac", confidence=Confidence.HIGH)
        self.assertEqual(self.snapshot((node,)).to_dict()["nodes"][0]["kind"], "local_host")

    def test_rejects_duplicate_node_ids(self):
        node = Node("same", NodeKind.DEVICE, "One")
        with self.assertRaises(ModelError):
            self.snapshot((node, node)).validate()

    def test_rejects_missing_edge_endpoint(self):
        node = Node("a", NodeKind.DEVICE, "A")
        edge = Edge("edge", "a", "missing", EdgeType.MEMBER_OF, False, Confidence.MEDIUM)
        with self.assertRaises(ModelError):
            self.snapshot((node,), (edge,)).validate()


if __name__ == "__main__":
    unittest.main()
