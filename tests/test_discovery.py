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
    def request(self, network="192.168.1.0/24", timeout=30):
        return validate_phase_a({"networks": [network], "operation_timeout_seconds": timeout})

    def test_equal_and_contained_targets_pass(self):
        self.assertEqual(str(validate_phase_b(self.request(), (interface(),))[0]), "192.168.1.0/24")
        self.assertEqual(str(validate_phase_b(self.request("192.168.1.0/25"), (interface(),))[0]), "192.168.1.0/25")

    def test_supernet_partial_adjacent_unrelated_and_tunnel_fail(self):
        cases = [
            ("192.168.0.0/23", interface()),
            ("192.168.1.128/23", interface()),
            ("192.168.2.0/24", interface()),
            ("10.0.0.0/24", interface()),
            ("192.168.1.0/24", interface(kind="tunnel")),
        ]
        for target, local in cases:
            with self.subTest(target=target), self.assertRaises(ValidationError):
                validate_phase_b(self.request(target), (local,))

    def test_phase_a_exact_boundaries(self):
        networks = [f"10.0.{index}.0/27" for index in range(32)]
        request = validate_phase_a({"networks": networks, "operation_timeout_seconds": 5})
        self.assertEqual(len(request.networks), 32)
        with self.assertRaises(ValidationError):
            validate_phase_a({"networks": networks + ["10.1.0.0/27"]})
        with self.assertRaises(ValidationError):
            validate_phase_a({"networks": ["10.0.0.0/21"]})

    def test_rejects_public_documentation_and_ipv6(self):
        for value in ("8.8.8.0/24", "192.0.2.0/24", "2001:db8::/64"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.request(value)

    def test_parses_only_up_hosts_from_xml(self):
        hosts = parse_nmap_xml((FIXTURES / "nmap_host_discovery.xml").read_text())
        self.assertEqual([host.address for host in hosts], ["192.0.2.20"])
        self.assertEqual(hosts[0].mac_address, "02:00:00:00:00:20")

    def test_malformed_xml_fails(self):
        with self.assertRaises(ValidationError):
            parse_nmap_xml("<nmaprun>")


if __name__ == "__main__":
    unittest.main()
