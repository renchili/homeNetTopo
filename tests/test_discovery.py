from pathlib import Path
import ipaddress
import unittest

from homenettopo.discovery import ValidationError, parse_nmap_xml, validate_phase_a, validate_phase_b
from homenettopo.interfaces import InterfaceAddress, InterfaceFact

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "macos"


def interface(network="192.168.1.0/24", kind="physical"):
    net = ipaddress.IPv4Network(network)
    address = str(next(net.hosts()))
    return InterfaceFact("en0", ("UP",), kind, (InterfaceAddress(address, net.prefixlen, str(net)),))


class DiscoveryValidationTests(unittest.TestCase):
    def request(self, networks=None, timeout=30):
        return validate_phase_a({"networks": networks or ["192.168.1.0/24"], "operation_timeout_seconds": timeout})

    def test_equal_contained_and_collapsed_targets_pass(self):
        self.assertEqual(str(validate_phase_b(self.request(), (interface(),))[0]), "192.168.1.0/24")
        request = self.request(["192.168.1.0/24", "192.168.1.0/25"])
        self.assertEqual(tuple(map(str, validate_phase_b(request, (interface(),)))), ("192.168.1.0/24",))

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

    def test_network_count_address_union_and_timeout_boundaries(self):
        networks = [f"10.0.{index}.0/27" for index in range(32)]
        self.assertEqual(len(self.request(networks, 5).networks), 32)
        self.assertEqual(self.request(["10.0.0.0/22"], 120).operation_timeout_seconds, 120)
        for invalid in (
            {"networks": networks + ["10.1.0.0/27"]},
            {"networks": ["10.0.0.0/22", "10.0.4.0/32"]},
            {"networks": ["10.0.0.0/24"], "operation_timeout_seconds": 4},
            {"networks": ["10.0.0.0/24"], "operation_timeout_seconds": 121},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_phase_a(invalid)

    def test_rejects_public_documentation_ipv6_and_unknown_fields(self):
        for body in (
            {"networks": ["8.8.8.0/24"]},
            {"networks": ["192.0.2.0/24"]},
            {"networks": ["2001:db8::/64"]},
            {"networks": ["10.0.0.0/24"], "extra": True},
        ):
            with self.subTest(body=body), self.assertRaises(ValidationError):
                validate_phase_a(body)

    def test_parses_only_up_hosts_with_addresses(self):
        hosts = parse_nmap_xml((FIXTURES / "nmap_host_discovery.xml").read_text())
        self.assertEqual([host.address for host in hosts], ["192.0.2.20"])
        self.assertEqual(hosts[0].mac_address, "02:00:00:00:00:20")
        self.assertEqual(parse_nmap_xml("<nmaprun><host><status state='up'/></host></nmaprun>"), ())

    def test_malformed_xml_fails(self):
        with self.assertRaises(ValidationError):
            parse_nmap_xml("<nmaprun>")


if __name__ == "__main__":
    unittest.main()
