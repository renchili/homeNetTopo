import json
import unittest

from homenettopo.interfaces import (
    WirelessAttachmentFact,
    merge_wireless_facts,
    parse_airport_json,
    parse_ifconfig,
    parse_wifi_hardware_ports,
)


IFCONFIG_MULTI_INTERFACE = """\
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    ether 02:00:00:00:10:01
    inet 192.0.2.10 netmask 0xffffff00 broadcast 192.0.2.255
bridge0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    ether 02:00:00:00:10:02
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
            "spairport_channel": "44 (5GHz, 80MHz)",
            "spairport_signal_noise": "-41 dBm / -91 dBm",
            "spairport_rssi": "-41 dBm",
            "spairport_noise": "-91 dBm",
            "spairport_phymode": "802.11ax",
            "spairport_transmit_rate": "1200",
        }
    else:
        interface["spairport_current_network_information"] = current_marker
    return json.dumps({"SPAirPortDataType": [{"spairport_airport_interfaces": [interface]}]})


class InterfaceParserTests(unittest.TestCase):
    def test_parses_physical_virtual_addresses_and_current_macs(self):
        facts = parse_ifconfig(IFCONFIG_MULTI_INTERFACE)
        by_name = {fact.name: fact for fact in facts}
        self.assertEqual(by_name["en0"].kind, "physical")
        self.assertEqual(by_name["bridge0"].kind, "virtual")
        self.assertEqual(by_name["en0"].addresses[0].network, "192.0.2.0/24")
        self.assertEqual(by_name["en0"].current_mac_address, "02:00:00:00:10:01")
        self.assertEqual(by_name["bridge0"].current_mac_address, "02:00:00:00:10:02")

    def test_parses_utun_point_to_point(self):
        facts = parse_ifconfig(IFCONFIG_UTUN_POINT_TO_POINT)
        self.assertEqual(facts[0].kind, "tunnel")
        self.assertEqual(facts[0].addresses[0].peer, "203.0.113.10")
        self.assertIsNone(facts[0].current_mac_address)

    def test_empty_output_is_empty_but_unrecognized_output_fails(self):
        self.assertEqual(parse_ifconfig(""), ())
        with self.assertRaises(ValueError):
            parse_ifconfig("not ifconfig output\n")

    def test_wifi_hardware_ports_identify_adapter_hardware_mac_only(self):
        facts = parse_wifi_hardware_ports(NETWORKSETUP_HARDWARE_PORTS)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].interface, "en0")
        self.assertFalse(facts[0].associated)
        self.assertIsNone(facts[0].bssid)
        self.assertEqual(facts[0].hardware_mac_address, "02:00:00:00:00:01")

    def test_wifi_hardware_ports_accept_legacy_airport_label_and_reject_drift(self):
        legacy = "Hardware Port: AirPort\nDevice: en1\nEthernet Address: 02:00:00:00:00:11\n"
        fact = parse_wifi_hardware_ports(legacy)[0]
        self.assertEqual(fact.interface, "en1")
        self.assertEqual(fact.hardware_mac_address, "02:00:00:00:00:11")
        with self.assertRaises(ValueError):
            parse_wifi_hardware_ports("unexpected output\n")

    def test_airport_parser_keeps_current_radio_metrics_and_normalizes_bssid(self):
        fact = parse_airport_json(airport_payload())[0]
        self.assertEqual(fact.interface, "en0")
        self.assertEqual(fact.bssid, "02:aa:bb:cc:dd:01")
        self.assertEqual(fact.ssid, "Synthetic Wi-Fi")
        self.assertEqual(fact.channel, "44 (5GHz, 80MHz)")
        self.assertEqual(fact.rssi_dbm, -41)
        self.assertEqual(fact.noise_dbm, -91)
        self.assertEqual(fact.phy_mode, "802.11ax")
        self.assertEqual(fact.transmit_rate_mbps, 1200)
        self.assertTrue(fact.bssid_observed)
        self.assertTrue(fact.associated)

    def test_airport_parser_preserves_redacted_association_without_guessing(self):
        fact = parse_airport_json(airport_payload("<redacted>"))[0]
        self.assertIsNone(fact.bssid)
        self.assertFalse(fact.identified)
        self.assertFalse(fact.bssid_observed)
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

    def test_merge_preserves_hardware_mac_and_prefers_automatic_bssid(self):
        media = parse_wifi_hardware_ports(NETWORKSETUP_HARDWARE_PORTS)
        detailed = parse_airport_json(airport_payload())
        fallback = (
            WirelessAttachmentFact(
                "en0",
                "02:aa:bb:cc:dd:55",
                "Configured Wi-Fi",
                associated=False,
                role="relay",
                configured=True,
            ),
        )
        merged = merge_wireless_facts(media, fallback, detailed)[0]
        self.assertEqual(merged.hardware_mac_address, "02:00:00:00:00:01")
        self.assertEqual(merged.bssid, "02:aa:bb:cc:dd:01")
        self.assertEqual(merged.ssid, "Synthetic Wi-Fi")
        self.assertEqual(merged.role, "relay")
        self.assertTrue(merged.bssid_observed)
        self.assertFalse(merged.configured)

    def test_configured_bssid_fills_only_missing_automatic_identity(self):
        media = parse_wifi_hardware_ports(NETWORKSETUP_HARDWARE_PORTS)
        fallback = (
            WirelessAttachmentFact(
                "en0",
                "02:aa:bb:cc:dd:55",
                "Configured Wi-Fi",
                associated=False,
                role="relay",
                configured=True,
            ),
        )
        merged = merge_wireless_facts(media, fallback)[0]
        self.assertEqual(merged.bssid, "02:aa:bb:cc:dd:55")
        self.assertEqual(merged.hardware_mac_address, "02:00:00:00:00:01")
        self.assertEqual(merged.role, "relay")
        self.assertTrue(merged.configured)
        self.assertFalse(merged.bssid_observed)

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
