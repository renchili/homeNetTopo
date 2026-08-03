import unittest

from homenettopo.neighbors import parse_neighbors


ARP_COMPLETE = """\
router.example (192.0.2.1) at 02:00:00:00:00:01 on en0 ifscope [ethernet]
device.example (192.0.2.20) at 02:00:00:00:00:20 on en0 ifscope [ethernet]
"""

ARP_INCOMPLETE = "? (192.0.2.99) at (incomplete) on en0 ifscope [ethernet]\n"


class NeighborParserTests(unittest.TestCase):
    def test_parses_complete_entries_and_name(self):
        neighbors = parse_neighbors(ARP_COMPLETE)
        self.assertEqual(neighbors[0].name, "router.example")
        self.assertEqual(neighbors[0].mac_address, "02:00:00:00:00:01")
        self.assertTrue(neighbors[0].complete)

    def test_retains_incomplete_without_fabricating_mac(self):
        neighbor = parse_neighbors(ARP_INCOMPLETE)[0]
        self.assertFalse(neighbor.complete)
        self.assertIsNone(neighbor.mac_address)

    def test_empty_output_is_empty_but_unrecognized_entries_fail(self):
        self.assertEqual(parse_neighbors(""), ())
        with self.assertRaises(ValueError):
            parse_neighbors("not arp output\n")


if __name__ == "__main__":
    unittest.main()
