from pathlib import Path
import unittest

from homenettopo.routes import parse_routes

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "macos"


class RouteParserTests(unittest.TestCase):
    def test_parses_default_route(self):
        routes = parse_routes((FIXTURES / "route_default.txt").read_text())
        self.assertTrue(routes[0].is_default)
        self.assertEqual(routes[0].destination, "0.0.0.0/0")
        self.assertEqual(routes[0].gateway, "192.0.2.1")

    def test_parses_specific_route(self):
        route = parse_routes((FIXTURES / "route_specific.txt").read_text())[0]
        self.assertEqual(route.destination, "10.10.0.0/16")


if __name__ == "__main__":
    unittest.main()
