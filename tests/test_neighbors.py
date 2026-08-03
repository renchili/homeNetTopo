from pathlib import Path
import unittest

from homenettopo.neighbors import parse_neighbors

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "macos"


class NeighborParserTests(unittest.TestCase):
    def test_parses_complete_entries_and_name(self):
        neighbors = parse_neighbors((FIXTURES / "arp_all.txt").read_text())
        self.assertEqual(neighbors[0].name, "router.example")
        self.assertEqual(neighbors[0].mac_address, "02:00:00:00:00:01")
        self.assertTrue(neighbors[0].complete)

    def test_retains_incomplete_without_fabricating_mac(self):
        neighbor = parse_neighbors((FIXTURES / "arp_incomplete.txt").read_text())[0]
        self.assertFalse(neighbor.complete)
        self.assertIsNone(neighbor.mac_address)


if __name__ == "__main__":
    unittest.main()
