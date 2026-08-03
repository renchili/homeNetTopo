"""Parser for macOS IPv4 routing-table output."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteFact:
    destination: str
    gateway: str
    flags: tuple[str, ...]
    interface: str
    is_default: bool


def _normalize_destination(value: str) -> str:
    if value == "default":
        return "0.0.0.0/0"
    if "/" in value:
        return str(ipaddress.IPv4Network(value, strict=False))
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        return value
    return f"{address}/32"


def parse_routes(text: str) -> tuple[RouteFact, ...]:
    routes: list[RouteFact] = []
    candidate_lines = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("Routing tables", "Internet:", "Destination")):
            continue
        candidate_lines += 1
        parts = line.split()
        if len(parts) < 4:
            continue
        destination, gateway, flags = parts[0], parts[1], parts[2]
        interface = parts[-1]
        try:
            normalized = _normalize_destination(destination)
        except ValueError:
            continue
        routes.append(RouteFact(normalized, gateway, tuple(flags), interface, destination == "default"))
    if candidate_lines and not routes:
        raise ValueError("route output did not contain recognizable IPv4 entries")
    return tuple(sorted(routes, key=lambda item: (not item.is_default, item.destination, item.gateway, item.interface)))
