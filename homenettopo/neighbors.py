"""Parser for macOS ARP output."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

_ARP_RE = re.compile(r"^\?(?:\s+\((?P<address>[^)]+)\)|\s+\((?P<name>[^)]+)\))")


@dataclass(frozen=True)
class NeighborFact:
    address: str
    mac_address: str | None
    interface: str | None
    name: str | None
    complete: bool


def _normalize_mac(value: str) -> str:
    return ":".join(part.zfill(2).lower() for part in value.split(":"))


def parse_neighbors(text: str) -> tuple[NeighborFact, ...]:
    items: dict[tuple[str, str | None], NeighborFact] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        address_match = re.search(r"\(([^)]+)\)", line)
        if not address_match:
            continue
        address = address_match.group(1)
        try:
            ipaddress.IPv4Address(address)
        except ipaddress.AddressValueError:
            continue
        prefix = line[: address_match.start()].strip()
        name = prefix if prefix and prefix != "?" else None
        interface_match = re.search(r"\bon\s+(\S+)", line)
        interface = interface_match.group(1) if interface_match else None
        incomplete = "(incomplete)" in line
        mac_match = re.search(r"\bat\s+([0-9a-fA-F:]+)", line)
        mac = _normalize_mac(mac_match.group(1)) if mac_match and not incomplete else None
        fact = NeighborFact(address, mac, interface, name, not incomplete and mac is not None)
        items[(address, interface)] = fact
    return tuple(sorted(items.values(), key=lambda item: (ipaddress.IPv4Address(item.address), item.interface or "")))
