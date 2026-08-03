from pathlib import Path
import unittest

from homenettopo.interfaces import parse_ifconfig

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "macos"


class InterfaceParserTests(unittest.TestCase):
    def test_parses_physical_and_virtual_interfaces(self):
        facts = parse_ifconfig((FIXTURES / "ifconfig_multi_interface.txt").read_text())
        by_name = {fact.name: fact for fact in facts}
        self.assertEqual(by_name["en0"].kind, "physical")
        self.assertEqual(by_name["bridge0"].kind, "virtual")
        self.assertEqual(by_name["en0"].addresses[0].network, "192.0.2.0/24")

    def test_parses_utun_point_to_point(self):
        facts = parse_ifconfig((FIXTURES / "ifconfig_utun_point_to_point.txt").read_text())
        self.assertEqual(facts[0].kind, "tunnel")
        self.assertEqual(facts[0].addresses[0].peer, "203.0.113.10")


if __name__ == "__main__":
    unittest.main()
