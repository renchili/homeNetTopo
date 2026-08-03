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
10.10/16           192.0.2.2          UGSc                  en0
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


if __name__ == "__main__":
    unittest.main()
