import json
import unittest

from homenettopo.interfaces import parse_airport_json, parse_ifconfig


IFCONFIG_MULTI_INTERFACE = """\
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    inet 192.0.2.10 netmask 0xffffff00 broadcast 192.0.2.255
bridge0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    inet 198.51.100.1 netmask 0xffffff00 broadcast 198.51.100.255
"""

IFCONFIG_UTUN_POINT_TO_POINT = """\
utun0: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1380
    inet 203.0.113.9 --> 203.0.113.10 netmask 0xffffffff
"""


def airport_payload(bssid="02:AA:BB:CC:DD:01"):
    return json.dumps({
        "SPAirPortDataType": [{
            "spairport_airport_interfaces": [{
                "_name": "en0",
                "spairport_current_network_information": {
                    "_name": "Synthetic Wi-Fi",
                    "spairport_bssid": bssid,
                    "spairport_channel": "44",
                },
                "spairport_airport_other_local_wireless_networks": [{
                    "_name": "Nearby network",
                    "spairport_bssid": "02:aa:bb:cc:dd:99",
                }],
            }],
        }],
    })


class InterfaceParserTests(unittest.TestCase):
    def test_parses_physical_and_virtual_interfaces(self):
        facts = parse_ifconfig(IFCONFIG_MULTI_INTERFACE)
        by_name = {fact.name: fact for fact in facts}
        self.assertEqual(by_name["en0"].kind, "physical")
        self.assertEqual(by_name["bridge0"].kind, "virtual")
        self.assertEqual(by_name["en0"].addresses[0].network, "192.0.2.0/24")

    def test_parses_utun_point_to_point(self):
        facts = parse_ifconfig(IFCONFIG_UTUN_POINT_TO_POINT)
        self.assertEqual(facts[0].kind, "tunnel")
        self.assertEqual(facts[0].addresses[0].peer, "203.0.113.10")

    def test_empty_output_is_empty_but_unrecognized_output_fails(self):
        self.assertEqual(parse_ifconfig(""), ())
        with self.assertRaises(ValueError):
            parse_ifconfig("not ifconfig output\n")

    def test_airport_parser_keeps_only_current_association_and_normalizes_bssid(self):
        facts = parse_airport_json(airport_payload())
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].interface, "en0")
        self.assertEqual(facts[0].bssid, "02:aa:bb:cc:dd:01")
        self.assertEqual(facts[0].ssid, "Synthetic Wi-Fi")
        self.assertTrue(facts[0].identified)

    def test_airport_parser_preserves_redacted_association_without_guessing(self):
        fact = parse_airport_json(airport_payload("<redacted>"))[0]
        self.assertIsNone(fact.bssid)
        self.assertFalse(fact.identified)

    def test_airport_parser_rejects_invalid_or_wrong_root(self):
        for value in ("not json", "{}"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_airport_json(value)


if __name__ == "__main__":
    unittest.main()
