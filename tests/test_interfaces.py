import json
import unittest

from homenettopo.interfaces import (
    merge_wireless_facts,
    parse_airport_json,
    parse_ifconfig,
    parse_wifi_hardware_ports,
)


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

NETWORKSETUP_HARDWARE_PORTS = """\
Hardware Port: Ethernet
Device: en5
Ethernet Address: 02:00:00:00:00:05

Hardware Port: Wi-Fi
Device: en0
Ethernet Address: 02:00:00:00:00:01

Hardware Port: Thunderbolt Bridge
Device: bridge0
Ethernet Address: 02:00:00:00:00:02
"""


def airport_payload(bssid="02:AA:BB:CC:DD:01", current_marker=object()):
    interface = {
        "_name": "en0",
        "spairport_airport_other_local_wireless_networks": [{
            "_name": "Nearby network",
            "spairport_bssid": "02:aa:bb:cc:dd:99",
        }],
    }
    if current_marker.__class__ is object:
        interface["spairport_current_network_information"] = {
            "_name": "Synthetic Wi-Fi",
            "spairport_bssid": bssid,
            "spairport_channel": "44",
        }
    else:
        interface["spairport_current_network_information"] = current_marker
    return json.dumps({
        "SPAirPortDataType": [{
            "spairport_airport_interfaces": [interface],
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

    def test_wifi_hardware_ports_identify_only_wifi_bsd_interfaces(self):
        facts = parse_wifi_hardware_ports(NETWORKSETUP_HARDWARE_PORTS)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].interface, "en0")
        self.assertFalse(facts[0].associated)
        self.assertIsNone(facts[0].bssid)

    def test_wifi_hardware_ports_accept_legacy_airport_label_and_reject_drift(self):
        legacy = "Hardware Port: AirPort\nDevice: en1\nEthernet Address: 02:00:00:00:00:01\n"
        self.assertEqual(parse_wifi_hardware_ports(legacy)[0].interface, "en1")
        with self.assertRaises(ValueError):
            parse_wifi_hardware_ports("unexpected output\n")

    def test_airport_parser_keeps_only_current_association_and_normalizes_bssid(self):
        facts = parse_airport_json(airport_payload())
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].interface, "en0")
        self.assertEqual(facts[0].bssid, "02:aa:bb:cc:dd:01")
        self.assertEqual(facts[0].ssid, "Synthetic Wi-Fi")
        self.assertTrue(facts[0].identified)
        self.assertTrue(facts[0].associated)

    def test_airport_parser_preserves_redacted_association_without_guessing(self):
        fact = parse_airport_json(airport_payload("<redacted>"))[0]
        self.assertIsNone(fact.bssid)
        self.assertFalse(fact.identified)
        self.assertTrue(fact.associated)

    def test_airport_parser_accepts_string_current_network(self):
        fact = parse_airport_json(airport_payload(current_marker="Synthetic Wi-Fi"))[0]
        self.assertEqual(fact.interface, "en0")
        self.assertEqual(fact.ssid, "Synthetic Wi-Fi")
        self.assertIsNone(fact.bssid)
        self.assertTrue(fact.associated)

    def test_airport_parser_retains_wifi_interface_when_current_details_are_missing(self):
        payload = json.loads(airport_payload())
        del payload["SPAirPortDataType"][0]["spairport_airport_interfaces"][0]["spairport_current_network_information"]
        fact = parse_airport_json(json.dumps(payload))[0]
        self.assertEqual(fact.interface, "en0")
        self.assertIsNone(fact.ssid)
        self.assertIsNone(fact.bssid)
        self.assertFalse(fact.associated)

    def test_media_fallback_survives_profiler_failure_and_details_win_when_available(self):
        media = parse_wifi_hardware_ports(NETWORKSETUP_HARDWARE_PORTS)
        self.assertEqual(merge_wireless_facts(media), media)
        detailed = parse_airport_json(airport_payload())
        merged = merge_wireless_facts(media, detailed)
        self.assertEqual(merged[0].bssid, "02:aa:bb:cc:dd:01")
        self.assertTrue(merged[0].associated)

    def test_airport_parser_tolerates_only_a_trailing_profiler_prompt_marker(self):
        self.assertEqual(parse_airport_json(airport_payload() + "%")[0].interface, "en0")
        with self.assertRaises(ValueError):
            parse_airport_json(airport_payload() + "unexpected")

    def test_airport_parser_rejects_invalid_or_wrong_root(self):
        for value in ("not json", "{}"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_airport_json(value)


if __name__ == "__main__":
    unittest.main()
