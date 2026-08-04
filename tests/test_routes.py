import unittest

from homenettopo.routes import parse_routes


DEFAULT_ROUTE = """\
Routing tables

Internet:
Destination        Gateway            Flags               Netif Expire
default            192.0.2.1          UGScg                 en0
"""

SPECIFIC_ROUTE = """\
Routing tables

Internet:
Destination        Gateway            Flags               Netif Expire
10.10.0.0/16       192.0.2.2          UGSc                  en0
"""

MACOS_LOCAL_ROUTES = """\
Routing tables

Internet:
Destination        Gateway            Flags               Netif Expire
192.168.1/24       link#4             UCS                   en0      !
192.168.1.1        a:b:c:d:e:f         UHLWIir               en0   1194
"""


class RouteParserTests(unittest.TestCase):
    def test_parses_default_route(self):
        routes = parse_routes(DEFAULT_ROUTE)
        self.assertTrue(routes[0].is_default)
        self.assertEqual(routes[0].destination, "0.0.0.0/0")
        self.assertEqual(routes[0].gateway, "192.0.2.1")

    def test_parses_specific_route(self):
        route = parse_routes(SPECIFIC_ROUTE)[0]
        self.assertEqual(route.destination, "10.10.0.0/16")

    def test_parses_abbreviated_network_link_and_mac_gateways(self):
        routes = parse_routes(MACOS_LOCAL_ROUTES)
        by_destination = {route.destination: route for route in routes}
        self.assertEqual(by_destination["192.168.1.0/24"].gateway, "link#4")
        self.assertEqual(by_destination["192.168.1.0/24"].interface, "en0")
        self.assertEqual(by_destination["192.168.1.1/32"].gateway, "0a:0b:0c:0d:0e:0f")
        self.assertEqual(by_destination["192.168.1.1/32"].interface, "en0")

    def test_header_only_output_is_empty_but_unrecognized_entries_fail(self):
        self.assertEqual(parse_routes("Routing tables\n\nInternet:\nDestination Gateway Flags Netif\n"), ())
        invalid_outputs = (
            "unexpected route line\n",
            "Routing tables\n\nInternet:\nDestination Gateway Flags Netif\nalpha beta gamma delta\n",
            "Routing tables\n\nInternet:\nDestination Gateway Flags Netif\n10.0.0.0/24 not-a-gateway UGSc en0\n",
        )
        for output in invalid_outputs:
            with self.subTest(output=output), self.assertRaises(ValueError):
                parse_routes(output)


if __name__ == "__main__":
    unittest.main()
