import ipaddress
import unittest

from homenettopo.discovery import ValidationError, eligible_local_networks, parse_nmap_xml, validate_phase_a, validate_phase_b
from homenettopo.interfaces import InterfaceAddress, InterfaceFact


NMAP_HOST_DISCOVERY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<nmaprun>
  <host><status state="up"/><address addr="192.0.2.20" addrtype="ipv4"/><address addr="02:00:00:00:00:20" addrtype="mac"/></host>
  <host><status state="down"/><address addr="192.0.2.21" addrtype="ipv4"/></host>
</nmaprun>
"""


def interface(network="192.168.1.0/24", kind="physical", name="en0"):
    net = ipaddress.IPv4Network(network)
    address = str(next(net.hosts())) if net.num_addresses > 2 else str(net.network_address)
    return InterfaceFact(name, ("UP",), kind, (InterfaceAddress(address, net.prefixlen, str(net)),))


class DiscoveryValidationTests(unittest.TestCase):
    def request(self, networks=None, timeout=30):
        return validate_phase_a({"networks": networks or ["192.168.1.0/24"], "operation_timeout_seconds": timeout})

    def test_equal_contained_and_duplicate_targets_pass(self):
        self.assertEqual(str(validate_phase_b(self.request(), (interface(),))[0]), "192.168.1.0/24")
        request = self.request(["192.168.1.0/24", "192.168.1.0/25", "192.168.1.0/24"])
        self.assertEqual(tuple(map(str, validate_phase_b(request, (interface(),)))), ("192.168.1.0/24",))

    def test_adjacent_targets_on_separate_local_networks_are_not_merged(self):
        local = (
            interface("192.168.1.0/25", name="en0"),
            interface("192.168.1.128/25", name="en1"),
        )
        request = self.request(["192.168.1.0/25", "192.168.1.128/25"])
        self.assertEqual(
            tuple(map(str, validate_phase_b(request, local))),
            ("192.168.1.0/25", "192.168.1.128/25"),
        )

    def test_contained_targets_owned_by_overlapping_local_networks_remain_separate(self):
        local = (
            interface("192.168.1.0/24", name="en0"),
            interface("192.168.1.0/25", name="en1"),
        )
        request = self.request(["192.168.1.0/24", "192.168.1.0/25"])
        self.assertEqual(
            tuple(map(str, validate_phase_b(request, local))),
            ("192.168.1.0/24", "192.168.1.0/25"),
        )

    def test_supernet_noncanonical_overlap_adjacent_unrelated_and_tunnel_fail(self):
        cases = [
            (["192.168.0.0/23"], interface()),
            (["192.168.1.128/23"], interface()),
            (["192.168.2.0/24"], interface()),
            (["10.0.0.0/24"], interface()),
            (["192.168.1.0/24"], interface(kind="tunnel")),
        ]
        for targets, local in cases:
            with self.subTest(targets=targets), self.assertRaises(ValidationError):
                validate_phase_b(self.request(targets), (local,))

    def test_only_rfc1918_non_tunnel_local_networks_are_eligible(self):
        facts = (
            interface("127.0.0.0/8", name="lo0"),
            interface("169.254.0.0/16", name="en1"),
            interface("240.0.0.0/4", name="en2"),
            interface("192.0.2.0/24", name="en3"),
            interface("192.0.0.0/24", name="en4"),
            interface("198.18.0.0/15", name="en5"),
            interface("10.0.0.0/24", kind="tunnel", name="utun0"),
            interface("192.168.1.0/24", name="en0"),
        )
        self.assertEqual(tuple(map(str, eligible_local_networks(facts))), ("192.168.1.0/24",))

    def test_network_count_address_union_and_timeout_boundaries(self):
        networks = [f"10.0.{index}.0/27" for index in range(32)]
        self.assertEqual(len(self.request(networks, 5).networks), 32)
        self.assertEqual(self.request(["10.0.0.0/22"], 120).operation_timeout_seconds, 120)
        invalid_requests = (
            {"networks": networks + ["10.1.0.0/27"]},
            {"networks": ["10.0.0.0/22", "10.0.4.0/32"]},
            {"networks": ["10.0.0.0/24"], "operation_timeout_seconds": 4},
            {"networks": ["10.0.0.0/24"], "operation_timeout_seconds": 121},
        )
        for invalid in invalid_requests:
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_phase_a(invalid)

    def test_rejects_public_special_non_rfc1918_documentation_ipv6_and_unknown_fields(self):
        bodies = (
            {"networks": ["8.8.8.0/24"]},
            {"networks": ["127.0.0.0/8"]},
            {"networks": ["169.254.0.0/16"]},
            {"networks": ["240.0.0.0/4"]},
            {"networks": ["192.0.0.0/24"]},
            {"networks": ["198.18.0.0/15"]},
            {"networks": ["192.0.2.0/24"]},
            {"networks": ["2001:db8::/64"]},
            {"networks": ["10.0.0.0/24"], "extra": True},
        )
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(ValidationError):
                validate_phase_a(body)

    def test_parses_only_up_hosts_with_addresses(self):
        hosts = parse_nmap_xml(NMAP_HOST_DISCOVERY_XML)
        self.assertEqual([host.address for host in hosts], ["192.0.2.20"])
        self.assertEqual(hosts[0].mac_address, "02:00:00:00:00:20")
        self.assertEqual(parse_nmap_xml("<nmaprun><host><status state='up'/></host></nmaprun>"), ())

    def test_malformed_or_unexpected_xml_fails(self):
        for value in ("<nmaprun>", "<not-nmap/>"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_nmap_xml(value)


if __name__ == "__main__":
    unittest.main()
