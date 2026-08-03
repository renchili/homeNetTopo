from __future__ import annotations

import json
import unittest

from homenettopo.models import Confidence, Edge, EdgeType, ModelError, Node, NodeKind, SourceStatus, SourceStatusValue, TopologySnapshot


class ModelTests(unittest.TestCase):
    def snapshot(self, nodes=(), edges=(), collected_at="2026-08-03T00:00:00Z"):
        return TopologySnapshot("1", "id", collected_at, "passive", "darwin", False, (), (SourceStatus("interfaces", SourceStatusValue.OK),), (), tuple(nodes), tuple(edges))

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


if __name__ == "__main__":
    unittest.main()
